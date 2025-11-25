import streamlit as st
import pandas as pd
from pncp_client import PNCPClient
from external_scrapers import FemurnScraper, FamupScraper, AmupeScraper, AmaScraper, MaceioScraper, MaceioInvesteScraper, MaceioSaudeScraper
from notifications import WhatsAppNotifier
from ai_helper import get_google_price_estimate, estimate_market_price, configure_genai, summarize_bidding
from database import init_db, get_session, Produto, Licitacao, ItemLicitacao, Configuracao
from sqlalchemy import func
from datetime import datetime
from rapidfuzz import fuzz
import unicodedata

# Inicializa Banco
init_db()

st.set_page_config(page_title="Medcal Licitações", layout="wide", page_icon="🏥")

# --- UTILITÁRIOS DE TEXTO ---
def normalize_text(texto: str) -> str:
    if not texto:
        return ""
    return unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('ASCII').upper()

def safe_parse_date(date_str):
    """Converte string ISO para datetime de forma segura. Retorna None se inválido."""
    if not date_str or not isinstance(date_str, str) or date_str.strip() == "":
        return None
    try:
        return datetime.fromisoformat(date_str)
    except (ValueError, TypeError):
        return None

def best_match_against_keywords(texto: str, keywords):
    """Retorna (melhor_score, melhor_keyword) usando fuzzy parcial."""
    if not texto or not keywords:
        return 0, ""
    texto_norm = normalize_text(texto)
    best_score = 0
    best_kw = ""
    for kw in keywords:
        if not kw:
            continue
        score = fuzz.partial_ratio(normalize_text(kw), texto_norm)
        if score > best_score:
            best_score = score
            best_kw = kw
    return best_score, best_kw

# --- SIDEBAR ---
st.sidebar.title("🏥 Medcal Gestão")
page = st.sidebar.radio("Navegação", ["Dashboard", "Buscar Licitações", "Gestão (Kanban)", "Meu Catálogo", "📥 Importar & Relatórios", "Configurações"])

# --- FUNÇÕES AUXILIARES ---
def salvar_produtos(df_editor):
    session = get_session()
    # Lógica simplificada: deleta tudo e recria (para protótipo)
    # Em produção, faríamos upsert
    session.query(Produto).delete()
    
    for index, row in df_editor.iterrows():
        if row['Nome do Produto']:
            p = Produto(
                nome=row['Nome do Produto'],
                palavras_chave=row['Palavras-Chave'],
                preco_custo=float(row['Preço de Custo']),
                margem_minima=float(row['Margem (%)']),
                preco_referencia=float(row.get('Preço Referência', 0.0)),
                fonte_referencia=str(row.get('Fonte Referência', ""))
            )
            session.add(p)
    session.commit()
    session.close()
    st.success("Catálogo atualizado!")

def match_itens(session, licitacao_id, limiar=80):
    """Tenta cruzar itens da licitação com produtos do catálogo com fuzzy matching"""
    licitacao = session.query(Licitacao).filter_by(id=licitacao_id).first()
    produtos = session.query(Produto).all()
    
    count = 0
    for item in licitacao.itens:
        item_desc = item.descricao or ""
        melhor_match = None
        melhor_score = 0
        
        for prod in produtos:
            keywords = [k.strip() for k in prod.palavras_chave.split(',') if k.strip() and len(k.strip()) > 3]
            keywords.append(prod.nome)
            score, _ = best_match_against_keywords(item_desc, keywords)
            if score > melhor_score:
                melhor_match = prod
                melhor_score = score
        
        if melhor_match and melhor_score >= limiar:
            item.produto_match_id = melhor_match.id
            item.match_score = melhor_score
            count += 1
        else:
            item.produto_match_id = None
            item.match_score = melhor_score
            
    session.commit()
    return count

