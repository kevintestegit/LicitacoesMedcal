import streamlit as st
import os

def init_page_config(page_title="Medcal Licitações"):
    st.set_page_config(
        page_title=page_title,
        page_icon=" ",  # Ícone em branco para ocultar o padrão
        layout="wide",
        initial_sidebar_state="expanded"
    )
    inject_custom_css()
    hide_streamlit_elements()

def inject_custom_css():
    css_path = "assets/style.css"
    if os.path.exists(css_path):
        with open(css_path) as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

def hide_streamlit_elements():
    """Oculta ícones do header e remove TODAS as animações"""
    st.markdown("""
        <style>
        /* Oculta ícones do header (favicon, etc) */
        header[data-testid="stHeader"] {
            background: transparent !important;
        }
        header[data-testid="stHeader"] img,
        header[data-testid="stHeader"] svg,
        [data-testid="stDecoration"],
        .stDeployButton,
        #MainMenu {
            display: none !important;
            visibility: hidden !important;
        }
        
        /* REMOVE ABSOLUTAMENTE TODAS AS ANIMAÇÕES E TRANSIÇÕES */
        *, *::before, *::after {
            animation: none !important;
            animation-duration: 0s !important;
            animation-delay: 0s !important;
            transition: none !important;
            transition-duration: 0s !important;
            transition-delay: 0s !important;
        }
        
        /* Remove todas as keyframes do Streamlit */
        @keyframes fadeIn { from { opacity: 1; } to { opacity: 1; } }
        @keyframes fadeOut { from { opacity: 1; } to { opacity: 1; } }
        @keyframes slideIn { from { transform: none; } to { transform: none; } }
        @keyframes slideOut { from { transform: none; } to { transform: none; } }
        
        /* Força elementos a aparecerem instantaneamente */
        .stApp, .main, [data-testid="stAppViewContainer"],
        [data-testid="stSidebar"], .block-container,
        .element-container, .stMarkdown, .stButton,
        [data-testid="column"], section[data-testid="stSidebar"] > div {
            opacity: 1 !important;
            transform: none !important;
            visibility: visible !important;
        }
        
        /* Barra de loading estática (sem animação) no topo - apenas muda cor */
        .stSpinner {
            position: fixed !important;
            top: 0 !important;
            left: 0 !important;
            right: 0 !important;
            z-index: 9999 !important;
            height: 3px !important;
            background: #4CAF50 !important;
        }
        
        .stSpinner > div {
            display: none !important;
        }
        </style>
    """, unsafe_allow_html=True)

def normalize_text(texto: str) -> str:
    import unicodedata
    if not texto:
        return ""
    return unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('ASCII').upper()


