"""
Módulo de Alertas de Prazo
Verifica licitações fixadas com prazo próximo e envia notificações
"""

import json
from datetime import datetime, timedelta
from typing import List, Dict, Any

from modules.database.database import get_session, Licitacao, Configuracao
from modules.utils.notifications import WhatsAppNotifier
from modules.utils.logging_config import get_logger

logger = get_logger(__name__)

# Dias de antecedência para considerar urgente
DIAS_URGENTE = 2


def verificar_prazos_urgentes() -> List[Dict[str, Any]]:
    """
    Busca licitações fixadas (status='Salva') com prazo de encerramento
    nos próximos DIAS_URGENTE dias.
    
    Returns:
        Lista de licitações urgentes
    """
    session = get_session()
    try:
        hoje = datetime.now().date()
        limite = hoje + timedelta(days=DIAS_URGENTE)
        
        # Busca licitações fixadas com prazo próximo
        urgentes = session.query(Licitacao).filter(
            Licitacao.status == 'Salva',
            Licitacao.data_encerramento_proposta != None,
            Licitacao.data_encerramento_proposta >= hoje,
            Licitacao.data_encerramento_proposta <= limite
        ).order_by(Licitacao.data_encerramento_proposta).all()
        
        resultado = []
        for lic in urgentes:
            dias_restantes = (lic.data_encerramento_proposta.date() - hoje).days if isinstance(lic.data_encerramento_proposta, datetime) else (lic.data_encerramento_proposta - hoje).days
            resultado.append({
                'id': lic.id,
                'orgao': lic.orgao,
                'uf': lic.uf,
                'objeto': lic.objeto,
                'modalidade': lic.modalidade,
                'link': lic.link,
                'data_encerramento': lic.data_encerramento_proposta,
                'dias_restantes': dias_restantes,
                'categoria': getattr(lic, 'categoria', None)
            })
        
        logger.info(f"Encontradas {len(resultado)} licitações urgentes (prazo <= {DIAS_URGENTE} dias)")
        return resultado
        
    finally:
        session.close()


def enviar_alerta_prazo(licitacoes_urgentes: List[Dict[str, Any]]) -> bool:
    """
    Envia notificação WhatsApp para licitações com prazo urgente.
    
    Args:
        licitacoes_urgentes: Lista de licitações urgentes
    
    Returns:
        True se enviou com sucesso
    """
    if not licitacoes_urgentes:
        return False
    
    session = get_session()
    try:
        # Busca contatos WhatsApp
        config_contacts = session.query(Configuracao).filter_by(chave='whatsapp_contacts').first()
        if not config_contacts or not config_contacts.valor:
            logger.warning("WhatsApp não configurado para alertas de prazo")
            return False
        
        contacts_list = json.loads(config_contacts.valor)
        if not contacts_list:
            return False
        
        # Monta mensagem
        linhas = ["⚠️ *ALERTA DE PRAZO - MEDCAL*", ""]
        linhas.append(f"📅 {len(licitacoes_urgentes)} licitações com prazo próximo:")
        linhas.append("")
        
        for lic in licitacoes_urgentes[:10]:  # Máximo 10
            emoji_dias = "🔴" if lic['dias_restantes'] <= 1 else "🟡"
            orgao_curto = lic['orgao'][:30] + "..." if len(lic['orgao']) > 30 else lic['orgao']
            linhas.append(f"{emoji_dias} *{lic['dias_restantes']}d* - {orgao_curto} ({lic['uf']})")
            linhas.append(f"   🔗 {lic['link']}")
            linhas.append("")
        
        if len(licitacoes_urgentes) > 10:
            linhas.append(f"... e mais {len(licitacoes_urgentes) - 10} licitações")
        
        mensagem = "\n".join(linhas)
        
        # Envia para todos os contatos
        enviados = 0
        for contact in contacts_list:
            try:
                notifier = WhatsAppNotifier(contact.get('phone'), contact.get('apikey'))
                if notifier.enviar_mensagem(mensagem):
                    enviados += 1
            except Exception as e:
                logger.error(f"Erro ao enviar alerta para {contact.get('nome')}: {e}")
        
        logger.info(f"Alerta de prazo enviado para {enviados} contatos")
        return enviados > 0
        
    finally:
        session.close()


def executar_verificacao_diaria():
    """
    Função principal para verificação diária de prazos.
    Deve ser chamada pelo scheduler.
    """
    logger.info("Iniciando verificação diária de prazos...")
    
    urgentes = verificar_prazos_urgentes()
    
    if urgentes:
        logger.info(f"Encontradas {len(urgentes)} licitações urgentes")
        enviar_alerta_prazo(urgentes)
    else:
        logger.info("Nenhuma licitação com prazo urgente")
    
    return urgentes


def is_prazo_urgente(data_encerramento) -> bool:
    """
    Verifica se uma data de encerramento está dentro do prazo urgente.
    Usado pelo dashboard para mostrar badge.
    
    Args:
        data_encerramento: datetime ou date do encerramento
    
    Returns:
        True se prazo <= DIAS_URGENTE
    """
    if not data_encerramento:
        return False
    
    hoje = datetime.now().date()
    
    if isinstance(data_encerramento, datetime):
        data_enc = data_encerramento.date()
    else:
        data_enc = data_encerramento
    
    dias = (data_enc - hoje).days
    return 0 <= dias <= DIAS_URGENTE


def get_dias_restantes(data_encerramento) -> int:
    """
    Calcula dias restantes até o encerramento.
    
    Returns:
        Número de dias (negativo se já passou)
    """
    if not data_encerramento:
        return -999
    
    hoje = datetime.now().date()
    
    if isinstance(data_encerramento, datetime):
        data_enc = data_encerramento.date()
    else:
        data_enc = data_encerramento
    
    return (data_enc - hoje).days
