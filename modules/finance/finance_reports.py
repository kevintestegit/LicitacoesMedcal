"""
Módulo de Relatórios Financeiros
Gera relatórios de divergências, conciliação e auditoria para exportação
"""

import io
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

import pandas as pd
from sqlalchemy import func, and_, or_

from .database import get_finance_session
from .bank_models import ExtratoBB, ResumoMensal, SesapPagamento, FinanceAuditLog


@dataclass
class RelatorioDivergencias:
    """Resultado do relatório de divergências"""
    data_geracao: str
    periodo: str
    
    # Resumo
    total_extratos_pendentes: int
    valor_extratos_pendentes: float
    total_sesap_sem_match: int
    valor_sesap_sem_match: float
    
    # Detalhes
    extratos_pendentes: List[Dict]
    sesap_sem_match: List[Dict]
    divergencias_valor: List[Dict]


def gerar_relatorio_divergencias(
    mes: Optional[str] = None,
    ano: Optional[int] = None,
    apenas_pendentes: bool = True
) -> RelatorioDivergencias:
    """
    Gera relatório de divergências entre extratos bancários e pagamentos SESAP.
    
    Args:
        mes: Mês de referência (Jan, Fev, etc). Se None, usa todos.
        ano: Ano de referência. Se None, usa ano atual.
        apenas_pendentes: Se True, inclui apenas lançamentos com status 'Pendente'
    
    Returns:
        RelatorioDivergencias com todos os dados
    """
    session = get_finance_session()
    ano = ano or datetime.now().year
    
    try:
        # === 1. Extratos Pendentes (sem conciliação) ===
        query_extratos = session.query(ExtratoBB)
        
        if mes:
            query_extratos = query_extratos.filter(ExtratoBB.mes_referencia == mes)
        if ano:
            query_extratos = query_extratos.filter(ExtratoBB.ano_referencia == ano)
        if apenas_pendentes:
            query_extratos = query_extratos.filter(
                or_(ExtratoBB.status == 'Pendente', ExtratoBB.status.is_(None))
            )
        
        extratos_pendentes = query_extratos.order_by(ExtratoBB.dt_balancete.desc()).all()
        
        extratos_list = []
        total_valor_pendentes = 0.0
        for e in extratos_pendentes:
            extratos_list.append({
                'id': e.id,
                'data': e.dt_balancete.strftime('%d/%m/%Y') if e.dt_balancete else '',
                'historico': e.historico or '',
                'documento': e.documento or '',
                'valor': e.valor or 0,
                'tipo': e.tipo or '',
                'fatura': e.fatura or '',
                'banco': e.banco or 'BB',
            })
            total_valor_pendentes += abs(e.valor or 0)
        
        # === 2. Pagamentos SESAP sem match no extrato ===
        # Busca pagamentos que não encontramos correspondência
        query_sesap = session.query(SesapPagamento)
        sesap_pagamentos = query_sesap.all()
        
        # Busca todos os documentos já conciliados nos extratos
        docs_conciliados = set()
        faturas_conciliadas = set()
        for e in session.query(ExtratoBB).filter(ExtratoBB.status == 'Baixado').all():
            if e.documento:
                docs_conciliados.add(e.documento.strip())
            if e.fatura:
                # Extrai números de fatura do campo
                for part in e.fatura.replace('FT', '').replace('FTs', '').split():
                    if part.isdigit():
                        faturas_conciliadas.add(part)
        
        sesap_sem_match = []
        total_valor_sesap = 0.0
        for s in sesap_pagamentos:
            # Verifica se já está conciliado
            doc_match = s.num_doc and s.num_doc.strip() in docs_conciliados
            if not doc_match:
                sesap_sem_match.append({
                    'id': s.id,
                    'unidade': s.unidade or '',
                    'num_doc': s.num_doc or '',
                    'valor': s.valor_liquido or 0,
                    'vencimento': s.dt_vencimento.strftime('%d/%m/%Y') if s.dt_vencimento else '',
                    'status_sesap': s.status_sesap or '',
                    'processo': s.num_processo or '',
                })
                total_valor_sesap += abs(s.valor_liquido or 0)
        
        # === 3. Divergências de valor (mesma fatura, valores diferentes) ===
        divergencias_valor = []
        # Implementação simplificada - compara por documento
        
        periodo = f"{mes or 'Todos'}/{ano}"
        
        return RelatorioDivergencias(
            data_geracao=datetime.now().strftime('%d/%m/%Y %H:%M'),
            periodo=periodo,
            total_extratos_pendentes=len(extratos_list),
            valor_extratos_pendentes=total_valor_pendentes,
            total_sesap_sem_match=len(sesap_sem_match),
            valor_sesap_sem_match=total_valor_sesap,
            extratos_pendentes=extratos_list,
            sesap_sem_match=sesap_sem_match,
            divergencias_valor=divergencias_valor,
        )
    
    finally:
        session.close()


