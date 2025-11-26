"""
Sistema de Conciliação Automática entre Extratos e Faturas
Utiliza fuzzy matching e heurísticas para identificar pagamentos
"""

from typing import List, Dict, Tuple
from datetime import datetime, timedelta
from rapidfuzz import fuzz
import re

class ConciliadorFinanceiro:
    """Concilia extratos bancários com faturas automaticamente"""

    # Limiar de score para matching automático
    LIMIAR_AUTO_MATCH = 85
    LIMIAR_SUGESTAO = 70

    # Tolerância de dias para match de data
    TOLERANCIA_DIAS = 5

    # Tolerância percentual de valor (permite pequenas diferenças por taxas, etc)
    TOLERANCIA_VALOR_PERCENT = 2.0

    def __init__(self, session):
        """
        Args:
            session: Sessão do SQLAlchemy
        """
        self.session = session

    def buscar_matches(self, extrato, faturas: List, modo='auto') -> List[Dict]:
        """
        Busca matches entre um lançamento de extrato e uma lista de faturas

        Args:
            extrato: Objeto ExtratoBancario
            faturas: Lista de objetos Fatura
            modo: 'auto' (só matches fortes) ou 'sugestao' (inclui matches fracos)

        Returns:
            Lista de dicionários com matches e scores
        """
        matches = []

        for fatura in faturas:
            score = self._calcular_score_match(extrato, fatura)

            limiar = self.LIMIAR_AUTO_MATCH if modo == 'auto' else self.LIMIAR_SUGESTAO

            if score >= limiar:
                matches.append({
                    'fatura': fatura,
                    'score': score,
                    'tipo': 'AUTO' if score >= self.LIMIAR_AUTO_MATCH else 'SUGESTAO',
                    'detalhes': self._detalhar_match(extrato, fatura, score)
                })

        # Ordena por score (maior primeiro)
        matches.sort(key=lambda x: x['score'], reverse=True)

        return matches

    def _calcular_score_match(self, extrato, fatura) -> float:
        """
        Calcula score de matching entre extrato e fatura (0-100)

        Critérios:
        - Valor (40 pontos)
        - Data (30 pontos)
        - Descrição/Fornecedor (30 pontos)
        """
        score = 0.0

        # 1. VALOR (40 pontos)
        score_valor = self._score_valor(extrato.valor, fatura.valor_original)
        score += score_valor * 0.4

        # 2. DATA (30 pontos)
        score_data = self._score_data(extrato.data_lancamento, fatura.data_vencimento, fatura.data_pagamento)
        score += score_data * 0.3

        # 3. DESCRIÇÃO (30 pontos)
        score_descricao = self._score_descricao(extrato.descricao, fatura.fornecedor_cliente, fatura.descricao)
        score += score_descricao * 0.3

        return round(score, 2)

    def _score_valor(self, valor_extrato: float, valor_fatura: float) -> float:
        """
        Calcula score de matching de valor (0-100)
        100 = valores exatamente iguais
        0 = valores muito diferentes
        """
        # Normaliza para positivo (extrato pode ser negativo)
        valor_extrato_abs = abs(valor_extrato)

        # Diferença percentual
        if valor_fatura == 0:
            return 0.0

        diff_percent = abs((valor_extrato_abs - valor_fatura) / valor_fatura) * 100

        if diff_percent <= self.TOLERANCIA_VALOR_PERCENT:
            return 100.0
        elif diff_percent <= 5:
            return 90.0
        elif diff_percent <= 10:
            return 70.0
        elif diff_percent <= 20:
            return 50.0
        elif diff_percent <= 30:
            return 30.0
        else:
            return 0.0

    def _score_data(self, data_extrato, data_vencimento, data_pagamento) -> float:
        """
        Calcula score de matching de data (0-100)
        Prioriza data de pagamento (se existir), senão vencimento
        """
        # Se fatura já tem data de pagamento, compara com ela
        if data_pagamento:
            data_ref = data_pagamento
        else:
            data_ref = data_vencimento

        # Diferença em dias
        diff_dias = abs((data_extrato - data_ref).days)

        if diff_dias == 0:
            return 100.0
        elif diff_dias <= 1:
            return 90.0
        elif diff_dias <= self.TOLERANCIA_DIAS:
            return 80.0
        elif diff_dias <= 10:
            return 60.0
        elif diff_dias <= 15:
            return 40.0
        elif diff_dias <= 30:
            return 20.0
        else:
            return 0.0

    def _score_descricao(self, desc_extrato: str, fornecedor: str, desc_fatura: str) -> float:
        """
        Calcula score de matching de descrição usando fuzzy matching
        """
        desc_extrato = self._normalizar_texto(desc_extrato)
        fornecedor = self._normalizar_texto(fornecedor)
        desc_fatura = self._normalizar_texto(desc_fatura)

        # Testa match com fornecedor
        score_fornecedor = fuzz.partial_ratio(desc_extrato, fornecedor)

        # Testa match com descrição da fatura
        score_desc = fuzz.partial_ratio(desc_extrato, desc_fatura)

        # Retorna o maior score
        return max(score_fornecedor, score_desc)

    def _normalizar_texto(self, texto: str) -> str:
        """Normaliza texto para matching"""
        if not texto:
            return ""

        # Uppercase
        texto = texto.upper()

        # Remove acentos
        import unicodedata
        texto = unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('ASCII')

        # Remove pontuação e espaços extras
        texto = re.sub(r'[^\w\s]', ' ', texto)
        texto = ' '.join(texto.split())

        return texto

    def _detalhar_match(self, extrato, fatura, score: float) -> str:
        """Gera texto explicativo do match"""
        detalhes = []

        # Valor
        valor_ext = abs(extrato.valor)
        valor_fat = fatura.valor_original
        diff_valor = abs(valor_ext - valor_fat)
        if diff_valor < 0.01:
            detalhes.append("Valores idênticos")
        else:
            detalhes.append(f"Diferença de valor: R$ {diff_valor:.2f}")

        # Data
        data_ref = fatura.data_pagamento if fatura.data_pagamento else fatura.data_vencimento
        diff_dias = abs((extrato.data_lancamento - data_ref).days)
        if diff_dias == 0:
            detalhes.append("Datas coincidem")
        else:
            detalhes.append(f"Diferença de {diff_dias} dias")

        return " | ".join(detalhes)

    def conciliar_automatico(self, extratos: List, faturas: List) -> Dict:
        """
        Executa conciliação automática em lote

        Args:
            extratos: Lista de ExtratoBancario não conciliados
            faturas: Lista de Faturas pendentes

        Returns:
            Dict com estatísticas
        """
        from modules.finance.bank_models import Conciliacao

        stats = {
            'total_extratos': len(extratos),
            'total_faturas': len(faturas),
            'conciliados': 0,
            'sugestoes': 0,
            'sem_match': 0
        }

        for extrato in extratos:
            # Só concilia débitos (saídas)
            if extrato.valor >= 0:
                continue

            # Busca matches
            matches = self.buscar_matches(extrato, faturas, modo='auto')

            if matches and matches[0]['score'] >= self.LIMIAR_AUTO_MATCH:
                # Match forte - concilia automaticamente
                melhor_match = matches[0]
                fatura = melhor_match['fatura']

                # Cria conciliação
                conciliacao = Conciliacao(
                    extrato_id=extrato.id,
                    fatura_id=fatura.id,
                    valor_conciliado=abs(extrato.valor),
                    tipo_match='AUTO',
                    score_match=melhor_match['score'],
                    observacoes=melhor_match['detalhes']
                )
                self.session.add(conciliacao)

                # Atualiza status
                extrato.conciliado = True
                fatura.valor_pago += abs(extrato.valor)

                if fatura.valor_pago >= fatura.valor_original:
                    fatura.status = 'PAGA'
                    fatura.data_pagamento = extrato.data_lancamento
                else:
                    fatura.status = 'PARCIAL'

                stats['conciliados'] += 1

            elif matches and matches[0]['score'] >= self.LIMIAR_SUGESTAO:
                # Match fraco - apenas sugestão
                stats['sugestoes'] += 1
            else:
                stats['sem_match'] += 1

        self.session.commit()

        return stats

    def desfazer_conciliacao(self, conciliacao_id: int) -> bool:
        """
        Desfaz uma conciliação (para correções)

        Args:
            conciliacao_id: ID da conciliação

        Returns:
            True se sucesso, False se erro
        """
        from modules.finance.bank_models import Conciliacao

        try:
            conciliacao = self.session.query(Conciliacao).get(conciliacao_id)

            if not conciliacao:
                return False

            # Atualiza extrato
            conciliacao.extrato.conciliado = False

            # Atualiza fatura
            fatura = conciliacao.fatura
            fatura.valor_pago -= conciliacao.valor_conciliado

            if fatura.valor_pago <= 0:
                fatura.status = 'PENDENTE'
                fatura.data_pagamento = None
            elif fatura.valor_pago < fatura.valor_original:
                fatura.status = 'PARCIAL'

            # Remove conciliação
            self.session.delete(conciliacao)
            self.session.commit()

            return True

        except Exception as e:
            self.session.rollback()
            print(f"Erro ao desfazer conciliação: {e}")
            return False

    def criar_conciliacao_manual(self, extrato_id: int, fatura_id: int,
                                  valor: float, observacoes: str = "") -> bool:
        """
        Cria conciliação manual

        Args:
            extrato_id: ID do extrato
            fatura_id: ID da fatura
            valor: Valor a conciliar
            observacoes: Observações opcionais

        Returns:
            True se sucesso, False se erro
        """
        from modules.finance.bank_models import Conciliacao, ExtratoBancario, Fatura

        try:
            extrato = self.session.query(ExtratoBancario).get(extrato_id)
            fatura = self.session.query(Fatura).get(fatura_id)

            if not extrato or not fatura:
                return False

            # Cria conciliação
            conciliacao = Conciliacao(
                extrato_id=extrato_id,
                fatura_id=fatura_id,
                valor_conciliado=valor,
                tipo_match='MANUAL',
                observacoes=observacoes
            )
            self.session.add(conciliacao)

            # Atualiza status
            extrato.conciliado = True
            fatura.valor_pago += valor

            if fatura.valor_pago >= fatura.valor_original:
                fatura.status = 'PAGA'
                fatura.data_pagamento = extrato.data_lancamento
            else:
                fatura.status = 'PARCIAL'

            self.session.commit()
            return True

        except Exception as e:
            self.session.rollback()
            print(f"Erro ao criar conciliação manual: {e}")
            return False
