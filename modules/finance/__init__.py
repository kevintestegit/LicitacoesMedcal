"""
Módulo de Gestão Financeira e Conciliação Bancária
"""

# Lazy imports - importa apenas quando necessário para evitar dependências circulares
def __getattr__(name):
    if name == 'ContaBancaria':
        from .bank_models import ContaBancaria
        return ContaBancaria
    elif name == 'ExtratoBancario':
        from .bank_models import ExtratoBancario
        return ExtratoBancario
    elif name == 'Fatura':
        from .bank_models import Fatura
        return Fatura
    elif name == 'Conciliacao':
        from .bank_models import Conciliacao
        return Conciliacao
    elif name == 'ExtratoParser':
        from .extrato_parser import ExtratoParser
        return ExtratoParser
    elif name == 'ConciliadorFinanceiro':
        from .conciliador import ConciliadorFinanceiro
        return ConciliadorFinanceiro
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    'ExtratoBancario',
    'Fatura',
    'Conciliacao',
    'ContaBancaria',
    'ExtratoParser',
    'ConciliadorFinanceiro'
]
