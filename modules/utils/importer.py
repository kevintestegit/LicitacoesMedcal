import pandas as pd
import io
from datetime import datetime

def load_data(file):
    """
    Carrega dados de CSV ou Excel.
    Retorna um DataFrame pandas.
    """
    try:
        if file.name.endswith('.csv'):
            return pd.read_csv(file)
        elif file.name.endswith(('.xls', '.xlsx')):
            return pd.read_excel(file)
        else:
            return None
    except Exception as e:
        print(f"Erro ao ler arquivo: {e}")
        return None

def smart_map_columns(df):
    """
    Tenta identificar automaticamente as colunas relevantes (Objeto, Quantidade, Unidade, Preço).
    Retorna um dicionário com o mapeamento sugerido.
    """
    columns = df.columns.tolist()
    mapping = {
        "descricao": None,
        "quantidade": None,
        "unidade": None,
        "valor_unitario": None,
        "orgao": None,
        "numero_edital": None
    }
    
    # Heurísticas simples (case insensitive)
    for col in columns:
        col_lower = col.lower().strip()
        
        # Descrição / Objeto
        if not mapping["descricao"] and any(x in col_lower for x in ['objeto', 'descrição', 'descricao', 'produto', 'item', 'material']):
            mapping["descricao"] = col
            
        # Quantidade
        if not mapping["quantidade"] and any(x in col_lower for x in ['qtd', 'quant', 'qtde', 'quantidade']):
            mapping["quantidade"] = col
            
        # Unidade
        if not mapping["unidade"] and any(x in col_lower for x in ['unid', 'und', 'unidade', 'medida']):
            mapping["unidade"] = col
            
        # Valor Unitário
        if not mapping["valor_unitario"] and any(x in col_lower for x in ['valor unit', 'vlr unit', 'preco unit', 'preço unit']):
            mapping["valor_unitario"] = col
            
        # Órgão
        if not mapping["orgao"] and any(x in col_lower for x in ['orgao', 'órgão', 'comprador', 'cliente']):
            mapping["orgao"] = col
            
        # Número Edital
        if not mapping["numero_edital"] and any(x in col_lower for x in ['edital', 'licitacao', 'licitação', 'processo']):
            mapping["numero_edital"] = col
            
    return mapping

def normalize_imported_data(df, mapping):
    """
    Padroniza o DataFrame importado para o formato usado no sistema.
    OTIMIZADO: Usa itertuples() (10-50x mais rápido que iterrows)
    """
    normalized = []
    
    # Cria dicionário reverso para mapear nomes de colunas para índices
    col_to_idx = {col: idx for idx, col in enumerate(df.columns)}
    
    for row in df.itertuples(index=False):
        # Acessa valores por índice usando o mapeamento
        descricao_col = mapping["descricao"]
        quantidade_col = mapping["quantidade"]
        unidade_col = mapping["unidade"]
        valor_unitario_col = mapping["valor_unitario"]
        orgao_col = mapping["orgao"]
        numero_edital_col = mapping["numero_edital"]
        
        item = {
            "descricao": str(row[col_to_idx[descricao_col]]) if descricao_col and descricao_col in col_to_idx else "Sem Descrição",
            "quantidade": float(row[col_to_idx[quantidade_col]]) if quantidade_col and quantidade_col in col_to_idx and pd.notnull(row[col_to_idx[quantidade_col]]) else 1.0,
            "unidade": str(row[col_to_idx[unidade_col]]) if unidade_col and unidade_col in col_to_idx else "UN",
            "valor_unitario": float(row[col_to_idx[valor_unitario_col]]) if valor_unitario_col and valor_unitario_col in col_to_idx and pd.notnull(row[col_to_idx[valor_unitario_col]]) else 0.0,
            "orgao": str(row[col_to_idx[orgao_col]]) if orgao_col and orgao_col in col_to_idx else "Importado",
            "numero_edital": str(row[col_to_idx[numero_edital_col]]) if numero_edital_col and numero_edital_col in col_to_idx else f"IMP-{datetime.now().strftime('%Y%m%d')}",
            "original_row": {df.columns[i]: row[i] for i in range(len(row))}
        }
        normalized.append(item)
        
    return pd.DataFrame(normalized)