def processar_resultados(resultados_raw):
    """Processa, filtra, pontua e salva uma lista de resultados brutos."""
    if not resultados_raw:
        st.warning("Nenhum resultado encontrado para processar.")
        return

    session = get_session()
    client = PNCPClient()
    
    # Carrega produtos para matching
    prods = session.query(Produto).all()
    
    total_api = len(resultados_raw)
    
    # Filtro de Data de Início de Proposta (Pós-processamento)
    resultados = []
    hoje_date = datetime.now().date()
    ignorados_data = 0
    
    for res in resultados_raw:
        # REGRA SIMPLES: Mostra APENAS se ainda dá tempo de enviar proposta
        # Critério: Data de FIM de proposta >= HOJE

        encerramento_str = res.get('data_encerramento_proposta')
        should_exclude = False

        if encerramento_str:
            try:
                fim_dt = datetime.fromisoformat(encerramento_str).date()
                # Se data de fim JÁ PASSOU → EXCLUI
                if fim_dt < hoje_date:
                    should_exclude = True
            except:
                # Se der erro ao parsear data, mantém (não exclui por segurança)
                pass
        else:
            # Se NÃO tem data de encerramento:
            # - Se for PNCP (sem 'origem' ou origem='PNCP'), exclui.
            # - Se for Scraper Externo (tem 'origem' e != 'PNCP'), MANTÉM (pois scrapers de PDF não pegam data).
            origem = res.get('origem')
            if not origem or origem == 'PNCP':
                should_exclude = True
            else:
                should_exclude = False # Mantém resultados de scrapers externos sem data

        if should_exclude:
            ignorados_data += 1
            continue

        # --- Lógica de Priorização (Match Score) ---
        score = 0
        matched_tags = []
        obj_text = res['objeto']
        obj_norm = normalize_text(obj_text)

        # Verifica match com produtos do catálogo usando fuzzy
        for p in prods:
            p_keywords = [k.strip() for k in p.palavras_chave.split(',') if k.strip()]
            p_keywords.append(p.nome)
            match_score, kw = best_match_against_keywords(obj_text, p_keywords)
            if match_score >= 75:
                bonus = 15 if match_score >= 85 else 10
                score += bonus
                matched_tags.append(p.nome)

        # Termos positivos padrão (peso menor, usa texto normalizado)
        for t in client.TERMOS_POSITIVOS_PADRAO:
            if normalize_text(t) in obj_norm:
                score += 0.5

        # Peso por urgência de prazo
        dias_restantes = res.get('dias_restantes')
        if dias_restantes in (None, -999) and res.get('data_encerramento_proposta'):
            dias_restantes = client.calcular_dias(res.get('data_encerramento_proposta'))
        res['dias_restantes'] = dias_restantes
        if dias_restantes is not None and dias_restantes >= 0:
            if dias_restantes <= 7:
                score += 5
            elif dias_restantes <= 14:
                score += 3
        
        res['match_score'] = round(score, 1)
        res['matched_products'] = list(set(matched_tags)) # Remove duplicatas

        resultados.append(res)

    # Ordena por Score (Decrescente)
    resultados.sort(key=lambda x: x.get('match_score', 0), reverse=True)

    st.write(f"  Diagnóstico da Busca:")
    st.write(f"- Encontrados na API: {total_api}")
    st.write(f"- Ignorados pelo Filtro de Data (Passado): {ignorados_data}")
    st.write(f"- Restantes para Importação: {len(resultados)}")
    
    # Salvar no Banco
    novos = 0
    ignorados_duplicados = 0
    high_priority_alerts = []
    alert_threshold = 15
    
    for res in resultados:
        exists = session.query(Licitacao).filter_by(pncp_id=res['pncp_id']).first()
        if not exists:
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
            session.flush()

            # Buscar itens
            itens_api = client.buscar_itens(res)
            for i in itens_api:
                item_db = ItemLicitacao(
                    licitacao_id=lic.id,
                    numero_item=i['numero'],
                    descricao=i['descricao'],
                    quantidade=i['quantidade'],
                    unidade=i['unidade'],
                    valor_estimado=i['valor_estimado'],
                    valor_unitario=i['valor_unitario']
                )
                session.add(item_db)
            
            match_itens(session, lic.id)
            novos += 1

            if res.get('match_score', 0) >= alert_threshold or res.get('matched_products'):
                high_priority_alerts.append({
                    "orgao": res.get('orgao'),
                    "uf": res.get('uf'),
                    "modalidade": res.get('modalidade'),
                    "match_score": res.get('match_score'),
                    "matched_products": res.get('matched_products', []),
                    "dias_restantes": res.get('dias_restantes'),
                    "link": res.get('link')
                })
        else:
            ignorados_duplicados += 1
    
    session.commit()
    st.success(f"Busca finalizada! {novos} novas licitações importadas.")

    # Notificação automática de alta prioridade
    if high_priority_alerts:
        conf_phone = session.query(Configuracao).filter_by(chave='whatsapp_phone').first()
        conf_key = session.query(Configuracao).filter_by(chave='whatsapp_apikey').first()
        phone_val = conf_phone.valor if conf_phone else ""
        key_val = conf_key.valor if conf_key else ""

        if phone_val and key_val:
            notifier = WhatsAppNotifier(phone_val, key_val)
            preview = high_priority_alerts[:5]
            msg_lines = ["🚨 Novas licitações relevantes encontradas:"]
            for alert in preview:
                prazo = f"{alert['dias_restantes']}d" if alert.get('dias_restantes') not in (None, -999) else "prazo não informado"
                produtos = ", ".join(alert.get('matched_products', [])) or "sem match claro"
                msg_lines.append(
                    f"- [{alert['uf']}] {alert['orgao']} ({alert['modalidade']})\n  Score: {alert.get('match_score')}\n  Prazo: {prazo}\n  Produtos: {produtos}\n  {alert['link']}"
                )
            if len(high_priority_alerts) > len(preview):
                msg_lines.append(f"...+{len(high_priority_alerts) - len(preview)} outras.")
            notifier.enviar_mensagem("\n".join(msg_lines))
        else:
            st.info("Novas licitações prioritárias encontradas. Configure WhatsApp em Configurações para receber alertas.")

    session.close()

# --- PÁGINAS ---

if page == "Meu Catálogo":
    st.header("📦 Catálogo de Produtos")
    st.info("Cadastre aqui os produtos que a Medcal vende. O sistema usará as 'Palavras-Chave' para encontrar oportunidades.")
    
    session = get_session()
    produtos = session.query(Produto).all()
    session.close()
    
    data = []
    for p in produtos:
        data.append({
            "Nome do Produto": p.nome,
            "Palavras-Chave": p.palavras_chave,
            "Preço de Custo": p.preco_custo,
            "Margem (%)": p.margem_minima,
            "Preço Referência": p.preco_referencia,
            "Fonte Referência": p.fonte_referencia
        })
    
    if not data:
        data = [{
            "Nome do Produto": "", 
            "Palavras-Chave": "", 
            "Preço de Custo": 0.0, 
            "Margem (%)": 30.0,
            "Preço Referência": 0.0,
            "Fonte Referência": ""
        }]
        
    df = pd.DataFrame(data)
    
    edited_df = st.data_editor(df, num_rows="dynamic", width="stretch")
    
    if st.button("💾 Salvar Alterações"):
        salvar_produtos(edited_df)

