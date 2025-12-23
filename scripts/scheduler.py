#!/usr/bin/env python3
"""
Scheduler de Busca Automática de Licitações
Executa buscas em horários programados e envia notificações

Uso:
    python scripts/scheduler.py          # Modo contínuo (daemon)
    python scripts/scheduler.py --once   # Executa uma vez e sai
"""

import sys
import os
import time
import argparse
from datetime import datetime

# Adiciona raiz do projeto ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.database.database import init_db, get_session, Configuracao
from modules.finance import init_finance_db, init_finance_historico_db
from modules.core.search_engine import SearchEngine
from modules.core.opportunity_collector import coletar_todas_oportunidades
from modules.utils.deadline_alerts import executar_verificacao_diaria
from modules.utils.logging_config import get_logger

logger = get_logger("scheduler")

# Horários de busca (formato 24h)
HORARIOS_BUSCA = ["08:00", "14:00"]

# Horário de verificação de prazos
HORARIO_VERIFICACAO_PRAZO = "09:00"


def executar_busca_completa():
    """Executa busca completa em todas as fontes"""
    logger.info("=" * 60)
    logger.info("INICIANDO BUSCA AUTOMÁTICA")
    logger.info(f"Horário: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)
    
    try:
        # Inicializa bancos
        init_db()
        init_finance_db()
        init_finance_historico_db()
        
        # Busca configurações
        session = get_session()
        config = session.query(Configuracao).filter_by(chave='dias_busca').first()
        dias_busca = int(config.valor) if config and config.valor else 60
        session.close()
        
        # Coleta oportunidades
        logger.info(f"Buscando licitações dos últimos {dias_busca} dias...")
        resultados = coletar_todas_oportunidades(
            dias_busca=dias_busca,
            estados=['RN', 'PB', 'PE', 'AL'],
            fontes=['pncp', 'femurn', 'famup', 'amupe', 'ama']
        )
        
        logger.info(f"Total de {len(resultados)} licitações encontradas")
        
        # Processa e salva
        if resultados:
            engine = SearchEngine()
            details = engine.run_search_pipeline(
                resultados, 
                return_details=True, 
                send_immediate_alerts=True  # Envia alertas
            )
            novos = details.get('novos', 0) if details else 0
            logger.info(f"Novas licitações importadas: {novos}")
        
        logger.info("Busca automática concluída com sucesso!")
        return True
        
    except Exception as e:
        logger.error(f"Erro na busca automática: {e}")
        import traceback
        traceback.print_exc()
        return False


def verificar_horario(horario_alvo: str) -> bool:
    """Verifica se o horário atual corresponde ao alvo (com tolerância de 1 minuto)"""
    agora = datetime.now().strftime("%H:%M")
    return agora == horario_alvo


def modo_daemon():
    """Executa em modo daemon (contínuo)"""
    logger.info("Scheduler iniciado em modo DAEMON")
    logger.info(f"Horários de busca: {', '.join(HORARIOS_BUSCA)}")
    logger.info(f"Horário de verificação de prazo: {HORARIO_VERIFICACAO_PRAZO}")
    
    ultima_busca = None
    ultima_verificacao = None
    
    while True:
        agora = datetime.now()
        hora_atual = agora.strftime("%H:%M")
        
        # Verifica horários de busca
        for horario in HORARIOS_BUSCA:
            if hora_atual == horario and ultima_busca != hora_atual:
                logger.info(f"Horário de busca atingido: {horario}")
                executar_busca_completa()
                ultima_busca = hora_atual
        
        # Verifica horário de alerta de prazo
        if hora_atual == HORARIO_VERIFICACAO_PRAZO and ultima_verificacao != hora_atual:
            logger.info(f"Horário de verificação de prazo: {HORARIO_VERIFICACAO_PRAZO}")
            executar_verificacao_diaria()
            ultima_verificacao = hora_atual
        
        # Aguarda 30 segundos antes de verificar novamente
        time.sleep(30)


def modo_unico():
    """Executa uma vez e sai"""
    logger.info("Scheduler em modo ÚNICO (--once)")
    
    # Executa busca
    executar_busca_completa()
    
    # Verifica prazos
    executar_verificacao_diaria()
    
    logger.info("Execução única concluída")


def main():
    parser = argparse.ArgumentParser(description="Scheduler de busca de licitações")
    parser.add_argument("--once", action="store_true", help="Executa uma vez e sai")
    parser.add_argument("--busca", action="store_true", help="Executa apenas a busca")
    parser.add_argument("--prazo", action="store_true", help="Executa apenas verificação de prazo")
    args = parser.parse_args()
    
    if args.busca:
        executar_busca_completa()
    elif args.prazo:
        executar_verificacao_diaria()
    elif args.once:
        modo_unico()
    else:
        modo_daemon()


if __name__ == "__main__":
    main()
