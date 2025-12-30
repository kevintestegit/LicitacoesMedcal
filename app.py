import streamlit as st
from components.config import init_page_config
from components.sidebar import render_sidebar

# Configuração global da página
init_page_config(page_title="Medcal Licitações")

# Renderiza a sidebar compartilhada
render_sidebar()

# Conteúdo da página inicial (Home)
st.title("🚀 Bem-vindo ao Sistema de busca por Licitações da Medcal")

st.markdown("""
### Sistema de Gestão de Licitações

Use o menu lateral para navegar entre as funcionalidades:

*   **📊 Dashboard**: Visualize e fixe licitações interessantes.
*   **🔍 Buscar**: Procure novas oportunidades no PNCP e outros portais.
*   **🎯 Preparar**: Realize análise profunda de editais fixados.
*   **🧠 Análise IA**: Use nossa IA para analisar viabilidade de qualquer edital.
*   **📦 Catálogo**: Gerencie seus produtos e palavras-chave.
*   **💰 Financeiro**: Gestão completa de extratos e finanças.
*   **⚙️ Config**: Ajuste chaves de API e notificações.

---
*Versão 2.3*
""")

# Métricas rápidas (Opcional)
col1, col2, col3 = st.columns(3)
with col1:
    st.info("Páginas separadas para maior velocidade")
with col2:
    st.success("Lógica modular e organizada")
with col3:
    st.warning("Busca em background ativa")
