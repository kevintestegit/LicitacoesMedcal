import streamlit as st
import pandas as pd
from components.config import init_page_config
from components.sidebar import render_sidebar
from components.utils import salvar_produtos
from modules.database.database import get_session, Produto

# Configuração da página e CSS
init_page_config(page_title="Medcal - Catálogo")

# Renderiza sidebar
render_sidebar()

st.header("📦 Catálogo de Produtos")
st.info("Cadastro dos produtos. O sistema usará as 'Palavras-Chave' para encontrar as Licitações.")

session = get_session()
produtos = session.query(Produto).all()
session.close()

data = []
for p in produtos:
    data.append({
        "nome": p.nome or "",
        "palavras_chave": p.palavras_chave or "",
        "preco_custo": float(p.preco_custo or 0.0),
        "margem_minima": float(p.margem_minima or 30.0),
        "preco_referencia": float(p.preco_referencia or 0.0),
        "fonte_referencia": p.fonte_referencia or ""
    })

if not data:
    data = [{
        "nome": "", 
        "palavras_chave": "", 
        "preco_custo": 0.0, 
        "margem_minima": 30.0,
        "preco_referencia": 0.0,
        "fonte_referencia": ""
    }]
    
df = pd.DataFrame(data)

# Configuração explícita das colunas
edited_df = st.data_editor(
    df,
    column_config={
        "nome": st.column_config.TextColumn("Nome do Produto", required=True, width="medium"),
        "palavras_chave": st.column_config.TextColumn("Palavras-Chave", help="Separadas por vírgula", width="medium"),
        "preco_custo": st.column_config.NumberColumn("Preço de Custo", min_value=0.0, format="R$ %.2f", required=True, width="small"),
        "margem_minima": st.column_config.NumberColumn("Margem (%)", min_value=0.0, format="%.1f%%", width="small"),
        "preco_referencia": st.column_config.NumberColumn("Preço Referência", min_value=0.0, format="R$ %.2f", width="small"),
        "fonte_referencia": st.column_config.TextColumn("Fonte Referência", width="small")
    },
    num_rows="dynamic",
    width='stretch',
    key="editor_catalogo_page"
)

if st.button("💾 Salvar Alterações", key="btn_salvar_catalogo_page"):
    # Renomeia colunas para compatibilidade
    df_to_save = edited_df.rename(columns={
        "nome": "Nome do Produto",
        "palavras_chave": "Palavras-Chave",
        "preco_custo": "Preço de Custo",
        "margem_minima": "Margem (%)",
        "preco_referencia": "Preço Referência",
        "fonte_referencia": "Fonte Referência"
    })
    salvar_produtos(df_to_save)
