import streamlit as st
import time
from datetime import datetime
from components.config import init_page_config
from components.sidebar import render_sidebar
from modules.database.database import get_session, Licitacao
from modules.core.deep_analyzer import deep_analyzer

# Configuração da página e CSS
init_page_config(page_title="Medcal - Preparar Competição")

# Renderiza sidebar
render_sidebar()

st.header("🎯 Preparar para Competir")
st.info("Selecione licitações **fixadas** (⭐) para análise profunda. A IA lerá todos os anexos e preparará um relatório completo.")

session = get_session()
licitacoes_salvas = session.query(Licitacao).filter_by(status='Salva').order_by(Licitacao.data_sessao.asc()).all()

if not licitacoes_salvas:
    st.warning("Nenhuma licitação fixada. Vá ao Dashboard e clique em ⭐ Fixar nas licitações de interesse.")
else:
    st.success(f"📌 {len(licitacoes_salvas)} licitações fixadas para análise")
    
    for lic in licitacoes_salvas:
        cached_analysis = deep_analyzer.get_cached_analysis(lic.id)
        
        with st.expander(f"{'✅' if cached_analysis else '⏳'} {lic.orgao} ({lic.uf}) - {lic.modalidade}", expanded=False):
            col_info, col_action = st.columns([3, 1])
            
            with col_info:
                st.markdown(f"**Objeto:** {lic.objeto[:200]}...")
                if lic.data_encerramento_proposta:
                    dias = (lic.data_encerramento_proposta - datetime.now()).days
                    st.markdown(f"⏰ **Prazo:** {lic.data_encerramento_proposta.strftime('%d/%m/%Y')} ({dias} dias)")
                st.markdown(f"🔗 [Abrir no Portal]({lic.link})")
            
            with col_action:
                if cached_analysis:
                    st.markdown(f"**Score:** {cached_analysis.score_viabilidade}/100")
                    st.markdown(f"**Recomendação:** {cached_analysis.recomendacao_final}")
            
            # Botões de análise
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if st.button("🔍 Analisar Profundamente", key=f"analyze_{lic.id}", type="primary"):
                    with st.spinner("🤖 Baixando anexos e analisando com IA..."):
                        result = deep_analyzer.analyze(lic.id, force_refresh=True)
                        if result:
                            st.success("✅ Análise concluída!")
                            st.rerun()
            
            if cached_analysis:
                with col_btn2:
                    if st.button("🔄 Refazer Análise", key=f"refresh_{lic.id}"):
                        deep_analyzer.analyze(lic.id, force_refresh=True)
                        st.rerun()
                
                # Exibição resumida dos resultados da análise
                st.divider()
                st.markdown(f"**Justificativa:** {cached_analysis.justificativa}")
                
                tab1, tab2, tab3 = st.tabs(["📋 Detalhes", "🚫 Riscos/Impedimentos", "📄 Documentos"])
                with tab1:
                    st.markdown(f"**Valor Estimado:** R$ {cached_analysis.valor_total_estimado:,.2f}")
                    st.markdown(f"**Critérios:** {cached_analysis.resumo_objeto}")
                with tab2:
                    for imp in cached_analysis.impedimentos:
                        st.error(f"❌ {imp}")
                    for risco in cached_analysis.riscos:
                        st.warning(f"⚠️ {risco}")
                with tab3:
                    for doc in cached_analysis.documentos_necessarios:
                        st.checkbox(doc, key=f"doc_{lic.id}_{hash(doc)}")

session.close()