elif page == "Buscar Licitações":
    st.header("🔍 Buscar Novas Oportunidades")
    
    # Período fixo de busca (60 dias é suficiente para capturar todos os pregões abertos)
    dias = 60

    estados = st.multiselect("Estados:", ['RN', 'PB', 'PE', 'AL', 'CE', 'BA'], default=['RN', 'PB', 'PE', 'AL'])
        
    busca_ampla = st.checkbox("🌍 Modo Varredura Total (Ignorar filtros de palavras-chave)",
                              help="Se marcado, traz TUDO o que foi publicado, sem filtrar por termos médicos. Útil para garantir que nada passou batido.")

    st.markdown("#### Fontes Extras - Diários Oficiais Municipais")
    
    # --- FEMURN (RN) ---
    col_ext1, col_ext2, col_ext3 = st.columns(3)
    with col_ext1:
        st.markdown("**Rio Grande do Norte**")
        col_chk, col_btn = st.columns([0.7, 0.3])
        with col_chk:
            use_femurn = st.checkbox("FEMURN (RN)", value=True, help="Diário Oficial dos Municípios do RN")
        with col_btn:
            if st.button("▶️", key="btn_femurn", help="Rodar apenas FEMURN"):
                client = PNCPClient()
                with st.status("Buscando no FEMURN...", expanded=True):
                    scraper = FemurnScraper()
                    res = scraper.buscar_oportunidades(client.TERMOS_POSITIVOS_PADRAO, termos_negativos=client.TERMOS_NEGATIVOS_PADRAO)
                    processar_resultados(res)

    # --- FAMUP (PB) ---
    with col_ext2:
        st.markdown("**Paraíba**")
        col_chk, col_btn = st.columns([0.7, 0.3])
        with col_chk:
            use_famup = st.checkbox("FAMUP (PB)", value=True, help="Diário Oficial dos Municípios da PB")
        with col_btn:
            if st.button("▶️", key="btn_famup", help="Rodar apenas FAMUP"):
                client = PNCPClient()
                with st.status("Buscando no FAMUP...", expanded=True):
                    scraper = FamupScraper()
                    res = scraper.buscar_oportunidades(client.TERMOS_POSITIVOS_PADRAO, termos_negativos=client.TERMOS_NEGATIVOS_PADRAO)
                    processar_resultados(res)

    # --- AMUPE (PE) ---
    with col_ext3:
        st.markdown("**Pernambuco**")
        col_chk, col_btn = st.columns([0.7, 0.3])
        with col_chk:
            use_amupe = st.checkbox("AMUPE (PE)", value=True, help="Diário Oficial dos Municípios de PE")
        with col_btn:
            if st.button("▶️", key="btn_amupe", help="Rodar apenas AMUPE"):
                client = PNCPClient()
                with st.status("Buscando no AMUPE...", expanded=True):
                    scraper = AmupeScraper()
                    res = scraper.buscar_oportunidades(client.TERMOS_POSITIVOS_PADRAO, termos_negativos=client.TERMOS_NEGATIVOS_PADRAO)
                    processar_resultados(res)

    # --- ALAGOAS ---
    st.markdown("**Alagoas**")
    col_al1, col_al2, col_al3, col_al4 = st.columns(4)
    
    with col_al1:
        col_chk, col_btn = st.columns([0.7, 0.3])
        with col_chk:
            use_ama = st.checkbox("AMA (AL)", value=True, help="Associação dos Municípios Alagoanos")
        with col_btn:
            if st.button("▶️", key="btn_ama", help="Rodar apenas AMA"):
                client = PNCPClient()
                with st.status("Buscando no AMA...", expanded=True):
                    scraper = AmaScraper()
                    res = scraper.buscar_oportunidades(client.TERMOS_POSITIVOS_PADRAO, termos_negativos=client.TERMOS_NEGATIVOS_PADRAO)
                    processar_resultados(res)

    with col_al2:
        col_chk, col_btn = st.columns([0.7, 0.3])
        with col_chk:
            use_maceio = st.checkbox("Maceió", value=True, help="Diário Oficial de Maceió")
        with col_btn:
            if st.button("▶️", key="btn_maceio", help="Rodar apenas Maceió"):
                client = PNCPClient()
                with st.status("Buscando em Maceió...", expanded=True):
                    scraper = MaceioScraper()
                    res = scraper.buscar_oportunidades(client.TERMOS_POSITIVOS_PADRAO, termos_negativos=client.TERMOS_NEGATIVOS_PADRAO)
                    processar_resultados(res)

    with col_al3:
        col_chk, col_btn = st.columns([0.7, 0.3])
        with col_chk:
            use_maceio_investe = st.checkbox("Maceió Investe", value=True, help="Diário Oficial Maceió Investe")
        with col_btn:
            if st.button("▶️", key="btn_maceio_inv", help="Rodar apenas Maceió Investe"):
                client = PNCPClient()
                with st.status("Buscando em Maceió Investe...", expanded=True):
                    scraper = MaceioInvesteScraper()
                    res = scraper.buscar_oportunidades(client.TERMOS_POSITIVOS_PADRAO, termos_negativos=client.TERMOS_NEGATIVOS_PADRAO)
                    processar_resultados(res)

    with col_al4:
        col_chk, col_btn = st.columns([0.7, 0.3])
        with col_chk:
            use_maceio_saude = st.checkbox("Maceió Saúde", value=True, help="Diário Oficial Maceió Saúde")
        with col_btn:
            if st.button("▶️", key="btn_maceio_saude", help="Rodar apenas Maceió Saúde"):
                client = PNCPClient()
                with st.status("Buscando em Maceió Saúde...", expanded=True):
                    scraper = MaceioSaudeScraper()
                    res = scraper.buscar_oportunidades(client.TERMOS_POSITIVOS_PADRAO, termos_negativos=client.TERMOS_NEGATIVOS_PADRAO)
                    processar_resultados(res)

    # Filtro de futuro agora é MANDATÓRIO
    filtro_futuro = True 

    if st.button("🚀 Iniciar Varredura Completa (PNCP + Selecionados)"):
        client = PNCPClient()
        
        # Pega termos do catálogo para filtrar a busca inicial
        session = get_session()
        prods = session.query(Produto).all()
        all_keywords = []
        for p in prods:
            all_keywords.extend([k.strip().upper() for k in p.palavras_chave.split(',')])
        all_keywords = list(set(all_keywords)) # Remove duplicatas
        session.close()
        
        # Se busca ampla, ignoramos a validação de catálogo vazio
        if not all_keywords and not busca_ampla:
            st.warning("Seu catálogo está vazio! Cadastre produtos para gerar palavras-chave de busca.")
        else:
            with st.status("Buscando no PNCP e Fontes Extras...", expanded=True) as status:
                
                if busca_ampla:
                    st.write("⚠️ MODO VARREDURA: Buscando todas as licitações (sem filtro de termos)...")
                    termos_busca = [] # Lista vazia desativa o filtro no client
                else:
                    termos_busca = client.TERMOS_POSITIVOS_PADRAO
                    st.write(f"Filtrando por {len(termos_busca)} termos (Apenas Padrão Medcal)...")
                
                # Busca PNCP
                resultados_raw = client.buscar_oportunidades(dias, estados, termos_positivos=termos_busca)
                
                # Busca Fontes Extras (se marcadas)
                if use_femurn:
                    st.write("Baixando e analisando Diário Oficial do FEMURN (PDF)...")
                    scraper_femurn = FemurnScraper()
                    res_femurn = scraper_femurn.buscar_oportunidades(client.TERMOS_POSITIVOS_PADRAO, termos_negativos=client.TERMOS_NEGATIVOS_PADRAO)
                    resultados_raw.extend(res_femurn)

                if use_famup:
                    st.write("Baixando e analisando Diário Oficial do FAMUP (PDF)...")
                    scraper_famup = FamupScraper()
                    res_famup = scraper_famup.buscar_oportunidades(client.TERMOS_POSITIVOS_PADRAO, termos_negativos=client.TERMOS_NEGATIVOS_PADRAO)
                    resultados_raw.extend(res_famup)

                if use_amupe:
                    st.write("Baixando e analisando Diário Oficial do AMUPE (PDF)...")
                    scraper_amupe = AmupeScraper()
                    res_amupe = scraper_amupe.buscar_oportunidades(client.TERMOS_POSITIVOS_PADRAO, termos_negativos=client.TERMOS_NEGATIVOS_PADRAO)
                    resultados_raw.extend(res_amupe)

                # Scrapers de Alagoas
                if use_ama:
                    st.write("Baixando e analisando Diário Oficial do AMA (PDF)...")
                    scraper_ama = AmaScraper()
                    res_ama = scraper_ama.buscar_oportunidades(client.TERMOS_POSITIVOS_PADRAO, termos_negativos=client.TERMOS_NEGATIVOS_PADRAO)
                    resultados_raw.extend(res_ama)

                if use_maceio:
                    st.write("Baixando e analisando Diário Oficial de Maceió (PDF)...")
                    scraper_maceio = MaceioScraper()
                    res_maceio = scraper_maceio.buscar_oportunidades(client.TERMOS_POSITIVOS_PADRAO, termos_negativos=client.TERMOS_NEGATIVOS_PADRAO)
                    resultados_raw.extend(res_maceio)

                if use_maceio_investe:
                    st.write("Baixando e analisando Diário Oficial de Maceió Investe (PDF)...")
                    scraper_maceio_investe = MaceioInvesteScraper()
                    res_maceio_investe = scraper_maceio_investe.buscar_oportunidades(client.TERMOS_POSITIVOS_PADRAO, termos_negativos=client.TERMOS_NEGATIVOS_PADRAO)
                    resultados_raw.extend(res_maceio_investe)

                if use_maceio_saude:
                    st.write("Baixando e analisando Diário Oficial de Maceió Saúde (PDF)...")
                    scraper_maceio_saude = MaceioSaudeScraper()
                    res_maceio_saude = scraper_maceio_saude.buscar_oportunidades(client.TERMOS_POSITIVOS_PADRAO, termos_negativos=client.TERMOS_NEGATIVOS_PADRAO)
                    resultados_raw.extend(res_maceio_saude)

                # Processa tudo junto
                processar_resultados(resultados_raw)
        
    st.divider()
    with st.expander("Limpeza do banco de dados"):
        st.warning("Isso apagará todas as licitações importadas.")
        if st.button("Limpar Histórico de Licitações"):
            session = get_session()
            session.query(ItemLicitacao).delete()
            session.query(Licitacao).delete()
            session.commit()
            session.close()
            st.success("Banco de dados limpo!")
            st.rerun()

    st.divider()
    st.subheader("Buscar por ID PNCP (debug de edital específico)")
    pncp_id_input = st.text_input("Informe o PNCP ID ou URL (ex: 08308470000129-2025-24 ou link do edital)")
    if st.button("🔍 Buscar e importar este edital"):
        client = PNCPClient()
        cnpj = ano = seq = None
        text = pncp_id_input.strip()
        if "/" in text:
            parts = text.strip().split("/")
            if len(parts) >= 3:
                cnpj, ano, seq = parts[-3], parts[-2], parts[-1]
        elif "-" in text:
            parts = text.split("-")
            if len(parts) == 3:
                cnpj, ano, seq = parts
        if not (cnpj and ano and seq):
            st.error("Formato inválido. Use CNPJ-ANO-SEQ ou URL do PNCP.")
        else:
            res = client.buscar_por_id(cnpj, ano, seq)
            if not res:
                st.error("Não foi possível buscar este edital.")
            else:
                session = get_session()
                exists = session.query(Licitacao).filter_by(pncp_id=res['pncp_id']).first()
                if exists:
                    st.info("Já está no banco.")
                else:
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
                    session.flush()
                    itens_api = client.buscar_itens(res)
                    for i in itens_api:
                        item_db = ItemLicitacao(
                            licitacao_id=lic.id,
                            numero_item=i['numero'],
                            descricao=i['descricao'],
                            quantidade=i['quantidade'],
                            unidade=i['unidade'],
                            valor_estimado=i['valor_estimado'],
                            valor_unitario=i['valor_unitario']
                        )
                        session.add(item_db)
                    match_itens(session, lic.id)
                    session.commit()
                    session.close()
                    st.success("Edital importado com sucesso! Veja no Dashboard.")

