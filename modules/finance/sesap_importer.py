"""
Importador da planilha SESAP (listagem de lançamentos a receber/pagos).
- Detecta cabeçalho (linha com "Filial") e lê colunas principais.
- Salva em `sesap_pagamentos` com deduplicação simples (hash de processo+doc+valor+vencimento).
"""
import os
import hashlib
from datetime import datetime, date
from typing import Dict

import pandas as pd

from .bank_models import SesapPagamento


def importar_planilha_sesap(file_path: str, session, arquivo_origem: str = None) -> Dict:
    df_raw = pd.read_excel(file_path, sheet_name=0, header=None)

    header_row = _encontrar_header(df_raw)
    if header_row is None:
        return {'importados': 0, 'duplicados': 0, 'erros': ['Cabeçalho não encontrado'], 'avisos': []}

    header = df_raw.iloc[header_row]
    df = df_raw.iloc[header_row + 1:].copy()
    df.columns = header

    # Normaliza nomes de colunas
    col_map = {}
    for col in df.columns:
        c = str(col).strip().lower()
        if 'filial' in c:
            col_map['filial'] = col
        elif 'compet' in c:
            col_map['competencia'] = col
        elif 'unidade' in c:
            col_map['unidade'] = col
        elif 'contrato' in c:
            col_map['contrato'] = col
        elif 'cliente' in c or 'fornecedor' in c:
            col_map['cliente'] = col
        elif 'emiss' in c:
            col_map['dt_emissao'] = col
        elif 'doc' in c and 'nº' in c or ('doc' in c and 'num' in c):
            col_map['num_doc'] = col
        elif 'líquido' in c or 'liquido' in c:
            col_map['valor_liquido'] = col
        elif 'venc' in c:
            col_map['dt_vencimento'] = col
        elif 'processo' in c:
            col_map['num_processo'] = col
        elif 'status' in c:
            col_map['status_sesap'] = col
        elif 'pago' in c:
            col_map['status_manual'] = col

    importados = duplicados = 0
    avisos = []

    # OTIMIZADO: itertuples é 10-50x mais rápido que iterrows
    # Cria mapeamento de colunas para atributos namedtuple
    col_names = list(df.columns)
    
    def get_val(row_tuple, col_key):
        """Helper para acessar valor por chave do col_map de forma segura"""
        col_name = col_map.get(col_key)
        if col_name and col_name in col_names:
            idx = col_names.index(col_name)
            return row_tuple[idx]
        return None

    for row in df.itertuples(index=False):
        # Ignora linhas totalmente vazias
        if all(pd.isna(val) for val in row):
            continue

        valor = _parse_float(get_val(row, 'valor_liquido'))
        num_doc = _clean_str(get_val(row, 'num_doc'))
        num_processo = _clean_str(get_val(row, 'num_processo'))
        if not num_doc and not num_processo and valor == 0:
            continue

        dt_venc = _parse_date(get_val(row, 'dt_vencimento'))

        hash_key = _hash_registro(num_doc, num_processo, valor, dt_venc)
        existe = session.query(SesapPagamento).filter_by(observacao=hash_key).first()
        if existe:
            duplicados += 1
            continue

        pagamento = SesapPagamento(
            filial=_clean_str(get_val(row, 'filial')),
            competencia=_clean_str(get_val(row, 'competencia')),
            unidade=_clean_str(get_val(row, 'unidade')),
            contrato=_clean_str(get_val(row, 'contrato')),
            cliente_fornecedor=_clean_str(get_val(row, 'cliente')),
            dt_emissao=_parse_date(get_val(row, 'dt_emissao')),
            num_doc=num_doc,
            valor_liquido=valor,
            dt_vencimento=dt_venc,
            num_processo=num_processo,
            status_sesap=_clean_str(get_val(row, 'status_sesap')),
            status_manual=_clean_str(get_val(row, 'status_manual')),
            banco=_inferir_banco(get_val(row, 'status_manual')),
            observacao=hash_key,  # usado como dedupe simples
            arquivo_origem=arquivo_origem or os.path.basename(file_path)
        )
        session.add(pagamento)
        importados += 1

    session.commit()
    return {'importados': importados, 'duplicados': duplicados, 'erros': [], 'avisos': avisos}


def _encontrar_header(df: pd.DataFrame):
    for i in range(min(len(df), 30)):
        row = df.iloc[i].tolist()
        labels = [str(x).lower() for x in row if pd.notna(x)]
        if any('filial' in l for l in labels) and any('compet' in l for l in labels):
            return i
    return None


def _parse_date(val) -> date | None:
    if pd.isna(val):
        return None
    if isinstance(val, (datetime, date)):
        return val.date() if isinstance(val, datetime) else val
    s = str(val).strip()
    for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%d/%m/%y']:
        try:
            return datetime.strptime(s.split()[0], fmt).date()
        except Exception:
            continue
    try:
        return pd.to_datetime(s, dayfirst=True).date()
    except Exception:
        return None


def _parse_float(val) -> float:
    if pd.isna(val):
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    s = s.replace('R$', '').replace('.', '').replace(',', '.')
    try:
        return float(s)
    except Exception:
        return 0.0


def _clean_str(val):
    if val is None or pd.isna(val):
        return None
    s = str(val).strip()
    return s if s.lower() not in ['nan', 'none', ''] else None


def _inferir_banco(status_manual: str | None) -> str | None:
    if not status_manual:
        return None
    s = str(status_manual).upper()
    if '748' in s or 'SICRED' in s or 'SICREDI' in s:
        return '748'
    if '001' in s or 'BB' in s or 'BANCO DO BRASIL' in s:
        return '001'
    return None


def _hash_registro(num_doc, num_processo, valor, dt_venc):
    s = f"{num_doc}|{num_processo}|{valor}|{dt_venc}"
    return hashlib.sha256(s.encode()).hexdigest()[:16]
