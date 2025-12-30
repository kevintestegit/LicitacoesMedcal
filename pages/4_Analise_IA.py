import streamlit as st
from components.config import init_page_config
from components.sidebar import render_sidebar
from modules.database.database import get_session, Licitacao
from modules.ai.smart_analyzer import SmartAnalyzer
from modules.ai.eligibility_checker import EligibilityChecker
from modules.scrapers.pncp_client import PNCPClient
from modules.ai.improved_matcher import SemanticMatcher

# Configuração da página e CSS
init_page_config(page_title="Medcal - Análise IA")

# Renderiza sidebar
render_sidebar()

st.header("🧠 Análise Inteligente de Licitações")
st.info("Use a Inteligência Artificial para analisar a viabilidade, riscos e elegibilidade dos editais.")

session = get_session()
# Lista licitações para análise (apenas as que não foram ignoradas/perdidas)
licitacoes = session.query(Licitacao).filter(Licitacao.status.in_(['Nova', 'Em Análise', 'Participar', 'Salva'])).order_by(Licitacao.data_publicacao.desc()).all()

if not licitacoes:
    st.warning("Nenhuma licitação disponível para análise.")
else:
    lic_dict = {f"{l.id} - {l.orgao} ({l.modalidade})": l for l in licitacoes}
    selected_lic_key = st.selectbox("Selecione uma Licitação para Analisar:", list(lic_dict.keys()))
    
    if selected_lic_key:
        lic = lic_dict[selected_lic_key]
        
        # Exibe detalhes básicos
        with st.expander("Detalhes da Licitação", expanded=False):
            st.write(f"**Objeto:** {lic.objeto}")
            st.write(f"**Link:** {lic.link}")
            st.write(f"**Data:** {lic.data_publicacao}")
        
        if st.button("🤖 Gerar Análise Completa (IA)"):
            with st.spinner("A IA está lendo o edital e analisando viabilidade..."):
                analyzer = SmartAnalyzer()
                eligibility = EligibilityChecker()
                client = PNCPClient()
                
                # 1. Análise do Texto
                texto_analise = f"OBJETO: {lic.objeto}\n\nITENS:\n"
                for item in lic.itens:
                    texto_analise += f"- {item.quantidade} {item.unidade} de {item.descricao}\n"
                
                # --- LEITURA PROFUNDA (Opcional, se PNCP) ---
                if lic.pncp_id and len(lic.pncp_id.split('-')) == 3:
                    try:
                        cnpj, ano, seq = lic.pncp_id.split('-')
                        lic_info = {"cnpj": cnpj, "ano": ano, "seq": seq}
                        arquivos = client.buscar_arquivos(lic_info)
                        
                        pdf_url = None
                        for arq in arquivos:
                            nome_lower = (arq.get('titulo') or "").lower() + (arq.get('nome') or "").lower()
                            if "edital" in nome_lower or "termo de referencia" in nome_lower or "termo de referência" in nome_lower:
                                if arq.get('url') and arq['url'].lower().endswith('.pdf'):
                                    pdf_url = arq['url']
                                    break
                        
                        if pdf_url:
                            st.toast("Baixando anexo para análise profunda...", icon="📥")
                            pdf_content = client.download_arquivo(pdf_url)
                            if pdf_content:
                                import io
                                from pypdf import PdfReader
                                try:
                                    reader = PdfReader(io.BytesIO(pdf_content))
                                    texto_pdf = ""
                                    for page in reader.pages[:10]: # Limita a 10 páginas para não estourar context window
                                        texto_pdf += page.extract_text() + "\n"
                                    if texto_pdf:
                                        texto_analise += f"\n\n--- CONTEÚDO EXTRAÍDO DO EDITAL ---\n{texto_pdf[:30000]}"
                                except: pass
                    except: pass

                analise = analyzer.analisar_viabilidade(texto_analise)
                
                # 2. Verificação de Elegibilidade
                elegibilidade = eligibility.check_eligibility({
                    "uf": lic.uf,
                    "modalidade": lic.modalidade
                }, ai_analysis=analise)
                
                # --- EXIBIÇÃO DOS RESULTADOS ---
                st.divider()
                
                if analise.get('erro'):
                    st.error(f"❌ {analise.get('erro')}")
                else:
                    st.subheader(f"Score de Viabilidade: {analise.get('score_viabilidade', 0)}/100")
                    st.write(analise.get('resumo_objeto', ''))
                    st.info(f"Justificativa: {analise.get('justificativa_score', '')}")

                # Elegibilidade
                if elegibilidade['eligible']:
                    st.success("✅ Empresa Elegível para participar")
                else:
                    st.error("🚫 Empresa INELEGÍVEL")
                    for reason in elegibilidade['reasons']:
                        st.write(f"- {reason}")
                
                # Riscos e Pontos de Atenção
                col_red, col_att = st.columns(2)
                with col_red:
                    st.markdown("### 🚩 Riscos")
                    for flag in analise.get('red_flags', []):
                        st.markdown(f"- {flag}")
                with col_att:
                    st.markdown("### ⚠️ Pontos de Atenção")
                    for point in analise.get('pontos_atencao', []):
                        st.markdown(f"- {point}")

session.close()
