"""
Utilitário central de logging.
- Usa nível vindo de LOG_LEVEL (default INFO).
- Garante que não criamos múltiplos handlers duplicados.
"""
import logging
import os
from typing import Optional

_LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
_FORMAT = "%(asctime)s [%(levelname)s] %(name)s - %(message)s"


def get_logger(name: str, level: Optional[str] = None) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    log_level = getattr(logging, (level or _LOG_LEVEL), logging.INFO)
    logger.setLevel(log_level)

    handler = logging.StreamHandler()
    handler.setLevel(log_level)
    handler.setFormatter(logging.Formatter(_FORMAT))

    logger.addHandler(handler)
    logger.propagate = False
    return logger
