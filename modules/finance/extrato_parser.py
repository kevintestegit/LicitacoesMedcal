"""
Parser inteligente de extratos bancários
Suporta: CSV, Excel, OFX
"""

import pandas as pd
import hashlib
from datetime import datetime
from typing import List, Dict, Optional
import re

class ExtratoParser:
    """Parser universal de extratos bancários"""

    # Mapeamento de colunas comuns
    COLUMN_MAPPINGS = {
        'data': ['data', 'date', 'dt_lancamento', 'data_lancamento', 'data_movimento', 'data mov', 'dt mov'],
        'descricao': ['descricao', 'historico', 'description', 'desc', 'histórico', 'detalhes'],
        'valor': ['valor', 'value', 'amount', 'vlr_lancamento', 'valor_lancamento'],
        'documento': ['documento', 'doc', 'numero_documento', 'num_doc', 'cheque'],
        'tipo': ['tipo', 'type', 'natureza', 'operacao', 'operação']
    }

    def __init__(self):
        self.erros = []

    def parse_file(self, file_content, filename: str, conta_id: int) -> List[Dict]:
        """
        Faz parse de arquivo de extrato e retorna lista de lançamentos normalizados

        Args:
            file_content: Conteúdo do arquivo (BytesIO ou similar)
            filename: Nome do arquivo
            conta_id: ID da conta bancária

        Returns:
            Lista de dicionários com lançamentos normalizados
        """
        self.erros = []

        # Detecta formato
        if filename.endswith('.csv'):
            df = self._parse_csv(file_content)
        elif filename.endswith(('.xlsx', '.xls')):
            df = self._parse_excel(file_content)
        elif filename.endswith('.ofx'):
            df = self._parse_ofx(file_content)
        else:
            raise ValueError(f"Formato não suportado: {filename}")

        if df is None or df.empty:
            raise ValueError("Arquivo vazio ou inválido")

        # Normaliza colunas
        df_normalized = self._normalize_columns(df)

        # Converte para lista de lançamentos
        lancamentos = self._extract_lancamentos(df_normalized, filename, conta_id)

        return lancamentos

    def _parse_csv(self, file_content) -> pd.DataFrame:
        """Parse de arquivo CSV"""
        try:
            # Tenta diferentes encodings
            for encoding in ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']:
                try:
                    file_content.seek(0)
                    df = pd.read_csv(file_content, encoding=encoding, sep=None, engine='python')
                    if not df.empty:
                        return df
                except:
                    continue
            return None
        except Exception as e:
            self.erros.append(f"Erro ao ler CSV: {str(e)}")
            return None

    def _parse_excel(self, file_content) -> pd.DataFrame:
        """Parse de arquivo Excel"""
        try:
            file_content.seek(0)
            # Tenta ler a primeira planilha
            df = pd.read_excel(file_content, engine='openpyxl')
            return df
        except Exception as e:
            self.erros.append(f"Erro ao ler Excel: {str(e)}")
            return None

    def _parse_ofx(self, file_content) -> pd.DataFrame:
        """Parse de arquivo OFX"""
        try:
            from ofxparse import OfxParser
            file_content.seek(0)
            ofx = OfxParser.parse(file_content)

            # Extrai transações
            transactions = []
            for account in ofx.accounts:
                for trans in account.statement.transactions:
                    transactions.append({
                        'data': trans.date,
                        'descricao': trans.memo or trans.payee,
                        'valor': float(trans.amount),
                        'tipo': trans.type,
                        'documento': trans.id
                    })

            return pd.DataFrame(transactions)
        except ImportError:
            self.erros.append("Biblioteca ofxparse não instalada. Execute: pip install ofxparse")
            return None
        except Exception as e:
            self.erros.append(f"Erro ao ler OFX: {str(e)}")
            return None

    def _normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normaliza nomes de colunas para padrão"""
        df_copy = df.copy()

        # Lowercase e remove espaços
        df_copy.columns = [str(col).lower().strip() for col in df_copy.columns]

        # Mapeia colunas
        column_map = {}
        for standard_name, possible_names in self.COLUMN_MAPPINGS.items():
            for col in df_copy.columns:
                if any(pn in col for pn in possible_names):
                    column_map[col] = standard_name
                    break

        df_copy = df_copy.rename(columns=column_map)

        return df_copy

    def _extract_lancamentos(self, df: pd.DataFrame, filename: str, conta_id: int) -> List[Dict]:
        """Extrai lançamentos do DataFrame normalizado"""
        lancamentos = []

        # Colunas obrigatórias
        if 'data' not in df.columns or 'descricao' not in df.columns:
            raise ValueError("Arquivo deve conter pelo menos colunas de Data e Descrição")

        for idx, row in df.iterrows():
            try:
                # Data
                data_lancamento = self._parse_date(row.get('data'))
                if not data_lancamento:
                    continue

                # Descrição
                descricao = str(row.get('descricao', '')).strip()
                if not descricao or descricao.lower() in ['nan', 'none', '']:
                    continue

                # Valor
                valor = self._parse_valor(row.get('valor', 0))

                # Se não tem coluna valor, tenta detectar crédito/débito
                if valor == 0:
                    credito = self._parse_valor(row.get('credito', row.get('crédito', 0)))
                    debito = self._parse_valor(row.get('debito', row.get('débito', 0)))
                    valor = credito - debito

                # Tipo
                tipo = self._detectar_tipo(row.get('tipo', ''), valor)

                # Hash único para evitar duplicatas
                hash_str = f"{conta_id}_{data_lancamento}_{descricao}_{valor}"
                hash_lancamento = hashlib.md5(hash_str.encode()).hexdigest()

                lancamento = {
                    'conta_id': conta_id,
                    'data_lancamento': data_lancamento,
                    'descricao': descricao,
                    'documento': str(row.get('documento', '')).strip() or None,
                    'valor': valor,
                    'tipo': tipo,
                    'arquivo_origem': filename,
                    'hash_lancamento': hash_lancamento
                }

                lancamentos.append(lancamento)

            except Exception as e:
                self.erros.append(f"Linha {idx}: {str(e)}")
                continue

        return lancamentos

    def _parse_date(self, date_val) -> Optional[datetime]:
        """Parse flexível de datas"""
        if pd.isna(date_val):
            return None

        # Se já é datetime
        if isinstance(date_val, datetime):
            return date_val.date()

        # Se é string
        date_str = str(date_val).strip()

        # Tenta formatos comuns brasileiros
        for fmt in ['%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d', '%d/%m/%y', '%d.%m.%Y']:
            try:
                return datetime.strptime(date_str, fmt).date()
            except:
                continue

        # Tenta pandas to_datetime
        try:
            return pd.to_datetime(date_str, dayfirst=True).date()
        except:
            return None

    def _parse_valor(self, valor_val) -> float:
        """Parse de valores monetários"""
        if pd.isna(valor_val):
            return 0.0

        if isinstance(valor_val, (int, float)):
            return float(valor_val)

        # Remove caracteres não numéricos, exceto . , -
        valor_str = str(valor_val).strip()
        valor_str = re.sub(r'[^\d,.\-]', '', valor_str)

        # Substitui vírgula por ponto (padrão BR)
        if ',' in valor_str and '.' in valor_str:
            # Se tem ambos, assume formato BR (1.234,56)
            valor_str = valor_str.replace('.', '').replace(',', '.')
        elif ',' in valor_str:
            # Só vírgula (1234,56)
            valor_str = valor_str.replace(',', '.')

        try:
            return float(valor_str)
        except:
            return 0.0

    def _detectar_tipo(self, tipo_str: str, valor: float) -> str:
        """Detecta tipo de transação"""
        tipo_str = str(tipo_str).upper().strip()

        if 'DEBITO' in tipo_str or 'DEB' in tipo_str:
            return 'DÉBITO'
        elif 'CREDITO' in tipo_str or 'CRED' in tipo_str:
            return 'CRÉDITO'
        elif 'TRANSF' in tipo_str:
            return 'TRANSFERÊNCIA'
        elif 'TAXA' in tipo_str or 'TARIFA' in tipo_str:
            return 'TAXA'
        elif 'PIX' in tipo_str:
            return 'PIX'
        else:
            # Inferir pelo valor
            return 'CRÉDITO' if valor > 0 else 'DÉBITO'

    def categorizar_lancamento(self, descricao: str) -> str:
        """Categorização automática baseada na descrição"""
        descricao = descricao.upper()

        categorias = {
            'FOLHA DE PAGAMENTO': ['SALARIO', 'FOLHA', 'PAGAMENTO', 'VENCIMENTO', 'ORDENADO'],
            'IMPOSTOS': ['IMPOSTO', 'DARF', 'GPS', 'INSS', 'FGTS', 'IRRF', 'ICMS', 'ISS'],
            'FORNECEDORES': ['FORNECEDOR', 'COMPRA', 'PAGTO', 'NOTA FISCAL', 'NF'],
            'TAXAS BANCÁRIAS': ['TARIFA', 'TAXA', 'MANUTENÇÃO', 'ANUIDADE', 'IOF'],
            'TRANSFERÊNCIAS': ['TRANSF', 'TED', 'DOC', 'PIX'],
            'EMPRÉSTIMOS': ['EMPRESTIMO', 'FINANCIAMENTO', 'PARCELA'],
            'RECEITAS': ['RECEBIMENTO', 'VENDA', 'CLIENTE', 'DEPOSITO']
        }

        for categoria, keywords in categorias.items():
            if any(kw in descricao for kw in keywords):
                return categoria

        return 'OUTROS'
