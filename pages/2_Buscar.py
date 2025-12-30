import streamlit as st
import time
from components.config import init_page_config
from components.sidebar import render_sidebar
from components.utils import match_itens
from modules.database.database import get_session, Licitacao, Configuracao
from modules.scrapers.pncp_client import PNCPClient
from modules.scrapers.external_scrapers import (
    FemurnScraper, FamupScraper, AmupeScraper, AmaScraper, 
    MaceioScraper, MaceioInvesteScraper, MaceioSaudeScraper
)
from modules.core.opportunity_collector import prepare_results_for_pipeline
from modules.core.search_engine import SearchEngine
from modules.core.background_search import background_manager

# Configuração da página e CSS
init_page_config(page_title="Medcal - Buscar Licitações")

# Renderiza sidebar
render_sidebar()

def processar_resultados(resultados_raw, notificar=False, fonte_nome=""):
    if not resultados_raw:
        st.warning("Nenhum resultado encontrado para processar.")
        return
    
    # Notificação imediata (opcional, simplificada para a página)
    st.info(f"Processando {len(resultados_raw)} resultados de {fonte_nome}...")
    
    resultados_preparados = prepare_results_for_pipeline(resultados_raw)
    engine = SearchEngine()
    details = engine.run_search_pipeline(resultados_preparados, return_details=True, send_immediate_alerts=notificar)
    novos = int((details or {}).get("novos") or 0)
    st.success(f"Busca finalizada! {novos} novas licitações importadas de {fonte_nome}.")

st.header("🔍 Buscar Novas Oportunidades")

# Grid de Scrapers
st.markdown("#### 📰 Portais e Diários Oficiais")
col_ext1, col_ext2, col_ext3 = st.columns(3)

# PNCP
with col_ext1:
    with st.container(border=True):
        st.markdown("**🏛️ PNCP**")
        if st.button("▶️ Buscar PNCP", key="btn_pncp"):
            with st.status("Buscando no PNCP...") as status:
                client = PNCPClient()
                # Busca simplificada para teste
                res = client.buscar_oportunidades(dias_atras=2)
                processar_resultados(res, notificar=True, fonte_nome="PNCP")
                status.update(label="Busca PNCP concluída!", state="complete")

# FEMURN (RN)
with col_ext2:
    with st.container(border=True):
        st.markdown("**📰 FEMURN (RN)**")
        if st.button("▶️ Buscar FEMURN", key="btn_femurn"):
            with st.status("Buscando no FEMURN...") as status:
                scraper = FemurnScraper()
                client = PNCPClient()
                res = scraper.buscar_oportunidades(client.TERMOS_PRIORITARIOS, termos_negativos=client.TERMOS_NEGATIVOS_PADRAO)
                processar_resultados(res, notificar=True, fonte_nome="FEMURN")
                status.update(label="Busca FEMURN concluída!", state="complete")

# FAMUP (PB)
with col_ext3:
    with st.container(border=True):
        st.markdown("**📰 FAMUP (PB)**")
        if st.button("▶️ Buscar FAMUP", key="btn_famup"):
            with st.status("Buscando no FAMUP...") as status:
                scraper = FamupScraper()
                client = PNCPClient()
                res = scraper.buscar_oportunidades(client.TERMOS_PRIORITARIOS, termos_negativos=client.TERMOS_NEGATIVOS_PADRAO)
                processar_resultados(res, notificar=True, fonte_nome="FAMUP")
                status.update(label="Busca FAMUP concluída!", state="complete")

st.divider()

# Busca em Background
st.markdown("#### 🚀 Busca em Segundo Plano")
try:
    search_status = background_manager.get_current_status()
except Exception:
    search_status = {'status': 'idle'}

if search_status.get('status') == 'running':
    st.info(f"🔄 **Busca em andamento...**\n{search_status.get('message', '')}")
else:
    if st.button("🚀 Iniciar Busca Completa (Todas as Fontes)", type="primary"):
        st.info("Iniciando busca em background...")
        # background_manager.start_search(['pncp', 'femurn', 'famup', 'amupe', 'ama', 'maceio'])

st.divider()
with st.expander("Limpeza do banco de dados"):
    st.warning("Isso apagará todas as licitações NÃO SALVAS (que não foram fixadas).")
    if st.button("Limpar Histórico de Licitações"):
        session = get_session()
        deleted = session.query(Licitacao).filter(Licitacao.status != 'Salva').delete()
        session.commit()
        st.success(f"✅ {deleted} licitações removidas do histórico.")
        session.close()
        time.sleep(1)
        st.rerun()
