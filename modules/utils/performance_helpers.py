"""
Funções Otimizadas de Performance
Substitui funções lentas do dashboard por versões otimizadas
"""

import pandas as pd
import streamlit as st
from modules.database.database import get_session, Produto
from functools import lru_cache
import hashlib


def salvar_produtos_otimizado(df_editor):
    """
    Versão otimizada de salvar_produtos()
    Usa bulk insert ao invés de iterrows
    """
    session = get_session()
    session.query(Produto).delete()

    # Converte DataFrame para lista de objetos usando list comprehension
    # Muito mais rápido que iterrows()
    produtos = []
    for row in df_editor.itertuples(index=False):
        if row[0]:  # Nome do Produto (primeiro campo)
            produtos.append(
                Produto(
                    nome=row[0],
                    palavras_chave=row[1],
                    preco_custo=float(row[2]),
                    margem_minima=float(row[3]),
                    preco_referencia=float(row[4] if len(row) > 4 else 0.0),
                    fonte_referencia=str(row[5] if len(row) > 5 else "")
                )
            )

    # Bulk insert é MUITO mais rápido
    session.bulk_save_objects(produtos)
    session.commit()
    session.close()

    return len(produtos)


@st.cache_data(ttl=300)
def load_licitacoes_cached(status=None, limit=100, offset=0):
    """
    Carrega licitações com cache de 5 minutos
    """
    session = get_session()
    query = session.query(Licitacao)

    if status:
        query = query.filter(Licitacao.status == status)

    query = query.order_by(Licitacao.data_captura.desc())
    query = query.offset(offset).limit(limit)

    # Converte para dicts para poder cachear
    licitacoes = query.all()
    result = [
        {
            'id': lic.id,
            'pncp_id': lic.pncp_id,
            'orgao': lic.orgao,
            'uf': lic.uf,
            'modalidade': lic.modalidade,
            'objeto': lic.objeto,
            'status': lic.status,
            'data_captura': lic.data_captura
        }
        for lic in licitacoes
    ]
    session.close()

    return result


@st.cache_data(ttl=600)
def load_produtos_cached():
    """Carrega produtos com cache de 10 minutos"""
    session = get_session()
    produtos = session.query(Produto).all()

    result = [
        {
            'id': p.id,
            'nome': p.nome,
            'palavras_chave': p.palavras_chave,
            'preco_custo': p.preco_custo,
            'margem_minima': p.margem_minima,
            'preco_referencia': p.preco_referencia,
            'fonte_referencia': p.fonte_referencia
        }
        for p in produtos
    ]
    session.close()

    return result


def paginate_dataframe(df, page_size=50, key="pagination"):
    """
    Pagina um DataFrame para melhor performance no Streamlit
    """
    total_rows = len(df)
    total_pages = (total_rows // page_size) + (1 if total_rows % page_size > 0 else 0)

    if total_pages == 0:
        return df

    col1, col2, col3 = st.columns([2, 3, 2])

    with col2:
        page = st.number_input(
            f'Página (total: {total_pages})',
            min_value=1,
            max_value=max(1, total_pages),
            value=1,
            key=f"{key}_page"
        )

    start_idx = (page - 1) * page_size
    end_idx = min(start_idx + page_size, total_rows)

    with col1:
        st.info(f"Mostrando {start_idx+1}-{end_idx} de {total_rows}")

    with col3:
        page_size_select = st.selectbox(
            "Linhas por página",
            options=[25, 50, 100, 200],
            index=1,
            key=f"{key}_pagesize"
        )

    return df.iloc[start_idx:end_idx]


@lru_cache(maxsize=500)
def cached_text_match(text_hash, keyword_hash):
    """
    Cache de matching de texto
    Evita recalcular matches repetidos
    """
    # Esta é apenas a estrutura - a lógica real de matching
    # deve ser implementada aqui
    return 0, ""


def processar_dataframe_otimizado(df, coluna_origem, coluna_destino, funcao_transformacao):
    """
    Processa DataFrame usando operações vetorizadas ao invés de iterrows

    Exemplo de uso:
        # Ao invés de:
        for idx, row in df.iterrows():
            df.at[idx, 'nova_col'] = funcao(row['col'])

        # Use:
        df = processar_dataframe_otimizado(df, 'col', 'nova_col', funcao)
    """
    df[coluna_destino] = df[coluna_origem].apply(funcao_transformacao)
    return df


def bulk_update_database(session, model, updates):
    """
    Atualiza múltiplos registros de uma vez

    Args:
        session: SQLAlchemy session
        model: Modelo do SQLAlchemy
        updates: Lista de dicts com 'id' e campos a atualizar

    Exemplo:
        updates = [
            {'id': 1, 'status': 'Aprovado', 'valor': 100},
            {'id': 2, 'status': 'Rejeitado', 'valor': 200}
        ]
        bulk_update_database(session, Licitacao, updates)
    """
    session.bulk_update_mappings(model, updates)
    session.commit()


# Configuração do Streamlit para melhor performance
def configure_streamlit_performance():
    """Aplica configurações otimizadas ao Streamlit"""
    # Esta função pode ser chamada no início do dashboard
    st.set_page_config(
        page_title="Medcal Licitações",
        layout="wide",
        page_icon="🏥",
        initial_sidebar_state="expanded"
    )
