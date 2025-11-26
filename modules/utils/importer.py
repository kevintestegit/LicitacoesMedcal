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
    """
    normalized = []
    
    for index, row in df.iterrows():
        item = {
            "descricao": str(row[mapping["descricao"]]) if mapping["descricao"] else "Sem Descrição",
            "quantidade": float(row[mapping["quantidade"]]) if mapping["quantidade"] and pd.notnull(row[mapping["quantidade"]]) else 1.0,
            "unidade": str(row[mapping["unidade"]]) if mapping["unidade"] else "UN",
            "valor_unitario": float(row[mapping["valor_unitario"]]) if mapping["valor_unitario"] and pd.notnull(row[mapping["valor_unitario"]]) else 0.0,
            "orgao": str(row[mapping["orgao"]]) if mapping["orgao"] else "Importado",
            "numero_edital": str(row[mapping["numero_edital"]]) if mapping["numero_edital"] else f"IMP-{datetime.now().strftime('%Y%m%d')}",
            "original_row": row.to_dict()
        }
        normalized.append(item)
        
    return pd.DataFrame(normalized)