elif page == "Gestão (Kanban)":
    st.header("📋 Gestão de Licitações (Kanban)")
    
    session = get_session()
    
    # Filtros
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        filtro_uf = st.multiselect("Filtrar por UF", ['RN', 'PB', 'PE', 'AL', 'CE', 'BA'])
    with col_f2:
        filtro_texto = st.text_input("Buscar no Objeto/Órgão")
        
    query = session.query(Licitacao).filter(Licitacao.status != 'Ignorada') # Não mostra ignoradas no Kanban principal
    if filtro_uf:
        query = query.filter(Licitacao.uf.in_(filtro_uf))
    if filtro_texto:
        query = query.filter(Licitacao.objeto.ilike(f"%{filtro_texto}%") | Licitacao.orgao.ilike(f"%{filtro_texto}%"))
        
    licitacoes = query.all()
    
    # Definição das colunas do Kanban
    cols = st.columns(5)
    status_list = ["Nova", "Em Análise", "Participar", "Ganha", "Perdida"]
    status_colors = ["blue", "orange", "green", "gold", "red"]
    
    for i, status in enumerate(status_list):
        with cols[i]:
            st.markdown(f"### :{status_colors[i]}[{status}]")
            items = [l for l in licitacoes if l.status == status]
            st.write(f"Total: {len(items)}")
            
            for lic in items:
                with st.container(border=True):
                    st.markdown(f"**{lic.orgao}**")
                    st.caption(f"{lic.uf} | {lic.modalidade}")
                    if lic.data_sessao:
                        st.caption(f"📅 {lic.data_sessao.strftime('%d/%m/%Y')}")
                    
                    # Matches
                    matches = sum(1 for item in lic.itens if item.produto_match_id is not None)
                    if matches > 0:
                        st.markdown(f"🔥 **{matches} matches**")
                    
                    with st.expander("Detalhes"):
                        st.write(lic.objeto)
                        st.write(f"[Link]({lic.link})")
                        
                        # Comentários
                        comentario = st.text_area("Notas", value=lic.comentarios or "", key=f"com_{lic.id}")
                        if st.button("Salvar Nota", key=f"btn_com_{lic.id}"):
                            lic.comentarios = comentario
                            session.commit()
                            st.success("Nota salva!")
                            st.rerun()
                            
                        # Mover Status
                        novo_status = st.selectbox("Mover para:", status_list + ["Ignorada"], index=status_list.index(status) if status in status_list else 0, key=f"st_{lic.id}")
                        if novo_status != lic.status:
                            lic.status = novo_status
                            session.commit()
                            st.rerun()

    session.close()

