"""
Importador flexível para extratos históricos (Sicredi/BB em formato simples).
- Aceita XLSX com colunas mínimas: Data, Descrição, Documento (opcional), Valor.
- Limpa cabeçalhos soltos na planilha e ignora totais/resumos.
"""

import hashlib
import os
import re
from collections import defaultdict
from datetime import datetime, date
from typing import Dict, List, Optional

import pandas as pd

from .extrato_parser import ExtratoBBParser, salvar_extrato_db


MESES_MAP_NUM_TO_STR = {
    1: 'Jan', 2: 'Fev', 3: 'Mar', 4: 'Abr',
    5: 'Mai', 6: 'Jun', 7: 'Jul', 8: 'Ago',
    9: 'Set', 10: 'Out', 11: 'Nov', 12: 'Dez'
}


def importar_extrato_historico(file_path: str, session, banco_origem: Optional[str] = None) -> Dict:
    """
    Importa um XLSX histórico (Sicredi/BB fora do padrão) para o banco informado.
    - Usa hash (data+histórico+valor+documento) para deduplicar.
    - Marca status='Baixado' e acrescenta observação com banco/arquivo.
    """
    parser = ExtratoBBParser()
    todos_lancamentos: List[Dict] = []

    with pd.ExcelFile(file_path, engine='openpyxl') as xl:
        for sheet in xl.sheet_names:
            df_raw = pd.read_excel(xl, sheet_name=sheet, engine='openpyxl')
            df = _localizar_cabecalho_generico(df_raw)
            if df is None:
                continue

            df = _renomear_colunas(df)
            if 'data' not in df.columns or 'descricao' not in df.columns or 'valor' not in df.columns:
                continue

            extras_cols = [c for c in df.columns if c not in ['data', 'descricao', 'documento', 'valor']]

            for row in df.itertuples(index=False):
                dt = _parse_data(getattr(row, 'data', None))
                if not dt:
                    continue

                historico = str(getattr(row, 'descricao', '')).strip()
                if not historico or historico.lower() in ['nan', 'none', '']:
                    continue

                valor = _parse_valor(getattr(row, 'valor', 0))
                if valor == 0:
                    continue

                documento = _formatar_documento(getattr(row, 'documento', None))

                # Captura fatura em colunas extras (ex.: coluna E nos Sicredi, coluna G nos BB históricos)
                fatura_val = getattr(row, 'fatura', None) if hasattr(row, 'fatura') else None
                if not fatura_val:
                    for col in extras_cols:
                        val = getattr(row, col, None)
                        if pd.notna(val) and str(val).strip() not in ['nan', 'None', '']:
                            fatura_val = val
                            break

                obs = []
                for col in extras_cols:
                    val = getattr(row, col, None)
                    if pd.notna(val) and str(val).strip() not in ['nan', 'None', '']:
                        # Evita duplicar a mesma info que já foi para fatura
                        if val == fatura_val:
                            continue
                        obs.append(f"{col}: {val}")
                if banco_origem:
                    obs.append(f"Banco: {banco_origem}")
                obs.append(f"Aba: {sheet}")
                obs.append(f"Arquivo: {os.path.basename(file_path)}")
                observacoes = " | ".join(obs)

                mes_ref = MESES_MAP_NUM_TO_STR.get(dt.month)
                ano_ref = dt.year
                tipo_base = _inferir_tipo_basico(historico, valor)

                lancamento = {
                    'status': 'Baixado',
                    'dt_balancete': dt,
                    'ag_origem': None,
                    'lote': None,
                    'historico': historico,
                    'documento': documento,
                    'valor': valor,
                    'fatura': _formatar_fatura(fatura_val),
                    'tipo': tipo_base,
                    'historico_complementar': None,
                    'mes_referencia': mes_ref,
                    'ano_referencia': ano_ref,
                    'arquivo_origem': file_path,
                    'observacoes': observacoes,
                    'hash_lancamento': _gerar_hash(dt, historico, valor, documento),
                    'banco': '748' if 'sicred' in (banco_origem or '').lower() else None
                }
                todos_lancamentos.append(lancamento)

    resumos = _calcular_resumos_por_mes(parser, todos_lancamentos)

    resultado = {
        'lancamentos': todos_lancamentos,
        'resumos': resumos,
        'total_lancamentos': len(todos_lancamentos),
        'erros': [],
        'avisos': [],
        'fonte': os.path.basename(file_path),
    }
    return salvar_extrato_db(session, resultado)


