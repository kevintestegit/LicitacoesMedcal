import concurrent.futures
from datetime import datetime
import unicodedata
import json

from modules.database.database import get_session, Licitacao, ItemLicitacao, Produto, Configuracao, LicitacaoFeature
from modules.scrapers.pncp_client import PNCPClient
from modules.ai.improved_matcher import SemanticMatcher
from modules.utils.notifications import WhatsAppNotifier
from modules.utils.notification_cache import notification_cache
from modules.core.opportunity_collector import collect_opportunities
from modules.utils.logging_config import get_logger

logger = get_logger(__name__)

def normalize_text(texto: str) -> str:
    if not texto:
        return ""
    return unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('ASCII').upper()

def safe_parse_date(date_str):
    if isinstance(date_str, datetime):
        return date_str
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
            logger.info(msg)

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

    def execute_full_search(self, dias=60, estados=['RN', 'PB', 'PE', 'AL'], fontes=None, callback=None):
        """
        Executa busca completa.
        
        Args:
            dias: Dias de histórico para buscar
            estados: Lista de UFs
            fontes: Lista de fontes a usar. Se None, usa todas. Ex: ['pncp', 'femurn', 'famup']
            callback: Função de callback para logs
        """
        self.log(f"Iniciando varredura. Dias={dias}, Estados={estados}, Fontes={fontes or 'TODAS'}...", callback)
        resultados_raw = collect_opportunities(
            dias=dias,
            estados=estados,
            fontes=fontes,
            termos_positivos=self.client.TERMOS_POSITIVOS_PADRAO,
            termos_negativos=self.client.TERMOS_NEGATIVOS_PADRAO,
            apenas_abertas=True,
        )
        self.log(f"Total de oportunidades encontradas (dedupe aplicado): {len(resultados_raw)}", callback)
        return self.run_search_pipeline(resultados_raw, callback)

    def run_search_pipeline(self, resultados_raw, callback=None, *, return_details: bool = False, send_immediate_alerts: bool = True):
        """
        Executa o pipeline completo: Filtro -> Async Fetch -> Save -> Match -> Alert
        """
        self.log("Iniciando pipeline de processamento...", callback)
        session = get_session()
        high_priority_alerts = []
        
        # 1. Filtro Data
        resultados = []
        hoje_date = datetime.now().date()
        for res in resultados_raw:
            enc_dt = safe_parse_date(res.get('data_encerramento_proposta'))
            if enc_dt and enc_dt.date() < hoje_date:
                continue
            if not enc_dt:
                origem = res.get("origem") or res.get("fonte")
                if not origem or str(origem).upper() == "PNCP":
                    continue
            
            # Score preliminar
            score = 0
            dias_restantes = res.get('dias_restantes')
            if dias_restantes and dias_restantes <= 7: score += 5
            res['match_score'] = score
            resultados.append(res)

        # 2. Identifica Novos
        candidatos_novos = []
        for res in resultados:
            pncp_id = res.get("pncp_id")
            if not pncp_id:
                continue
            exists = session.query(Licitacao).filter_by(pncp_id=pncp_id).first()
            if not exists:
                candidatos_novos.append(res)

        self.log(f"Novas licitações para processar: {len(candidatos_novos)}", callback)

        # 3. Async Fetch
        if candidatos_novos:
            with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
                pncp_candidates = [
                    r
                    for r in candidatos_novos
                    if not (r.get("itens") or [])
                    and r.get("cnpj")
                    and r.get("ano")
                    and r.get("seq")
                ]
                future_to_res = {executor.submit(self.client.buscar_itens, res): res for res in pncp_candidates}
                for future in concurrent.futures.as_completed(future_to_res):
                    res = future_to_res[future]
                    try:
                        res['_itens_preloaded'] = future.result()
                    except Exception as exc:
                        logger.warning("Erro ao pré-carregar itens para %s: %s", res.get('pncp_id'), exc, exc_info=True)
                        res['_itens_preloaded'] = []

        # 4. Salvar e Match
        novos = 0
        for res in candidatos_novos:
            lic = Licitacao(
                pncp_id=res['pncp_id'],
                orgao=res.get('orgao'),
                uf=res.get('uf'),
                modalidade=res.get('modalidade'),
                data_sessao=safe_parse_date(res.get('data_sessao')),
                data_publicacao=safe_parse_date(res.get('data_publicacao')),
                data_inicio_proposta=safe_parse_date(res.get('data_inicio_proposta')),
                data_encerramento_proposta=safe_parse_date(res.get('data_encerramento_proposta')),
                objeto=res.get('objeto'),
                link=res.get('link')
            )
            session.add(lic)
            session.flush() # Get ID

            # Registra sinais para treino futuro (NLP/classificador)
            termos_hit = res.get('termos_encontrados') or []
            feature = LicitacaoFeature(
                licitacao_id=lic.id,
                fonte=res.get('origem') or res.get('fonte') or "PNCP",
                motivo_aprovacao=res.get('motivo_aprovacao'),
                termos_encontrados=json.dumps(termos_hit) if termos_hit else None,
                objeto_resumido=(res.get('objeto') or "")[:400]
            )
            session.add(feature)

            itens_api = res.get("itens") or res.get("_itens_preloaded", [])
            if not itens_api and res.get("cnpj") and res.get("ano") and res.get("seq"):
                itens_api = self.client.buscar_itens(res)
            
            # --- DEEP SCAN DESABILITADO (causa lentidão extrema) ---
            # O Deep Scan baixa PDFs e usa IA para extrair itens, mas:
            # 1. Consome muitas requisições de IA (rate limit)
            # 2. Leva 10-30s por PDF
            # 3. A maioria das licitações já tem itens na API
            # Para análise profunda, use a aba "🧠 Análise IA" no Dashboard
            #
            # deve_fazer_deep_scan = False
            # if not itens_api:
            #     deve_fazer_deep_scan = True
            # ... (código removido para performance)

            itens_filtrados = self.filtrar_itens_negativos(itens_api, self.client.TERMOS_NEGATIVOS_PADRAO)

            for i in itens_filtrados:
                # Normaliza campos (compatibilidade com diferentes fontes: API PNCP vs PDF Extractor)
                numero = i.get('numero') or i.get('numero_item') or 0
                valor_unit = i.get('valor_unitario') or i.get('valor_maximo') or 0
                valor_est = i.get('valor_estimado') or i.get('valor_total') or 0
                
                session.add(ItemLicitacao(
                    licitacao_id=lic.id,
                    numero_item=numero,
                    descricao=i.get('descricao', ''),
                    quantidade=i.get('quantidade') or 0,
                    unidade=i.get('unidade', 'UN'),
                    valor_estimado=valor_est,
                    valor_unitario=valor_unit
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
                alert_data = {
                    "pncp_id": res.get("pncp_id"), # Added for cache tracking
                    "orgao": res.get('orgao'),
                    "uf": res.get('uf'),
                    "modalidade": res.get('modalidade'),
                    "match_score": res.get('match_score'),
                    "matched_products": matched_products,
                    "dias_restantes": res.get('dias_restantes'),
                    "data_encerramento_proposta": res.get('data_encerramento_proposta'),
                    "link": res.get('link')
                }
                high_priority_alerts.append(alert_data)
                
                if send_immediate_alerts:
                    # Verifica cache para não re-enviar (Fluxo Contínuo)
                    if not notification_cache.was_already_sent(res.get("pncp_id")):
                        # Envia alerta IMEDIATAMENTE
                        if self.enviar_relatorio_whatsapp([alert_data], session):
                            notification_cache.mark_as_sent(res.get("pncp_id"))
            
            # Salva no banco IMEDIATAMENTE para aparecer no Dashboard
            session.commit()
            novos += 1

        session.close()
        
        self.log(f"Processamento concluído. {novos} importados.", callback)
        if return_details:
            return {"novos": novos, "alerts": high_priority_alerts}
        return novos
