from typing import Optional, Dict, Any
from datetime import datetime

from .database import get_finance_session
from .bank_models import FinanceAuditLog


def log_finance_event(
    session,
    event_type: str,
    message: str,
    source: Optional[str] = None,
    reference: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
):
    """
    Persiste uma linha de auditoria financeira de forma enxuta.
    Aceita sessão já existente para não abrir/fechar transação extra.
    """
    try:
        log = FinanceAuditLog(
            event_type=event_type,
            message=message,
            source=source,
            reference=reference,
            meta=meta,
            created_at=datetime.now(),
        )
        session.add(log)
        session.flush()
    except Exception:
        # Auditoria não pode quebrar fluxo principal; falha silenciosa.
        session.rollback()


def log_finance_event_autocommit(
    event_type: str,
    message: str,
    source: Optional[str] = None,
    reference: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
):
    """
    Atalho seguro que abre sessão própria. Útil para caminhos fora de transações.
    """
    session = get_finance_session()
    try:
        log_finance_event(session, event_type, message, source, reference, meta)
        session.commit()
    finally:
        session.close()