elif page == "Dashboard":
    st.header("Painel de Controle")
    
    session = get_session()
    licitacoes_db = session.query(Licitacao).all()
    
    # Ordenação Inteligente: Primeiro por número de itens com match, depois por data (mais recente)
    licitacoes = sorted(
        licitacoes_db, 
        key=lambda x: (sum(1 for i in x.itens if i.produto_match_id is not None), x.data_sessao or datetime.min), 
        reverse=True
    )
    
    if not licitacoes:
        st.info("Nenhuma licitação no banco. Vá em 'Buscar Licitações' para começar.")
    else:
        for lic in licitacoes:
            # Contar itens com match
            total_itens = len(lic.itens)
            matches = sum(1 for i in lic.itens if i.produto_match_id is not None)
            
            # Ícone e cor baseados no match
            if matches > 0:
                icon = "🔥" # Fogo para alta prioridade
                label_match = f":green[**{matches} itens do seu catálogo!**]"
            elif lic.modalidade == "Diário Oficial" or lic.modalidade == "Portal Externo":
                icon = "📢"
                label_match = "Aviso de Edital (Verificar PDF/Link)"
            else:
                icon = "⚠️"
                label_match = f"{matches}/{total_itens} itens compatíveis"
            
            with st.expander(f"{icon} [{lic.uf}] {lic.orgao} - {label_match}"):
                st.write(f"**Objeto:** {lic.objeto}")
                st.write(f"**Sessão:** {lic.data_sessao} | **Início Proposta:** {lic.data_inicio_proposta} | **Fim Proposta:** {lic.data_encerramento_proposta}")
                st.write(f"**Link:** [Acessar PNCP]({lic.link})")
                
                # Tabela de Itens
                data_itens = []
                valor_total_proposta = 0
                
                for item in lic.itens:
                    match_nome = "❌ Sem Match"
                    custo = 0
                    preco_venda = 0
                    lucro = 0
                    preco_ref = 0
                    fonte_ref = "-"
                    v_unit_edital = item.valor_unitario if item.valor_unitario else 0
                    diff_percent = 0
                    
                    if item.produto_match:
                        match_nome = f"✅ {item.produto_match.nome}"
                        custo = item.produto_match.preco_custo
                        margem = item.produto_match.margem_minima / 100
                        preco_venda = custo * (1 + margem)
                        lucro = (preco_venda - custo) * item.quantidade
                        valor_total_proposta += preco_venda * item.quantidade
                        
                        preco_ref = item.produto_match.preco_referencia
                        fonte_ref = item.produto_match.fonte_referencia
                        
                        if v_unit_edital > 0 and custo > 0:
                            diff_percent = ((v_unit_edital - custo) / custo) * 100
                    
                    data_itens.append({
                        "Item": item.numero_item,
                        "Descrição Edital": item.descricao,
                        "Qtd": item.quantidade,
                        "Unidade": item.unidade,
                        "V. Unit. Edital": f"R$ {v_unit_edital:,.2f}",
                        "Meu Custo": f"R$ {custo:,.2f}" if custo > 0 else "-",
                        "Ref. Mercado": f"R$ {preco_ref:,.2f} ({fonte_ref})" if preco_ref > 0 else "-",
                        "Dif. Custo %": f"{diff_percent:+.1f}%" if diff_percent != 0 else "-",
                        "Match": match_nome
                    })
                    
                st.dataframe(pd.DataFrame(data_itens), width="stretch")
                
                col_a, col_b = st.columns(2)
                with col_a:
                    if matches > 0:
                        st.metric("Valor Total da Proposta (Itens com Match)", f"R$ {valor_total_proposta:,.2f}")
                    else:
                        st.warning("Nenhum item deste edital corresponde aos produtos do seu catálogo.")
                
                with col_b:
                    if st.button("📄 Ver Arquivos do Edital", key=f"btn_arq_{lic.id}"):
                        client = PNCPClient()
                        # Reconstrói dict mínimo para buscar arquivos
                        lic_dict = {
                            "cnpj": lic.pncp_id.split('-')[0],
                            "ano": lic.pncp_id.split('-')[1],
                            "seq": lic.pncp_id.split('-')[2]
                        }
                        arquivos = client.buscar_arquivos(lic_dict)
                        
                        if arquivos:
                            st.write("**Arquivos Disponíveis:**")
                            for arq in arquivos:
                                st.markdown(f"- [{arq['titulo']}]({arq['url']})")
                        else:
                            st.info("Nenhum arquivo encontrado.")
                            
                    st.divider()
                    st.markdown("### 🧠 Inteligência Artificial")
                    
                    # Seletor de Item para Estimativa
                    item_opts = {f"{i.numero_item} - {i.descricao[:50]}...": i.descricao for i in lic.itens}
                    selected_item_label = st.selectbox("Selecione um item para estimar preço de mercado:", list(item_opts.keys()), key=f"sel_item_{lic.id}")
                    
                    if st.button("💰 Estimar Preço de Mercado (Google/IA)", key=f"btn_price_{lic.id}"):
                        item_desc = item_opts[selected_item_label]
                        with st.spinner(f"Pesquisando preço de mercado para: {item_desc[:30]}..."):
                            estimate = get_google_price_estimate(item_desc)
                            st.info(f"**Estimativa de Preço:** {estimate}")
                            st.caption("Nota: Esta é uma estimativa baseada em IA e dados históricos. Sempre verifique fornecedores reais.")
                            
                    # Botão de IA
                    if st.button("✨ Gerar Resumo IA", key=f"btn_ai_{lic.id}"):
                        session = get_session()
                        api_key = session.query(Configuracao).filter_by(chave='gemini_api_key').first()
                        session.close()
                        
                        if api_key and api_key.valor:
                            configure_genai(api_key.valor)
                            with st.spinner("A IA está analisando o edital..."):
                                resumo = summarize_bidding(lic, lic.itens)
                                st.markdown("### 🤖 Análise da IA")
                                st.markdown(resumo)
                        else:
                            st.error("Configure a API Key do Gemini na aba Configurações primeiro!")
                            
                    # Botão de Estimativa de Preço (Novo)
                    if st.button("💰 Estimar Preços de Mercado (IA)", key=f"btn_price_all_{lic.id}"):
                        session = get_session()
                        api_key = session.query(Configuracao).filter_by(chave='gemini_api_key').first()
                        session.close()
                        
                        if api_key and api_key.valor:
                            configure_genai(api_key.valor)
                            st.write("### 💰 Estimativas de Mercado (IA)")
                            
                            # Estima apenas para os primeiros 5 itens para não demorar muito
                            itens_para_estimar = lic.itens[:5]
                            
                            for item in itens_para_estimar:
                                with st.spinner(f"Estimando: {item.descricao[:30]}..."):
                                    estimativa = estimate_market_price(item.descricao)
                                    st.markdown(f"**{item.descricao}**: {estimativa}")
                            
                            if len(lic.itens) > 5:
                                st.info("Estimativa limitada aos 5 primeiros itens para economizar tempo.")
                        else:
                            st.error("Configure a API Key do Gemini na aba Configurações primeiro!")

