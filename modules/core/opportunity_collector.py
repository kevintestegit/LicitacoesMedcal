import concurrent.futures
import hashlib
from typing import Any, Dict, Iterable, List, Tuple

from modules.scrapers.pncp_client import PNCPClient
from modules.scrapers.external_scrapers import (
    FemurnScraper,
    FamupScraper,
    AmupeScraper,
    AmaScraper,
    MaceioScraper,
    MaceioInvesteScraper,
    MaceioSaudeScraper,
    BncScraper,
)
from modules.utils.logging_config import get_logger

logger = get_logger(__name__)


SCRAPERS_MAP: Dict[str, Tuple[type, str]] = {
    "femurn": (FemurnScraper, "FEMURN"),
    "famup": (FamupScraper, "FAMUP"),
    "amupe": (AmupeScraper, "AMUPE"),
    "ama": (AmaScraper, "AMA"),
    "maceio": (MaceioScraper, "Maceió"),
    "maceio_investe": (MaceioInvesteScraper, "Maceió Investe"),
    "maceio_saude": (MaceioSaudeScraper, "Maceió Saúde"),
    "bnc": (BncScraper, "BNC"),
}


def _sha1(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()


def _compute_source_key(res: Dict[str, Any]) -> str:
    pncp_id = (res.get("pncp_id") or "").strip()
    if pncp_id:
        return f"pncp:{pncp_id}"
    link = (res.get("link") or "").strip()
    if link:
        return f"link:{_sha1(link)}"
    base = f"{res.get('orgao','')}-{res.get('uf','')}-{res.get('objeto','')}-{res.get('data_publicacao','')}"
    return f"hash:{_sha1(base)}"


def _ensure_stable_id(res: Dict[str, Any]) -> None:
    if (res.get("pncp_id") or "").strip():
        return
    key = _compute_source_key(res)
    res["pncp_id"] = f"EXT-{_sha1(key)}"


def _is_error_entry(res: Dict[str, Any]) -> bool:
    pncp_id = (res.get("pncp_id") or "").upper()
    if pncp_id.endswith("-ERROR"):
        return True
    objeto = (res.get("objeto") or "").lower()
    return "nao foi possivel" in objeto or "não foi possível" in objeto


def collect_opportunities(
    *,
    dias: int = 60,
    estados: List[str] | None = None,
    fontes: List[str] | None = None,
    termos_positivos: List[str] | None = None,
    termos_negativos: List[str] | None = None,
    apenas_abertas: bool = True,
) -> List[Dict[str, Any]]:
    """
    Coleta oportunidades (PNCP + fontes externas) em um formato compatível com o pipeline do sistema.

    - Gera `pncp_id` estável para entradas externas sem ID, evitando dedupe incorreto.
    - Remove entradas de erro dos scrapers (ex.: PDF indisponível).
    """
    estados = estados or ["RN", "PB", "PE", "AL"]
    resultados_raw: List[Dict[str, Any]] = []

    client = PNCPClient()

    usar_pncp = fontes is None or "pncp" in fontes
    scrapers_ativos: List[Tuple[type, str]] = []
    if fontes is None:
        scrapers_ativos = list(SCRAPERS_MAP.values())
    else:
        for key, value in SCRAPERS_MAP.items():
            if key in fontes:
                scrapers_ativos.append(value)

    def fetch_pncp():
        try:
            res = client.buscar_oportunidades(
                dias_busca=dias,
                estados=estados,
                termos_positivos=termos_positivos or client.TERMOS_POSITIVOS_PADRAO,
                termos_negativos=termos_negativos,
                apenas_abertas=apenas_abertas,
            )
            for r in res or []:
                r.setdefault("fonte", "PNCP")
            return res or []
        except Exception as exc:
            logger.warning("Erro PNCP: %s", exc, exc_info=True)
            return []

    def fetch_external(ScraperCls: type, name: str):
        try:
            scraper = ScraperCls()
            termos_pos_externos = termos_positivos or getattr(client, "TERMOS_PRIORITARIOS", None) or client.TERMOS_POSITIVOS_PADRAO
            termos_neg_externos = termos_negativos or client.TERMOS_NEGATIVOS_PADRAO
            if name == "BNC":
                res = scraper.buscar_oportunidades(
                    termos_busca=termos_pos_externos,
                    termos_negativos=termos_neg_externos,
                    estados=estados,
                )
            else:
                res = scraper.buscar_oportunidades(
                    termos_busca=termos_pos_externos,
                    termos_negativos=termos_neg_externos,
                )
            for r in res or []:
                r.setdefault("fonte", name)
                r.setdefault("origem", name)
            return res or []
        except Exception as exc:
            logger.warning("Erro %s: %s", name, exc, exc_info=True)
            return []

    total_fontes = (1 if usar_pncp else 0) + len(scrapers_ativos)
    logger.info("Disparando coleta em %s fonte(s) (dias=%s, estados=%s, fontes=%s)", total_fontes, dias, estados, fontes or "TODAS")

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = []
        if usar_pncp:
            futures.append(executor.submit(fetch_pncp))
        for ScraperCls, name in scrapers_ativos:
            futures.append(executor.submit(fetch_external, ScraperCls, name))

        for future in concurrent.futures.as_completed(futures):
            try:
                res = future.result() or []
                resultados_raw.extend(res)
            except Exception as exc:
                logger.warning("Erro fatal em thread de coleta: %s", exc, exc_info=True)

    # Dedup e saneamento mínimo (IDs estáveis)
    vistos = set()
    consolidados: List[Dict[str, Any]] = []
    for res in resultados_raw:
        if not isinstance(res, dict) or _is_error_entry(res):
            continue
        _ensure_stable_id(res)
        key = _compute_source_key(res)
        if key in vistos:
            continue
        vistos.add(key)
        consolidados.append(res)

    return consolidados


def prepare_results_for_pipeline(resultados_raw: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Aplica saneamento/dedupe/IDs estáveis + ETL em resultados já coletados.
    Útil para pontos do dashboard que chamam scrapers diretamente.
    """
    vistos = set()
    consolidados: List[Dict[str, Any]] = []
    for res in resultados_raw or []:
        if not isinstance(res, dict) or _is_error_entry(res):
            continue
        _ensure_stable_id(res)
        key = _compute_source_key(res)
        if key in vistos:
            continue
        vistos.add(key)
        consolidados.append(res)
    
    # Aplica transformações ETL
    try:
        from modules.etl import process_licitacoes
        consolidados = process_licitacoes(consolidados)
        logger.info("ETL aplicado: %s registros processados", len(consolidados))
    except Exception as e:
        logger.warning("Erro ao aplicar ETL, continuando sem transformações: %s", e)
    
    return consolidados