def _localizar_cabecalho_generico(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    """Procura linha com cabeçalho contendo 'data' e 'descr'/'hist'.
    OTIMIZADO: Usa itertuples ao invés de iterrows"""
    for idx, row in enumerate(df.head(30).itertuples(index=False)):
        labels = [str(x).strip() for x in row]
        labels_lower = [l.lower() for l in labels if l]
        if any('data' in l for l in labels_lower) and any(('descr' in l) or ('hist' in l) for l in labels_lower):
            df_clean = df.iloc[idx+1:].reset_index(drop=True)
            df_clean.columns = labels
            return df_clean

    # Já vem com colunas boas
    if any('data' in str(c).lower() for c in df.columns):
        return df

    return None


def _renomear_colunas(df: pd.DataFrame) -> pd.DataFrame:
    mapping = {}
    new_cols = []
    for col in df.columns:
        c = str(col).strip().lower()
        if 'data' == c or c.startswith('data'):
            new_cols.append('data')
        elif 'descr' in c or 'hist' in c:
            new_cols.append('descricao')
        elif 'doc' in c:
            new_cols.append('documento')
        elif 'valor' in c:
            new_cols.append('valor')
        else:
            new_cols.append(c.replace(' ', '_'))
    df.columns = new_cols
    return df


def _parse_data(date_val) -> Optional[date]:
    if pd.isna(date_val):
        return None
    if isinstance(date_val, (datetime, date)):
        return date_val.date() if isinstance(date_val, datetime) else date_val
    date_str = str(date_val).strip()
    for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%d/%m/%y']:
        try:
            return datetime.strptime(date_str.split()[0], fmt).date()
        except Exception:
            continue
    try:
        return pd.to_datetime(date_str, dayfirst=True).date()
    except Exception:
        return None


def _parse_valor(valor_val) -> float:
    if pd.isna(valor_val):
        return 0.0
    if isinstance(valor_val, (int, float)):
        return float(valor_val)
    valor_str = str(valor_val).strip().upper()
    multiplier = 1.0
    if valor_str.endswith('D') or valor_str.endswith('-'):
        multiplier = -1.0
    elif '(' in valor_str and ')' in valor_str:
        multiplier = -1.0
    elif valor_str.startswith('-'):
        multiplier = -1.0
    valor_limpo = re.sub(r'[^\d,.]', '', valor_str)
    if not valor_limpo:
        return 0.0
    if ',' in valor_limpo and '.' in valor_limpo:
        valor_limpo = valor_limpo.replace('.', '').replace(',', '.')
    elif ',' in valor_limpo:
        valor_limpo = valor_limpo.replace(',', '.')
    try:
        return float(valor_limpo) * multiplier
    except Exception:
        return 0.0


def _formatar_documento(doc) -> Optional[str]:
    if doc is None or pd.isna(doc):
        return None
    doc_str = str(doc).strip()
    if doc_str.lower() in ['nan', 'none', '']:
        return None
    if doc_str.endswith('.0'):
        doc_str = doc_str[:-2]
    try:
        if 'e' in doc_str.lower() or len(doc_str) > 15:
            doc_num = int(float(doc_str))
            return str(doc_num)
    except Exception:
        pass
    return doc_str


def _formatar_fatura(fat) -> Optional[str]:
    if fat is None or pd.isna(fat):
        return None
    fat_str = str(fat).strip()
    if fat_str.lower() in ['nan', 'none', '']:
        return None
    if fat_str.endswith('.0'):
        fat_str = fat_str[:-2]
    return fat_str


def _inferir_tipo_basico(historico: str, valor: float) -> str:
    """
    Heurística simples para classificar créditos recorrentes (ex.: SESAP no Sicredi).
    """
    hist_upper = historico.upper()
    if '08241739000105' in hist_upper and 'FONDO' not in hist_upper:  # CNPJ SESAP/RN no Sicredi
        return 'Recebimento SESAP'
    if 'FUNDO DE SAUDE DO RN FUSERN' in hist_upper or 'FONDO DE SAUDE DO RN FUSERN' in hist_upper:
        return 'Recebimento SESAP'
    return "Histórico Crédito" if valor > 0 else "Histórico Débito"


def _gerar_hash(data, historico: str, valor: float, documento) -> str:
    hash_str = f"{data}_{historico}_{valor}_{documento}"
    return hashlib.sha256(hash_str.encode()).hexdigest()[:32]


def _calcular_resumos_por_mes(parser: ExtratoBBParser, lancamentos: List[Dict]) -> Dict:
    grupos = defaultdict(list)
    for lanc in lancamentos:
        if lanc.get('mes_referencia') and lanc.get('ano_referencia'):
            chave = (lanc['mes_referencia'], lanc['ano_referencia'])
            grupos[chave].append(lanc)

    resumos = {}
    for (mes, ano), items in grupos.items():
        resumos[mes] = parser._calcular_resumo(items, mes, ano)
    return resumos
