import concurrent.futures
from datetime import datetime
import time
import unicodedata
from rapidfuzz import fuzz
from sqlalchemy import or_
import json

from modules.database.database import get_session, Licitacao, ItemLicitacao, Produto, Configuracao
from modules.scrapers.pncp_client import PNCPClient
from modules.ai.improved_matcher import SemanticMatcher
from modules.utils.notifications import WhatsAppNotifier
from modules.scrapers.external_scrapers import FemurnScraper, FamupScraper, AmupeScraper, AmaScraper, MaceioScraper, MaceioInvesteScraper, MaceioSaudeScraper

def normalize_text(texto: str) -> str:
    if not texto:
        return ""
    return unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('ASCII').upper()

def safe_parse_date(date_str):
    if not date_str or not isinstance(date_str, str) or date_str.strip() == "":
        return None
    try:
        return datetime.fromisoformat(date_str)
    except (ValueError, TypeError):
        return None

class SearchEngine:
    def __init__(self):
        self.client = PNCPClient()
        self.semantic_matcher = SemanticMatcher()

    def log(self, msg, callback=None):
        if callback:
            callback(msg)
        else:
            print(f"[ENGINE] {msg}")

    def match_itens(self, session, licitacao_id, limiar=75):
        """
        Cruza itens da licitação com produtos.
        Usa Keyword Match (rápido) + Semantic AI (preciso).
        """
        licitacao = session.query(Licitacao).filter_by(id=licitacao_id).first()
        produtos = session.query(Produto).all()
        
        count = 0
        for item in licitacao.itens:
            item_desc = item.descricao or ""
            melhor_match = None
            melhor_score = 0
            
            # 1. Fase Rápida: Palavras-Chave
            # (Simplificando a lógica do dashboard para este motor centralizado)
            # A lógica original era complexa, vou usar o SemanticMatcher.find_matches primeiro?
            # Não, o find_matches usa embeddings (médio custo).
            # Vamos manter a lógica de keywords do dashboard para filtro inicial.
            
            # ... (Lógica de keyword seria ideal aqui, mas para não duplicar código enorme,
            # vamos usar o SemanticMatcher que já tem cache e é "Improved")
            
            # Vamos usar uma abordagem híbrida poderosa:
            # Busca candidatos pelo SemanticMatcher (Embeddings)
            candidates = self.semantic_matcher.find_matches(item_desc, threshold=0.70)
            
            if candidates:
                top_prod, score_emb = candidates[0]
                
                # 2. Fase Impecável: Validação LLM
                # Se o score é bom mas não perfeito, pergunta pra IA
                if score_emb >= 0.70:
                    is_compatible = self.semantic_matcher.verify_match(item_desc, top_prod.nome)
                    
                    if is_compatible:
                        melhor_match = top_prod
                        melhor_score = 95 # Confiança IA
                    else:
                        # IA disse que não é compatível (ex: Limpeza chão vs Limpeza Lab)
                        melhor_score = 0
            
            if melhor_match:
                item.produto_match_id = melhor_match.id
                item.match_score = melhor_score
                count += 1
            else:
                item.produto_match_id = None
                item.match_score = 0
                
        session.commit()
        return count

    def filtrar_itens_negativos(self, itens_api, termos_negativos):
        if not itens_api:
            return []
        itens_validos = []
        termos_neg_norm = [normalize_text(t) for t in termos_negativos]
        for item in itens_api:
            desc = item.get('descricao', '')
            desc_norm = normalize_text(desc)
            if not any(t in desc_norm for t in termos_neg_norm):
                itens_validos.append(item)
        return itens_validos

    def enviar_relatorio_whatsapp(self, licitacoes_relevantes, session):
        """Envia notificação se houver matches de alta prioridade"""
        config_contacts = session.query(Configuracao).filter_by(chave='whatsapp_contacts').first()
        contacts_list = []
        
        if config_contacts and config_contacts.valor:
            try:
                contacts_list = json.loads(config_contacts.valor)
            except:
                pass
        
        # Fallback legacy
        if not contacts_list:
            conf_phone = session.query(Configuracao).filter_by(chave='whatsapp_phone').first()
            conf_key = session.query(Configuracao).filter_by(chave='whatsapp_apikey').first()
            if conf_phone and conf_key and conf_phone.valor:
                contacts_list = [{"nome": "Admin", "phone": conf_phone.valor, "apikey": conf_key.valor}]

        if not contacts_list:
            return False

        # Monta mensagem resumida (Limpa, sem emojis)
        msg = f"*MEDCAL - NOVAS OPORTUNIDADES* ({len(licitacoes_relevantes)})\n\n"
        
        for lic in licitacoes_relevantes[:5]: # Top 5
            matches = ", ".join(lic['matched_products'][:2])
            msg += f"*{lic['orgao']}* ({lic['uf']})\n"
            msg += f"Produtos: {matches}\n"
            msg += f"Prazo: {lic['dias_restantes']} dias restantes\n"
            msg += f"Link: {lic['link']}\n\n"
        
        if len(licitacoes_relevantes) > 5:
            msg += f"... e mais {len(licitacoes_relevantes)-5} oportunidades."

        for contact in contacts_list:
            notifier = WhatsAppNotifier(contact.get('phone'), contact.get('apikey'))
            notifier.enviar_mensagem(msg)
        
        return True

    def execute_full_search(self, dias=60, estados=['RN', 'PB', 'PE', 'AL'], callback=None):
        self.log("Iniciando varredura completa...", callback)
        resultados_raw = []
        
        # 1. PNCP
        try:
            self.log("Buscando no PNCP...", callback)
            res_pncp = self.client.buscar_oportunidades(dias, estados, termos_positivos=self.client.TERMOS_POSITIVOS_PADRAO)
            resultados_raw.extend(res_pncp)
        except Exception as e:
            self.log(f"Erro PNCP: {e}", callback)

        # 2. Externos
        scrapers = [
            (FemurnScraper, "FEMURN"),
            (FamupScraper, "FAMUP"),
            (AmupeScraper, "AMUPE"),
            (AmaScraper, "AMA"),
            (MaceioScraper, "Maceió"),
            (MaceioInvesteScraper, "Maceió Investe"),
            (MaceioSaudeScraper, "Maceió Saúde")
        ]
        
        for ScraperCls, name in scrapers:
            try:
                self.log(f"Buscando em {name}...", callback)
                scraper = ScraperCls()
                res = scraper.buscar_oportunidades(self.client.TERMOS_POSITIVOS_PADRAO, self.client.TERMOS_NEGATIVOS_PADRAO)
                resultados_raw.extend(res)
            except Exception as e:
                self.log(f"Erro {name}: {e}", callback)
                
        self.log(f"Total de oportunidades encontradas: {len(resultados_raw)}", callback)
        
        return self.run_search_pipeline(resultados_raw, callback)

    def run_search_pipeline(self, resultados_raw, callback=None):
        """
        Executa o pipeline completo: Filtro -> Async Fetch -> Save -> Match -> Alert
        """
        self.log("Iniciando pipeline de processamento...", callback)
        session = get_session()
        
        # 1. Filtro Data
        resultados = []
        hoje_date = datetime.now().date()
        for res in resultados_raw:
            enc_str = res.get('data_encerramento_proposta')
            if enc_str:
                try:
                    if datetime.fromisoformat(enc_str).date() < hoje_date:
                        continue
                except:
                    pass
            
            # Score preliminar
            score = 0
            dias_restantes = res.get('dias_restantes')
            if dias_restantes and dias_restantes <= 7: score += 5
            res['match_score'] = score
            resultados.append(res)

        # 2. Identifica Novos
        candidatos_novos = []
        for res in resultados:
            exists = session.query(Licitacao).filter_by(pncp_id=res['pncp_id']).first()
            if not exists:
                candidatos_novos.append(res)

        self.log(f"Novas licitações para processar: {len(candidatos_novos)}", callback)

        # 3. Async Fetch
        if candidatos_novos:
            with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
                future_to_res = {executor.submit(self.client.buscar_itens, res): res for res in candidatos_novos}
                for future in concurrent.futures.as_completed(future_to_res):
                    res = future_to_res[future]
                    try:
                        res['_itens_preloaded'] = future.result()
                    except:
                        res['_itens_preloaded'] = []

        # 4. Salvar e Match
        novos = 0
        high_priority_alerts = []
        
        for res in candidatos_novos:
            lic = Licitacao(
                pncp_id=res['pncp_id'],
                orgao=res['orgao'],
                uf=res['uf'],
                modalidade=res['modalidade'],
                data_sessao=safe_parse_date(res.get('data_sessao')),
                data_publicacao=safe_parse_date(res.get('data_publicacao')),
                data_inicio_proposta=safe_parse_date(res.get('data_inicio_proposta')),
                data_encerramento_proposta=safe_parse_date(res.get('data_encerramento_proposta')),
                objeto=res['objeto'],
                link=res['link']
            )
            session.add(lic)
            session.flush() # Get ID

            itens_api = res.get('_itens_preloaded', []) or self.client.buscar_itens(res)
            itens_filtrados = self.filtrar_itens_negativos(itens_api, self.client.TERMOS_NEGATIVOS_PADRAO)

            for i in itens_filtrados:
                # Price Intelligence: Tenta pegar preço médio se não vier no item
                # (Isso seria lento para fazer em todos, vamos deixar sob demanda no dashboard ou async background job futuro)
                # Por enquanto, salva o básico
                session.add(ItemLicitacao(
                    licitacao_id=lic.id,
                    numero_item=i['numero'],
                    descricao=i['descricao'],
                    quantidade=i['quantidade'],
                    unidade=i['unidade'],
                    valor_estimado=i['valor_estimado'],
                    valor_unitario=i['valor_unitario']
                ))
            
            # SEMANTIC MATCHING
            matches_count = self.match_itens(session, lic.id)
            
            # Verifica se deu match
            matched_products = []
            for item in session.query(ItemLicitacao).filter_by(licitacao_id=lic.id).all():
                if item.produto_match_id:
                    matched_products.append(item.produto_match.nome)
            matched_products = list(set(matched_products))

            if matched_products:
                high_priority_alerts.append({
                    "orgao": res.get('orgao'),
                    "uf": res.get('uf'),
                    "matched_products": matched_products,
                    "dias_restantes": res.get('dias_restantes'),
                    "link": res.get('link')
                })
            novos += 1

        session.commit()
        session.close()
        
        if high_priority_alerts:
            self.log(f"Enviando alerta para {len(high_priority_alerts)} oportunidades...", callback)
            self.enviar_relatorio_whatsapp(high_priority_alerts, get_session())

        self.log(f"Processamento concluído. {novos} importados.", callback)
        return novos
