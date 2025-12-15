"""
Módulo de Gestão de Extratos Bancários - Banco do Brasil
Versão simplificada focada no extrato padrão BB
"""

from .bank_models import ExtratoBB, ResumoMensal, SesapPagamento
from .extrato_parser import ExtratoBBParser, importar_extrato_bb, processar_texto_extrato
from .historico_importer import importar_extrato_historico
from .sesap_importer import importar_planilha_sesap
from .database import (
    init_finance_db,
    init_finance_historico_db,
    get_finance_session,
    get_finance_historico_session,
)

__all__ = [
    'ExtratoBB',
    'ResumoMensal',
    'SesapPagamento',
    'ExtratoBBParser',
    'importar_extrato_bb',
    'processar_texto_extrato',
    'importar_extrato_historico',
    'importar_planilha_sesap',
    'init_finance_db',
    'init_finance_historico_db',
    'get_finance_session',
    'get_finance_historico_session',
]
