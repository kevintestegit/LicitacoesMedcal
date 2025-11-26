import logging
from datetime import datetime
import sys
import os

# Adiciona diretório raiz ao path para importar modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.scrapers.pncp_client import PNCPClient
from modules.scrapers.pdf_extractor import PDFExtractor
from modules.ai.semantic_filter import SemanticFilter
from modules.scrapers.external_scrapers import FemurnScraper, FamupScraper, AmupeScraper, AmaScraper, MaceioScraper, MaceioInvesteScraper, MaceioSaudeScraper
from modules.database.database import init_db, get_session, Licitacao, ItemLicitacao, Produto, Configuracao
from modules.utils.notifications import WhatsAppNotifier
# from dashboard import processar_resultados, match_itens # Avoid importing dashboard to prevent circular or UI issues
import pandas as pd

# Configure Logging
logging.basicConfig(
    filename='autorun.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def run_automation():
    logging.info("Iniciando automação de busca...")
    print("🚀 Iniciando automação Medcal...")
    
    init_db()
    session = get_session()
    
    # 1. Carregar Configurações
    config_termos = session.query(Configuracao).filter_by(chave='termos_busca_padrao').first()
    termos_busca = config_termos.valor.split(',') if config_termos and config_termos.valor else []
    termos_busca = [t.strip() for t in termos_busca if t.strip()]
    
    # 2. Instanciar Clientes
    client = PNCPClient()
    
    # 3. Executar Buscas
    resultados_totais = []
    
    # PNCP
    try:
        logging.info("Buscando no PNCP...")
        print("Buscando no PNCP...")
        # Busca padrão de 60 dias, estados do Nordeste
        res_pncp = client.buscar_oportunidades(dias=60, estados=['RN', 'PB', 'PE', 'AL', 'CE', 'BA'], termos_positivos=client.TERMOS_POSITIVOS_PADRAO)
        resultados_totais.extend(res_pncp)
        logging.info(f"PNCP: {len(res_pncp)} encontrados.")
    except Exception as e:
        logging.error(f"Erro no PNCP: {e}")

    # Scrapers Externos
    scrapers = [
        (FemurnScraper, "FEMURN"),
        (FamupScraper, "FAMUP"),
        (AmupeScraper, "AMUPE"),
        (AmaScraper, "AMA"),
        (MaceioScraper, "Maceió"),
        (MaceioInvesteScraper, "Maceió Investe"),
        (MaceioSaudeScraper, "Maceió Saúde")
    ]
    
    for ScraperClass, name in scrapers:
        try:
            logging.info(f"Buscando em {name}...")
            print(f"Buscando em {name}...")
            scraper = ScraperClass()
            res = scraper.buscar_oportunidades(client.TERMOS_POSITIVOS_PADRAO, termos_negativos=client.TERMOS_NEGATIVOS_PADRAO)
            resultados_totais.extend(res)
            logging.info(f"{name}: {len(res)} encontrados.")
        except Exception as e:
            logging.error(f"Erro em {name}: {e}")

    # 4. Processar e Salvar (Lógica Customizada para evitar dependência de UI do dashboard)
    logging.info(f"Processando {len(resultados_totais)} resultados...")
    print(f"Processando {len(resultados_totais)} resultados...")
    
    novos = 0
    alertas = []
    
    # Carrega produtos para match
    produtos = session.query(Produto).all()
    
    for res in resultados_totais:
        # Filtro de Data (Cópia da lógica do dashboard)
        encerramento_str = res.get('data_encerramento_proposta')
        should_exclude = False
        if encerramento_str:
            try:
                fim_dt = datetime.fromisoformat(encerramento_str).date()
                if fim_dt < datetime.now().date():
                    should_exclude = True
            except: pass
        else:
            origem = res.get('origem')
            if not origem or origem == 'PNCP':
                should_exclude = True
        
        if should_exclude: continue
        
        # --- NOVO: FILTRO SEMÂNTICO (IA GATEKEEPER) ---
        # Antes de salvar, perguntamos para a IA se é realmente relevante
        # Isso evita "Enxoval", "Livros" e outros falsos positivos que passaram pelos filtros de palavras
        semantic_filter = SemanticFilter()
        is_relevant = semantic_filter.is_relevant(res['objeto'])
        
        if not is_relevant:
            logging.info(f"🚫 Bloqueado pelo Filtro Semântico: {res['objeto'][:50]}...")
            continue
        # --------------------------------------------------

        # Verifica duplicidade
        exists = session.query(Licitacao).filter_by(pncp_id=res['pncp_id']).first()
        if not exists:
            # Salva Licitacao
            lic = Licitacao(
                pncp_id=res['pncp_id'],
                orgao=res['orgao'],
                uf=res['uf'],
                modalidade=res['modalidade'],
                data_sessao=datetime.fromisoformat(res['data_sessao']) if res.get('data_sessao') else None,
                data_publicacao=datetime.fromisoformat(res['data_publicacao']) if res.get('data_publicacao') else None,
                data_inicio_proposta=datetime.fromisoformat(res['data_inicio_proposta']) if res.get('data_inicio_proposta') else None,
                data_encerramento_proposta=datetime.fromisoformat(res['data_encerramento_proposta']) if res.get('data_encerramento_proposta') else None,
                objeto=res['objeto'],
                link=res['link']
            )
            session.add(lic)
            session.flush()
            
            # 4.1. Tentar baixar e ler PDF para pegar preços reais
            pdf_extractor = PDFExtractor()
            
            # Se não veio itens da API, ou se queremos validar preços no PDF
            arquivos = []
            try:
                arquivos = client.buscar_arquivos(res)
            except: pass
            
            # Procura Termo de Referência ou Edital
            url_pdf = None
            for arq in arquivos:
                nome = (arq.get('titulo') or arq.get('nome') or "").upper()
                if "TERMO" in nome or "EDITAL" in nome or "REFERENCIA" in nome:
                    url_pdf = arq.get('url')
                    break
            
            itens_pdf = []
            if url_pdf:
                logging.info(f"Baixando PDF: {url_pdf}")
                pdf_content = client.download_arquivo(url_pdf)
                if pdf_content:
                    pdf_text = pdf_extractor.extract_text(pdf_content)
                    itens_pdf = pdf_extractor.extract_financial_data(pdf_text)
            
            # Mesclar itens da API com itens do PDF (prioridade para PDF que tem Max Price confiável)
            # Se itens_pdf existir, usamos ele para enriquecer
            
            # Salva Itens (Priorizando PDF se tiver)
            itens_finais = itens_pdf if itens_pdf else itens_api
            
            lucro_total_potencial = 0.0
            itens_lucrativos = []
            
            for i in itens_finais:
                # Normaliza chaves (PDF usa 'valor_maximo', API usa 'valor_unitario')
                v_max = float(i.get('valor_maximo') or i.get('valor_unitario') or 0)
                qtd = float(i.get('quantidade') or 0)
                desc = i.get('descricao', '').upper()
                
                item_db = ItemLicitacao(
                    licitacao_id=lic.id,
                    numero_item=int(i.get('numero_item') or i.get('numero') or 0),
                    descricao=desc,
                    quantidade=qtd,
                    unidade=i.get('unidade', ''),
                    valor_estimado=v_max * qtd,
                    valor_unitario=v_max
                )
                
                # MATCH FINANCEIRO
                match_encontrado = False
                for prod in produtos:
                    kws = [k.strip().upper() for k in prod.palavras_chave.split(',')]
                    if any(k in desc for k in kws):
                        item_db.produto_match_id = prod.id
                        match_encontrado = True
                        
                        # Análise de Lucro
                        custo = prod.preco_custo or 0
                        margem_min = 0.30 # 30% margem mínima fixa por enquanto
                        impostos = 0.10 # 10% impostos
                        
                        preco_minimo_venda = custo * (1 + margem_min + impostos)
                        
                        if v_max >= preco_minimo_venda:
                            lucro_unit = v_max - (custo * (1 + impostos)) # Lucro bruto aprox
                            lucro_total = lucro_unit * qtd
                            lucro_total_potencial += lucro_total
                            itens_lucrativos.append({
                                "produto": prod.nome,
                                "qtd": qtd,
                                "teto": v_max,
                                "custo": custo,
                                "lucro": lucro_total
                            })
                        break
                
                session.add(item_db)
            
            novos += 1
            
            if itens_lucrativos:
                # Monta Alerta Rico
                msg = f"💰 *Oportunidade Lucrativa!* \n"
                msg += f"🏥 {lic.orgao} ({lic.uf})\n"
                msg += f"💵 *Lucro Est. Total: R$ {lucro_total_potencial:,.2f}*\n\n"
                
                for item in itens_lucrativos[:3]: # Top 3 itens
                    msg += f"📦 {item['produto']}\n"
                    msg += f"   Qtd: {item['qtd']} | Teto: R$ {item['teto']:.2f}\n"
                    msg += f"   ✅ Lucro: R$ {item['lucro']:,.2f}\n"
                
                if len(itens_lucrativos) > 3:
                    msg += f"...e mais {len(itens_lucrativos)-3} itens.\n"
                    
                msg += f"\n🔗 {lic.link}"
                alertas.append(msg)

    session.commit()
    
    # 5. Notificar
    if alertas:
        logging.info(f"Enviando {len(alertas)} alertas...")
        conf_phone = session.query(Configuracao).filter_by(chave='whatsapp_phone').first()
        conf_key = session.query(Configuracao).filter_by(chave='whatsapp_apikey').first()
        
        if conf_phone and conf_key and conf_phone.valor and conf_key.valor:
            notifier = WhatsAppNotifier(conf_phone.valor, conf_key.valor)
            for alert_msg in alertas:
                notifier.enviar_mensagem(alert_msg)
                time.sleep(1) # Delay para não bloquear
    
    session.close()
    logging.info("Automação finalizada com sucesso.")
    print("✅ Automação finalizada!")

if __name__ == "__main__":
    run_automation()
