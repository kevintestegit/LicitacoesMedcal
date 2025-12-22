"""
Parser de extratos bancários do Banco do Brasil
Formato específico: Status | Dt. balancete | Ag. origem | Lote | Histórico | Documento | Valor R$ | Fatura | Tipo
"""

import pandas as pd
import hashlib
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import re


class ExtratoBBParser:
    """
    Parser especializado para extratos do Banco do Brasil
    """
    
    COLUNAS_PADRAO = [
        'Status', 'Dt. balancete', 'Ag. origem', 'Lote', 
        'Histórico', 'Documento', 'Valor R$', 'Fatura', 'Tipo'
    ]
    
    MESES_MAP = {
        'Jan': 1, 'Fev': 2, 'Mar': 3, 'Abr': 4,
        'Mai': 5, 'Jun': 6, 'Jul': 7, 'Ago': 8,
        'Set': 9, 'Out': 10, 'Nov': 11, 'Dez': 12
    }

    # CPFs/CNPJ que representam APORTE DE CAPITAL (não receita operacional)
    APORTES_DOCS = {
        '83738657487',    # Magnus Soares
        '65427238468',    # Paulo Sergio
        '03319496000159'  # Medcal Farma
    }
    
    def __init__(self):
        self.erros = []
        self.avisos = []
    
    def parse_arquivo(self, file_path: str, ano: int = None) -> Dict:
        self.erros = []
        self.avisos = []
        if ano is None: ano = self._detectar_ano(file_path)
        
        with pd.ExcelFile(file_path, engine='openpyxl') as xl:
            todos_lancamentos = []
            resumos = {}
            
            for sheet_name in xl.sheet_names:
                if sheet_name.lower() == 'geral': continue
                mes = self._identificar_mes(sheet_name)
                if not mes:
                    self.avisos.append(f"Aba '{sheet_name}' não reconhecida como mês")
                    continue
                
                lancamentos = self._parse_planilha(xl, sheet_name, mes, ano, file_path)
                todos_lancamentos.extend(lancamentos)
                if lancamentos:
                    resumos[mes] = self._calcular_resumo(lancamentos, mes, ano)
        
        return {
            'lancamentos': todos_lancamentos,
            'resumos': resumos,
            'total_lancamentos': len(todos_lancamentos),
            'erros': self.erros,
            'avisos': self.avisos
        }
    
    def _parse_planilha(self, xl: pd.ExcelFile, sheet_name: str, mes: str, ano: int, arquivo: str) -> List[Dict]:
        df = pd.read_excel(xl, sheet_name=sheet_name, engine='openpyxl')
        df, inicio = self._localizar_cabecalho(df)
        if df is None:
            self.erros.append(f"Não foi possível identificar cabeçalho na aba '{sheet_name}'")
            return []
        if len(df.columns) >= 9:
            df = df.iloc[:, :9]
            df.columns = self.COLUNAS_PADRAO
        else:
            self.erros.append(f"Aba '{sheet_name}' tem menos de 9 colunas")
            return []
        
        lancamentos = []
        linha_anterior = None
        # OTIMIZADO: itertuples é 10-50x mais rápido que iterrows
        for row in df.itertuples(index=True):
            try:
                # Converte namedtuple para Series mantendo compatibilidade
                row_series = pd.Series({
                    'Status': getattr(row, 'Status', None),
                    'Dt. balancete': row[2] if len(row) > 2 else None,
                    'Ag. origem': row[3] if len(row) > 3 else None,
                    'Lote': row[4] if len(row) > 4 else None,
                    'Histórico': row[5] if len(row) > 5 else None,
                    'Documento': row[6] if len(row) > 6 else None,
                    'Valor R$': row[7] if len(row) > 7 else None,
                    'Fatura': row[8] if len(row) > 8 else None,
                    'Tipo': row[9] if len(row) > 9 else None
                })
                lancamento = self._processar_linha(row_series, linha_anterior, mes, ano, arquivo)
                if lancamento:
                    lancamentos.append(lancamento)
                    linha_anterior = None
                elif self._is_linha_complementar(row_series):
                    linha_anterior = row_series
            except Exception as e:
                self.erros.append(f"Erro na linha {row.Index} da aba '{sheet_name}': {str(e)}")
                continue
        return lancamentos
    
    def _processar_linha(self, row: pd.Series, linha_anterior: pd.Series, mes: str, ano: int, arquivo: str) -> Optional[Dict]:
        dt_balancete = self._parse_data(row.get('Dt. balancete'))
        if not dt_balancete: return None
        
        historico = str(row.get('Histórico', '')).strip()
        if not historico or historico.lower() in ['nan', 'none', '']: return None
        
        valor = self._parse_valor(row.get('Valor R$', 0))
        if valor == 0: return None

        # Linhas de "900 - Movimentacao do dia" são resumos e não devem impactar os totais
        historico_lower = historico.lower()
        is_movimentacao_dia = historico_lower.startswith('900') and 'movimenta' in historico_lower and 'dia' in historico_lower
        
        historico_complementar = None
        if linha_anterior is not None:
            hist_comp = str(linha_anterior.get('Histórico', '')).strip()
            if hist_comp and hist_comp.lower() not in ['nan', 'none', '']:
                historico_complementar = hist_comp
        
        tipo_original = self._normalizar_tipo(row.get('Tipo'))
        tipo_final = 'Movimentacao do Dia' if is_movimentacao_dia else (
            tipo_original if tipo_original else self._inferir_categoria_pelo_historico(historico)
        )

        # >>> BLOCO NOVO: detectar APORTE CAPITAL <<<
        # Junta histórico principal + complementar para procurar CPF/CNPJ
        texto_busca = f"{historico} {historico_complementar or ''}"
        is_aporte = any(doc in texto_busca for doc in self.APORTES_DOCS)

        # Se for PIX recebido ou TED/Transferência recebida de CPF/CNPJ de aporte → classifica como Aporte Capital
        if is_aporte and tipo_final in ['Pix - Recebido', 'Transferência Recebida']:
            tipo_final = 'Aporte Capital'
        # >>> FIM BLOCO NOVO <<<

        debit_categories = ['Compra com Cartão', 'Impostos', 'Pix - Enviado', 'Pagamento Boleto', 'Pagamento Fornecedor', 'Pagamento Título', 'Pagamento Ourocap', 'Tarifa Bancária', 'Transferência Enviada', 'Cheque', 'Saque', 'Pagamento Emprestimo Pronampe']
        credit_categories = ['Ordem Bancária', 'Recebimento SESAP', 'Recebimento Base Aérea', 'Pix - Recebido', 'Transferência Recebida', 'Crédito Salário', 'Depósito', 'Estorno', 'Depósito Corban', 'Hematologia', 'Coagulacao', 'Coagulação', 'Ionograma', 'Base', 'Aporte Capital']
        neutral_categories = ['Aplicação', 'Aplicação Financeira', 'BB Rende Fácil']

        if tipo_final == 'Movimentacao do Dia':
            valor = 0.0
        elif tipo_final in debit_categories: valor = -abs(valor)
        elif tipo_final in credit_categories: valor = abs(valor)
        elif any(cat in tipo_final for cat in ['Hematologia', 'Coagulacao', 'Ionograma']): valor = abs(valor)
        elif tipo_final in neutral_categories: valor = abs(valor)

        lancamento = {
            'status': self._normalizar_status(row.get('Status')),
            'dt_balancete': dt_balancete,
            'ag_origem': str(row.get('Ag. origem', '')).strip() or None,
            'lote': str(row.get('Lote', '')).strip() or None,
            'historico': historico,
            'documento': self._formatar_documento(row.get('Documento')),
            'valor': valor,
            'fatura': self._normalizar_fatura(row.get('Fatura')),
            'tipo': tipo_final,
            'historico_complementar': historico_complementar,
            'mes_referencia': mes,
            'ano_referencia': ano,
            'arquivo_origem': arquivo,
            'hash_lancamento': self._gerar_hash(dt_balancete, historico, valor, row.get('Documento'))
        }
        return lancamento

    def _inferir_categoria_pelo_historico(self, historico: str) -> str:
        hist_upper = historico.upper()
        match_code = re.match(r'^(\d+)', historico)
        code = match_code.group(1) if match_code else None
    
        if code:
            if code == '500': return 'Pagamento Emprestimo Pronampe'
            if code == '976':
                return 'Transferência Recebida'

            if code == '821': return 'Pix - Recebido'
            if code == '144': return 'Pix - Enviado'
            if code == '632': 
                if '12 SEC TES NAC' in hist_upper or 'AEREA' in hist_upper: 
                    return 'Recebimento Base Aérea'
                return 'Recebimento SESAP'
            if code == '234': return 'Compra com Cartão'
            if code == '375': return 'Impostos'
            if code == '860': return 'Pagamento Título'
            if code == '361' or code == '363': return 'Pagamento Boleto'
            if code == '168': return 'Pagamento Ourocap'
            if code == '342': return 'Aplicação Financeira'
            if code == '470': return 'Transferência Enviada'
            if code == '471': return 'Transferência Recebida'
            if code == '870': return 'Transferência Recebida'
            if code == '830': return 'Depósito Corban'
            if code == '969': return 'Cheque Compensado'
    
        if 'PIX' in hist_upper:
            if any(x in hist_upper for x in ['RECEBIDO', 'CREDIT', 'CREDI']): return 'Pix - Recebido'
            return 'Pix - Enviado'
        if 'CARTAO' in hist_upper or 'COMPRA' in hist_upper: return 'Compra com Cartão'
        if 'IMPOSTO' in hist_upper or 'TRIBUTO' in hist_upper or 'DAS' in hist_upper or 'DARF' in hist_upper: return 'Impostos'
        if 'BOLETO' in hist_upper or 'TITULO' in hist_upper or 'CONVENIO' in hist_upper: return 'Pagamento Boleto'
        if 'TARIFA' in hist_upper or 'CESTA' in hist_upper or 'DEBITO SERVICO' in hist_upper: return 'Tarifa Bancária'
        if 'APLICACAO' in hist_upper or 'BB RENDE' in hist_upper: return 'Aplicação'
        if 'TED' in hist_upper or 'DOC' in hist_upper or 'TRANSFERENCIA' in hist_upper:
            if 'RECEB' in hist_upper or 'CRED' in hist_upper: return 'Transferência Recebida'
            return 'Transferência Enviada'
        if 'CHEQUE' in hist_upper: return 'Cheque'
        if 'SISPAG' in hist_upper or 'FORNECEDOR' in hist_upper: return 'Pagamento Fornecedor'
        return 'Outros'

    
    def _localizar_cabecalho(self, df: pd.DataFrame) -> Tuple[Optional[pd.DataFrame], int]:
        # OTIMIZADO: itertuples mais rápido que iterrows
        for row in df.itertuples():
            row_str = ' '.join([str(val).lower() for val in row[1:] if pd.notna(val)])
            if 'status' in row_str or 'dt. balancete' in row_str or 'balancete' in row_str:
                return df.iloc[row.Index+1:].reset_index(drop=True), row.Index
        if any('status' in str(col).lower() for col in df.columns): return df, 0
        return None, -1
    
    def _is_linha_complementar(self, row: pd.Series) -> bool:
        dt = row.get('Dt. balancete')
        valor = row.get('Valor R$')
        historico = row.get('Histórico')
        return pd.isna(dt) and (pd.isna(valor) or self._parse_valor(valor) == 0) and pd.notna(historico)
    
    def _parse_data(self, date_val) -> Optional[datetime]:
        if pd.isna(date_val): return None
        if isinstance(date_val, datetime): return date_val.date() if hasattr(date_val, 'date') else date_val
        if hasattr(date_val, 'date'): return date_val.date()
        date_str = str(date_val).strip()
        for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%d/%m/%y', '%Y-%m-%d %H:%M:%S']:
            try: return datetime.strptime(date_str.split()[0], fmt).date()
            except: continue
        try: return pd.to_datetime(date_str, dayfirst=True).date()
        except: return None
    
    def _parse_valor(self, valor_val) -> float:
        if pd.isna(valor_val): return 0.0
        if isinstance(valor_val, (int, float)): return float(valor_val)
        valor_str = str(valor_val).strip().upper()
        multiplier = 1.0
        if valor_str.endswith('D') or valor_str.endswith('-'): multiplier = -1.0
        elif '(' in valor_str and ')' in valor_str: multiplier = -1.0
        elif valor_str.startswith('-'): multiplier = -1.0
        valor_limpo = re.sub(r'[^\d,.]', '', valor_str)
        if not valor_limpo: return 0.0
        if ',' in valor_limpo and '.' in valor_limpo: valor_limpo = valor_limpo.replace('.', '').replace(',', '.')
        elif ',' in valor_limpo: valor_limpo = valor_limpo.replace(',', '.')
        try: return float(valor_limpo) * multiplier
        except: return 0.0
    
    def _normalizar_status(self, status) -> Optional[str]:
        if pd.isna(status): return None
        status = str(status).strip().title()
        if status.lower() in ['baixado', 'ok', 'conciliado']: return 'Baixado'
        elif status.lower() in ['pendente', 'aberto', 'nao conciliado']: return 'Pendente'
        return status if status else None
    
    def _normalizar_tipo(self, tipo) -> Optional[str]:
        if pd.isna(tipo): return None
        tipo = str(tipo).strip()
        if tipo.lower() in ['nan', 'none', '']: return None
        return tipo.title()
    
    def _normalizar_fatura(self, fatura) -> Optional[str]:
        if pd.isna(fatura): return None
        fatura = str(fatura).strip()
        if fatura.lower() in ['nan', 'none', '']: return None
        return fatura
    
    def _formatar_documento(self, doc) -> Optional[str]:
        if pd.isna(doc): return None
        doc_str = str(doc).strip()
        if doc_str.endswith('.0'): doc_str = doc_str[:-2]
        try:
            if 'e' in doc_str.lower() or len(doc_str) > 15:
                doc_num = int(float(doc_str))
                return str(doc_num)
        except: pass
        return doc_str if doc_str.lower() not in ['nan', 'none', ''] else None
    
    def _gerar_hash(self, data, historico: str, valor: float, documento) -> str:
        hash_str = f"{data}_{historico}_{valor}_{documento}"
        return hashlib.sha256(hash_str.encode()).hexdigest()[:32]
    
    def _identificar_mes(self, sheet_name: str) -> Optional[str]:
        nome = sheet_name.strip()[:3].title()
        return nome if nome in self.MESES_MAP else None
    
    def _detectar_ano(self, file_path: str) -> int:
        import os
        nome = os.path.basename(file_path)
        match = re.search(r'(202\d)', nome)
        if match: return int(match.group(1))
        return datetime.now().year

    def _calcular_resumo(self, lancamentos: List[Dict], mes: str, ano: int) -> Dict:
        tipos_ignorados = ['Aplicação Financeira', 'Aplicação', 'Movimentacao do Dia', 'Resgate', 'Resgate Investimento', 'BB Rende Fácil']
        
        valores_reais_entradas = []
        valores_reais_saidas = []
        valores_aportes = []

        for l in lancamentos:
            tipo = l.get('tipo')
            valor = l['valor']
            if tipo in tipos_ignorados:
                continue

            if valor > 0:
                valores_reais_entradas.append(valor)
                # Se for Aporte Capital, guarda separado
                if tipo and 'aporte' in tipo.lower():
                    valores_aportes.append(valor)
            elif valor < 0:
                valores_reais_saidas.append(abs(valor))

        total_entradas = sum(valores_reais_entradas)
        total_saidas = sum(valores_reais_saidas)
        total_aportes = sum(valores_aportes)
        total_entradas_sem_aportes = total_entradas - total_aportes

        total_valor_liquido = sum(l['valor'] for l in lancamentos)
        resumo = {
            'mes': mes,
            'ano': ano,
            'total_lancamentos': len(lancamentos),
            'total_valor': total_valor_liquido,

            # Entradas totais (incluindo aportes)
            'total_entradas': total_entradas,
            'total_saidas': total_saidas,

            # NOVOS CAMPOS:
            'total_aportes': total_aportes,
            'total_entradas_sem_aportes': total_entradas_sem_aportes,

            'total_baixados': sum(1 for l in lancamentos if l['status'] == 'Baixado'),
            'valor_baixados': sum(l['valor'] for l in lancamentos if l['status'] == 'Baixado'),
            'total_pendentes': sum(1 for l in lancamentos if l['status'] == 'Pendente'),
            'valor_pendentes': sum(l['valor'] for l in lancamentos if l['status'] == 'Pendente'),
            'total_hematologia': sum(l['valor'] for l in lancamentos if l['tipo'] and 'hematologia' in l['tipo'].lower()),
            'total_coagulacao': sum(l['valor'] for l in lancamentos if l['tipo'] and 'coagula' in l['tipo'].lower()),
            'total_ionograma': sum(l['valor'] for l in lancamentos if l['tipo'] and 'ionograma' in l['tipo'].lower()),
            'total_base': sum(l['valor'] for l in lancamentos if l['tipo'] and 'base' in l['tipo'].lower()),
        }
        resumo['total_outros'] = resumo['total_valor'] - (
            resumo['total_hematologia'] +
            resumo['total_coagulacao'] +
            resumo['total_ionograma'] +
            resumo['total_base']
        )
        return resumo


    def parse_text(self, text_content: str) -> Dict:
        self.erros = []
        self.avisos = []
        lines = text_content.strip().split('\n')
        if not lines: return {'lancamentos': [], 'resumos': {}, 'total_lancamentos': 0, 'erros': ["Texto vazio"], 'avisos': []}

        lancamentos = []
        ano_detectado = datetime.now().year
        mes_detectado = None
        lancamento_anterior = None
        
        for line in lines:
            # Pula linhas vazias
            if not line.strip():
                continue

            # Pula linha de cabeçalho
            line_upper = line.upper()
            if any(header in line_upper for header in ['DT. BALANCETE', 'DT. MOVIMENTO', 'HISTÓRICO', 'VALOR R$']):
                continue

            # Pula linhas de "Saldo Anterior" (apenas informativo, não é transação real)
            if 'SALDO ANTERIOR' in line_upper:
                continue

            cols = line.split('\t')
            if len(cols) < 3:
                if ';' in line: cols = line.split(';')
            if len(cols) < 3:
                if lancamento_anterior and line.strip():
                    texto_comp = line.strip()
                    if "Dt. balancete" not in texto_comp and "Saldo" not in texto_comp:
                        if lancamento_anterior['historico_complementar']: lancamento_anterior['historico_complementar'] += " " + texto_comp
                        else: lancamento_anterior['historico_complementar'] = texto_comp
                continue

            is_bb_standard = False
            dt_val = self._parse_data(cols[0])
            if dt_val and len(cols) >= 7:
                v_str = cols[6].strip()
                if re.search(r'[\d.,]+[ ]?[DC]?', v_str):
                    col_data_idx = 0
                    col_valor_idx = 6
                    historico = cols[4].strip()
                    documento = self._formatar_documento(cols[5])
                    valor = self._parse_valor(v_str)
                    is_bb_standard = True
                    if not mes_detectado:
                        mes_detectado = list(self.MESES_MAP.keys())[dt_val.month - 1]
                        ano_detectado = dt_val.year

            if not is_bb_standard:
                col_data_idx = -1
                dt_val = None
                for i, val in enumerate(cols):
                    dt = self._parse_data(val)
                    if dt:
                        col_data_idx = i
                        dt_val = dt
                        if not mes_detectado:
                            mes_detectado = list(self.MESES_MAP.keys())[dt.month - 1]
                            ano_detectado = dt.year
                        break
                if col_data_idx == -1: 
                    if lancamento_anterior and line.strip():
                        maior_texto = max(cols, key=len).strip()
                        if len(maior_texto) > 3 and "Dt. balancete" not in maior_texto:
                             if lancamento_anterior['historico_complementar']: lancamento_anterior['historico_complementar'] += " " + maior_texto
                             else: lancamento_anterior['historico_complementar'] = maior_texto
                    continue
                
                col_valor_idx = -1
                valor = 0.0
                for i in range(len(cols) - 1, -1, -1):
                    if i == col_data_idx: continue
                    v_str = cols[i].strip()
                    if re.match(r'^\\d+$', v_str): continue 
                    if re.search(r'[\d.,]+[ ]?[DC]?', v_str):
                         v = self._parse_valor(v_str)
                         if v != 0 or '0,00' in v_str or '0.00' in v_str:
                             col_valor_idx = i
                             valor = v
                             break
                if col_valor_idx == -1: continue
                historico = ""
                documento = None
                if col_valor_idx > col_data_idx: candidates = cols[col_data_idx+1 : col_valor_idx]
                else: candidates = cols[col_data_idx+1:]
                if candidates:
                    sorted_candidates = sorted(candidates, key=len, reverse=True)
                    historico = sorted_candidates[0].strip()
                    for cand in candidates:
                        if cand != historico and len(cand) < 20 and re.search(r'\\d', cand):
                            documento = self._formatar_documento(cand)
                            break
            
            if not historico: historico = "Lançamento Importado"
            hist_lower = historico.lower()
            is_movimentacao_dia = hist_lower.startswith('900') and 'movimenta' in hist_lower and 'dia' in hist_lower
            tipo_inferido = 'Movimentacao do Dia' if is_movimentacao_dia else self._inferir_categoria_pelo_historico(historico)

            debit_categories = ['Compra com Cartão', 'Impostos', 'Pix - Enviado', 'Pagamento Boleto', 'Pagamento Fornecedor', 'Pagamento Título', 'Tarifa Bancária', 'Transferência Enviada', 'Cheque', 'Saque', 'Aplicação', 'Aplicação Financeira', 'Pagamento Ourocap', 'Pagamento Emprestimo Pronampe']
            credit_categories = ['Ordem Bancária', 'Recebimento SESAP', 'Recebimento Base Aérea', 'Pix - Recebido', 'Transferência Recebida', 'Crédito Salário', 'Depósito', 'Estorno', 'Depósito Corban', 'Aporte Capital']
            neutral_categories = ['Aplicação', 'Aplicação Financeira', 'BB Rende Fácil']

            if tipo_inferido == 'Movimentacao do Dia':
                valor = 0.0
            elif tipo_inferido in debit_categories: valor = -abs(valor)
            elif tipo_inferido in credit_categories: valor = abs(valor)
            elif tipo_inferido in neutral_categories: valor = abs(valor)

            lancamento = {
                'status': None,
                'dt_balancete': dt_val,
                'ag_origem': None,
                'lote': None,
                'historico': historico,
                'documento': documento,
                'valor': valor,
                'fatura': None,
                'tipo': tipo_inferido,
                'historico_complementar': None,
                'mes_referencia': mes_detectado,
                'ano_referencia': ano_detectado,
                'arquivo_origem': "Cola_Excel",
                'hash_lancamento': self._gerar_hash(dt_val, historico, valor, documento)
            }
            lancamentos.append(lancamento)
            lancamento_anterior = lancamento

        # >>> SEGUNDA PASSAGEM: Reclassificar aportes agora que histórico complementar foi coletado <<<
        for lanc in lancamentos:
            if lanc['tipo'] in ['Pix - Recebido', 'Transferência Recebida']:
                texto_completo = f"{lanc['historico']} {lanc.get('historico_complementar', '') or ''}"
                is_aporte = any(doc in texto_completo for doc in self.APORTES_DOCS)
                if is_aporte:
                    lanc['tipo'] = 'Aporte Capital'
                    # Garante que o valor é positivo (crédito)
                    lanc['valor'] = abs(lanc['valor'])
        # >>> FIM SEGUNDA PASSAGEM <<<

        resumos = {}
        if lancamentos:
            from collections import Counter
            datas = [l['dt_balancete'] for l in lancamentos if l['dt_balancete']]
            if datas:
                mes_ano_pairs = [(d.month, d.year) for d in datas]
                most_common = Counter(mes_ano_pairs).most_common(1)[0][0]
                mes_final_num, ano_final = most_common
                mes_final_str = list(self.MESES_MAP.keys())[mes_final_num - 1]
                for l in lancamentos:
                    l['mes_referencia'] = mes_final_str
                    l['ano_referencia'] = ano_final
                resumos[mes_final_str] = self._calcular_resumo(lancamentos, mes_final_str, ano_final)

        return {'lancamentos': lancamentos, 'resumos': resumos, 'total_lancamentos': len(lancamentos), 'erros': self.erros, 'avisos': self.avisos}

