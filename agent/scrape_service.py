import hashlib
import time
from datetime import datetime, date
from typing import Any, Dict, List

from modules.scrapers.pncp_client import PNCPClient
from modules.core.opportunity_collector import collect_opportunities
from modules.utils.logging_config import get_logger

# Modalidades alvo (PNCP): 6, 8, 12 => Pregao/Dispensa/Emergencial
_MODALIDADE_KEYWORDS = ("PREG", "DISPENSA", "EMERG")

logger = get_logger(__name__)


def _to_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except Exception:
        return None


def _prazo_aberto(data_encerramento: Any, hoje: date) -> bool:
    """Retorna True se nao ha data ou se o prazo ainda nao acabou."""
    dt = _to_datetime(data_encerramento)
    if not dt:
        # Scrapers de diario quase nunca trazem data; assume aberto.
        return True
    return dt.date() >= hoje


def _modalidade_valida(modalidade: str) -> bool:
    if not modalidade:
        return False
    mod_norm = modalidade.upper()
    return any(flag in mod_norm for flag in _MODALIDADE_KEYWORDS)


def _hash_licitacao(data: Dict[str, Any]) -> str:
    base = data.get("pncp_id") or f"{data.get('orgao','')}-{data.get('objeto','')}-{data.get('data_publicacao','')}"
    return hashlib.sha1(base.encode("utf-8", errors="ignore")).hexdigest()


def _normalize_entry(raw: Dict[str, Any], origem: str) -> Dict[str, Any]:
    """Uniformiza campos esperados pelo agente."""
    normalized = {
        "pncp_id": raw.get("pncp_id"),
        "orgao": raw.get("orgao"),
        "uf": raw.get("uf"),
        "modalidade": raw.get("modalidade"),
        "data_publicacao": _to_datetime(raw.get("data_publicacao")),
        "data_sessao": _to_datetime(raw.get("data_sessao")),
        "data_inicio_proposta": _to_datetime(raw.get("data_inicio_proposta")),
        "data_encerramento_proposta": _to_datetime(raw.get("data_encerramento_proposta")),
        "objeto": raw.get("objeto") or "",
        "link": raw.get("link"),
        "origem": origem,
        "itens": raw.get("itens") or [],
        "texto_edital": raw.get("texto_edital") or "",
    }
    normalized["dedupe_key"] = normalized["pncp_id"] or _hash_licitacao(normalized)
    return normalized


def _retry(fn, *, attempts=3, backoff=1.5, label=""):
    for idx in range(1, attempts + 1):
        try:
            return fn()
        except Exception as exc:
            if idx == attempts:
                logger.warning("Falha definitiva em %s: %s", label or fn.__name__, exc)
                raise
            wait = round(backoff * idx, 2)
            logger.warning("Erro em %s (tentativa %s/%s): %s. Retentando em %ss", label or fn.__name__, idx, attempts, exc, wait)
            time.sleep(wait)


def coletar_licitacoes(filtros_base: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
    """
    Coleta licitacoes do PNCP e diarios externos, aplicando dedupe e regra de prazo.
    Retorna lista de dicts normalizados.
    """
    filtros = filtros_base or {}
    hoje = date.today()

    pncp_client = PNCPClient()
    termos_positivos = filtros.get("termos_positivos") or getattr(pncp_client, "TERMOS_POSITIVOS_PADRAO", [])
    termos_negativos = filtros.get("termos_negativos")
    estados = filtros.get("estados") or ["RN", "PB", "PE", "AL", "CE", "BA"]
    dias_busca = filtros.get("dias") or 30
    fontes = filtros.get("fontes")

    coletados = collect_opportunities(
        dias=dias_busca,
        estados=estados,
        fontes=fontes,
        termos_positivos=termos_positivos,
        termos_negativos=termos_negativos,
        apenas_abertas=True,
    )

    consolidados_norm: List[Dict[str, Any]] = []
    for lic in coletados:
        origem = lic.get("origem") or lic.get("fonte") or "EXTERNO"
        lic_norm = _normalize_entry(lic, origem=str(origem))
        if not lic_norm["objeto"]:
            continue

        # Filtro de modalidade é confiável no PNCP; em diários, o campo pode não existir.
        if str(origem).upper() == "PNCP" and not _modalidade_valida(lic_norm.get("modalidade", "")):
            continue

        if not _prazo_aberto(lic_norm.get("data_encerramento_proposta"), hoje):
            continue

        consolidados_norm.append(lic_norm)

    # --- Dedupe ---
    vistos = set()
    consolidados: List[Dict[str, Any]] = []
    for lic in consolidados_norm:
        key = lic.get("dedupe_key")
        if not key or key in vistos:
            continue
        vistos.add(key)
        lic.pop("dedupe_key", None)
        consolidados.append(lic)

    return consolidados