elif page == "Configurações":
    st.header("⚙️ Configurações do Sistema")
    
    session = get_session()
    config_termos = session.query(Configuracao).filter_by(chave='termos_busca_padrao').first()
    
    if not config_termos:
        st.error("Configuração de termos não encontrada! Rode o script de migração.")
    else:
        # --- Seção 1: Gerenciador de Termos ---
        st.subheader("📝 Termos de Busca Padrão (Global)")
        st.info("Esses termos são usados para encontrar editais que podem ter descrições genéricas (ex: 'Material Hospitalar'). O sistema baixa esses editais e procura seus produtos dentro deles.")
        
        termos_atuais = config_termos.valor
        novos_termos = st.text_area("Lista de Termos (separados por vírgula)", value=termos_atuais, height=150)
        
        if st.button("Salvar Termos"):
            config_termos.valor = novos_termos
            session.commit()
            st.success("Termos de busca atualizados com sucesso!")
            st.rerun()
            
        st.divider()
        
        # --- Seção 2: Configuração IA (Gemini) ---
        st.subheader("🤖 Configuração da IA (Gemini)")
        st.markdown("Configure sua chave de API do Google Gemini para ativar resumos automáticos e estimativas de preço.")
        
        config_api_key = session.query(Configuracao).filter_by(chave='gemini_api_key').first()
        if not config_api_key:
            config_api_key = Configuracao(chave='gemini_api_key', valor='')
            session.add(config_api_key)
            session.commit()
            
        nova_key = st.text_input("Gemini API Key", value=config_api_key.valor, type="password")
        if st.button("Salvar API Key"):
            config_api_key.valor = nova_key
            session.commit()
            st.success("API Key salva com sucesso!")
            
        st.divider()
        

            

        
        # --- Seção 2: Importador CNAE ---
        st.subheader("🏭 Gerador de Keywords via CNAE")
        st.markdown("Digite o código CNAE da sua empresa para adicionar automaticamente termos técnicos relevantes à sua lista de busca.")
        
        cnae_input = st.text_input("Código CNAE (ex: 4645-1/01)", placeholder="0000-0/00")
        
        if st.button("Gerar e Adicionar Termos"):
            from cnae_data import get_keywords_by_cnae
            
            keywords_cnae = get_keywords_by_cnae(cnae_input)
            
            if keywords_cnae:
                # Lógica de Merge
                lista_atual = [t.strip() for t in termos_atuais.split(',')]
                adicionados = []
                
                for kw in keywords_cnae:
                    if kw not in lista_atual:
                        lista_atual.append(kw)
                        adicionados.append(kw)
                
                if adicionados:
                    config_termos.valor = ", ".join(lista_atual)
                    session.commit()
                    st.success(f"✅ {len(adicionados)} novos termos adicionados: {', '.join(adicionados)}")
                    st.rerun()
                else:
                    st.warning("Todos os termos desse CNAE já estão na sua lista!")
            else:
                st.error("CNAE não encontrado ou sem keywords mapeadas. Tente outro código.")

        st.divider()
        
        # --- Seção 4: Notificações WhatsApp ---
        st.subheader("🔔 Notificações WhatsApp (CallMeBot)")
        st.markdown("""
        Configure o envio de alertas via WhatsApp usando a API gratuita do CallMeBot.
        
        **Como configurar:**
        1. Adicione o número **+34 644 56 55 18** aos seus contatos do WhatsApp.
        2. Envie a mensagem: `I allow callmebot to send me messages`
        3. Você receberá uma **API Key**. Insira abaixo.
        """)
        
        conf_wpp_phone = session.query(Configuracao).filter_by(chave='whatsapp_phone').first()
        conf_wpp_key = session.query(Configuracao).filter_by(chave='whatsapp_apikey').first()
        
        if not conf_wpp_phone:
            conf_wpp_phone = Configuracao(chave='whatsapp_phone', valor='')
            session.add(conf_wpp_phone)
        if not conf_wpp_key:
            conf_wpp_key = Configuracao(chave='whatsapp_apikey', valor='')
            session.add(conf_wpp_key)
            
        col_wpp1, col_wpp2 = st.columns(2)
        with col_wpp1:
            new_wpp_phone = st.text_input("Seu Número (com DDI e DDD)", value=conf_wpp_phone.valor, placeholder="5584999999999")
        with col_wpp2:
            new_wpp_key = st.text_input("API Key (CallMeBot)", value=conf_wpp_key.valor, type="password")
            
        if st.button("Salvar WhatsApp"):
            conf_wpp_phone.valor = new_wpp_phone
            conf_wpp_key.valor = new_wpp_key
            session.commit()
            st.success("Configurações de WhatsApp salvas!")
            
        if st.button("📨 Testar Envio de Mensagem"):
            if not new_wpp_phone or not new_wpp_key:
                st.error("Preencha o número e a API Key antes de testar.")
            else:
                notifier = WhatsAppNotifier(new_wpp_phone, new_wpp_key)
                if notifier.enviar_mensagem("✅ Teste do Sistema de Licitações Medcal! O sistema de notificações está funcionando."):
                    st.success("Mensagem enviada com sucesso! Verifique seu WhatsApp.")
                else:
                    st.error("Falha ao enviar mensagem. Verifique o número e a API Key.")
    
    session.close()
            
    session.close()