from .audit import log_finance_event


def salvar_extrato_db(session, resultado: Dict) -> Dict:
    from .bank_models import ExtratoBB, ResumoMensal

    stats = {'importados': 0, 'duplicados': 0, 'erros': resultado.get('erros', []), 'avisos': resultado.get('avisos', [])}

    for lanc in resultado['lancamentos']:
        existe = session.query(ExtratoBB).filter_by(hash_lancamento=lanc['hash_lancamento']).first()
        if existe:
            stats['duplicados'] += 1
            if not existe.tipo or existe.tipo == 'Outros': existe.tipo = lanc['tipo']
            continue
        extrato = ExtratoBB(**lanc)
        session.add(extrato)
        stats['importados'] += 1
    
    for mes, resumo in resultado['resumos'].items():
        resumo_db = session.query(ResumoMensal).filter_by(mes=mes, ano=resumo['ano']).first()
        if resumo_db:
            for key, value in resumo.items():
                if hasattr(resumo_db, key): setattr(resumo_db, key, value)
            resumo_db.data_atualizacao = datetime.now()
        else:
            resumo_db = ResumoMensal(**resumo)
            session.add(resumo_db)
    
    session.commit()
    try:
        log_finance_event(
            session,
            event_type="import",
            message=f"Importação concluída: {stats['importados']} novos, {stats['duplicados']} duplicados",
            source=resultado.get('fonte'),
            meta={'erros': len(stats['erros']), 'avisos': len(stats['avisos'])},
        )
        session.commit()
    except Exception:
        session.rollback()
    return stats

def importar_extrato_bb(file_path: str, session, ano: int = None) -> Dict:
    parser = ExtratoBBParser()
    resultado = parser.parse_arquivo(file_path, ano)
    return salvar_extrato_db(session, resultado)

def processar_texto_extrato(texto: str, session) -> Dict:
    parser = ExtratoBBParser()
    resultado = parser.parse_text(texto)
    return salvar_extrato_db(session, resultado)