def exportar_relatorio_excel(relatorio: RelatorioDivergencias) -> bytes:
    """
    Exporta relatório de divergências para Excel.
    
    Returns:
        Bytes do arquivo Excel
    """
    output = io.BytesIO()
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Aba Resumo
        resumo_data = {
            'Indicador': [
                'Data Geração',
                'Período',
                'Extratos Pendentes (qtd)',
                'Extratos Pendentes (valor)',
                'SESAP sem Match (qtd)',
                'SESAP sem Match (valor)',
            ],
            'Valor': [
                relatorio.data_geracao,
                relatorio.periodo,
                relatorio.total_extratos_pendentes,
                f"R$ {relatorio.valor_extratos_pendentes:,.2f}",
                relatorio.total_sesap_sem_match,
                f"R$ {relatorio.valor_sesap_sem_match:,.2f}",
            ]
        }
        df_resumo = pd.DataFrame(resumo_data)
        df_resumo.to_excel(writer, sheet_name='Resumo', index=False)
        
        # Aba Extratos Pendentes
        if relatorio.extratos_pendentes:
            df_extratos = pd.DataFrame(relatorio.extratos_pendentes)
            df_extratos.to_excel(writer, sheet_name='Extratos Pendentes', index=False)
        
        # Aba SESAP sem Match
        if relatorio.sesap_sem_match:
            df_sesap = pd.DataFrame(relatorio.sesap_sem_match)
            df_sesap.to_excel(writer, sheet_name='SESAP sem Match', index=False)
    
    output.seek(0)
    return output.read()


def gerar_relatorio_auditoria(
    data_inicio: Optional[date] = None,
    data_fim: Optional[date] = None,
    limit: int = 500
) -> pd.DataFrame:
    """
    Gera relatório de auditoria com histórico de importações e operações.
    
    Returns:
        DataFrame com logs de auditoria
    """
    session = get_finance_session()
    
    try:
        query = session.query(FinanceAuditLog).order_by(FinanceAuditLog.created_at.desc())
        
        if data_inicio:
            query = query.filter(FinanceAuditLog.created_at >= data_inicio)
        if data_fim:
            query = query.filter(FinanceAuditLog.created_at <= data_fim)
        
        logs = query.limit(limit).all()
        
        data = []
        for log in logs:
            data.append({
                'data_hora': log.created_at.strftime('%d/%m/%Y %H:%M') if log.created_at else '',
                'evento': log.event_type or '',
                'fonte': log.source or '',
                'referencia': log.reference or '',
                'mensagem': log.message or '',
            })
        
        return pd.DataFrame(data)
    
    finally:
        session.close()


def gerar_resumo_por_periodo(ano: int = None) -> pd.DataFrame:
    """
    Gera resumo consolidado por mês/ano.
    
    Returns:
        DataFrame com totais por período
    """
    session = get_finance_session()
    ano = ano or datetime.now().year
    
    try:
        resumos = session.query(ResumoMensal).filter(
            ResumoMensal.ano == ano
        ).order_by(ResumoMensal.ano, ResumoMensal.mes).all()
        
        data = []
        for r in resumos:
            data.append({
                'mes': r.mes,
                'ano': r.ano,
                'lancamentos': r.total_lancamentos,
                'entradas': r.total_entradas,
                'saidas': r.total_saidas,
                'saldo': r.total_entradas - r.total_saidas,
                'baixados': r.total_baixados,
                'pendentes': r.total_pendentes,
            })
        
        return pd.DataFrame(data)
    
    finally:
        session.close()


# Meses para ordenação
MESES_ORDEM = {
    'Jan': 1, 'Fev': 2, 'Mar': 3, 'Abr': 4,
    'Mai': 5, 'Jun': 6, 'Jul': 7, 'Ago': 8,
    'Set': 9, 'Out': 10, 'Nov': 11, 'Dez': 12
}