elif page == "📥 Importar & Relatórios":
    st.header("📥 Central de Importação e Relatórios")
    st.info("Importe planilhas do ConLicitação, Portal de Compras Públicas ou qualquer Excel/CSV para analisar automaticamente.")
    
    from importer import load_data, smart_map_columns, normalize_imported_data
    from database import Produto
    
    uploaded_file = st.file_uploader("Carregar Arquivo (Excel ou CSV)", type=['xlsx', 'xls', 'csv'])
    
    if uploaded_file:
        df = load_data(uploaded_file)
        
        if df is not None:
            st.write("### 1. Pré-visualização dos Dados")
            st.dataframe(df.head())
            
            st.write("### 2. Mapeamento de Colunas")
            mapping = smart_map_columns(df)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                mapping["descricao"] = st.selectbox("Coluna de Descrição/Objeto", df.columns, index=df.columns.get_loc(mapping["descricao"]) if mapping["descricao"] in df.columns else 0)
                mapping["quantidade"] = st.selectbox("Coluna de Quantidade", df.columns, index=df.columns.get_loc(mapping["quantidade"]) if mapping["quantidade"] in df.columns else 0)
            with col2:
                mapping["valor_unitario"] = st.selectbox("Coluna de Valor Unitário (Estimado)", df.columns, index=df.columns.get_loc(mapping["valor_unitario"]) if mapping["valor_unitario"] in df.columns else 0)
                mapping["unidade"] = st.selectbox("Coluna de Unidade", df.columns, index=df.columns.get_loc(mapping["unidade"]) if mapping["unidade"] in df.columns else 0)
            with col3:
                mapping["orgao"] = st.selectbox("Coluna de Órgão/Comprador", df.columns, index=df.columns.get_loc(mapping["orgao"]) if mapping["orgao"] in df.columns else 0)
                mapping["numero_edital"] = st.selectbox("Coluna de Nº Edital", df.columns, index=df.columns.get_loc(mapping["numero_edital"]) if mapping["numero_edital"] in df.columns else 0)
                
            if st.button("✅ Confirmar e Analisar"):
                st.write("### 3. Resultado da Análise")
                
                # Normaliza
                df_norm = normalize_imported_data(df, mapping)
                
                # Busca Produtos do Banco para Match
                session = get_session()
                produtos = session.query(Produto).all()
                
                matches = []
                
                progress_bar = st.progress(0)
                total_items = len(df_norm)
                
                for idx, row in df_norm.iterrows():
                    item_desc = str(row['descricao']).upper()
                    melhor_match = None
                    
                    # Lógica de Match (Cópia simplificada do match_itens)
                    for prod in produtos:
                        keywords = [k.strip().upper() for k in prod.palavras_chave.split(',')]
                        if any(k in item_desc for k in keywords):
                            melhor_match = prod
                            break
                    
                    if melhor_match:
                        lucro_bruto = (row['valor_unitario'] - melhor_match.preco_custo) * row['quantidade']
                        margem = ((row['valor_unitario'] - melhor_match.preco_custo) / row['valor_unitario']) * 100 if row['valor_unitario'] > 0 else 0
                        
                        matches.append({
                            "Edital": row['numero_edital'],
                            "Órgão": row['orgao'],
                            "Item Edital": row['descricao'],
                            "Qtd": row['quantidade'],
                            "Valor Edital (Unit)": row['valor_unitario'],
                            "Meu Produto": melhor_match.nome,
                            "Meu Custo": melhor_match.preco_custo,
                            "Lucro Potencial": lucro_bruto,
                            "Margem (%)": margem
                        })
                    
                    progress_bar.progress((idx + 1) / total_items)
                
                session.close()
                
                if matches:
                    df_matches = pd.DataFrame(matches)
                    st.success(f"Encontradas {len(matches)} oportunidades compatíveis com seu catálogo!")
                    
                    # Formatação para exibição
                    st.dataframe(
                        df_matches.style.format({
                            "Valor Edital (Unit)": "R$ {:.2f}",
                            "Meu Custo": "R$ {:.2f}",
                            "Lucro Potencial": "R$ {:.2f}",
                            "Margem (%)": "{:.1f}%"
                        })
                    )
                    
                    # Botão de Exportar Relatório
                    # CSV por enquanto para ser rápido, Excel requer mais libs/io bytes
                    csv = df_matches.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Baixar Relatório (CSV)",
                        data=csv,
                        file_name='relatorio_oportunidades.csv',
                        mime='text/csv',
                    )
                else:
                    st.warning("Nenhum item da planilha correspondeu aos produtos do seu catálogo.")
        else:
            st.error("Formato de arquivo não suportado ou arquivo vazio.")
