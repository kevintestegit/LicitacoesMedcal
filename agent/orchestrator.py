from typing import Any, Dict, List

from agent.scrape_service import coletar_licitacoes
from agent.analyze_service import analisar_licitacao
from agent.decision.policy import aplicar_politica, PolicyResult
from modules.utils.logging_config import get_logger

logger = get_logger(__name__)


def executar(filtros_base: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
    """
    Executa pipeline completo em memoria (coleta -> analise -> politica).
    Nao persiste no banco; usado pelo runner.
    """
    resultados = []
    logger.info("Iniciando coleta (filtros=%s)", filtros_base)
    licitacoes = coletar_licitacoes(filtros_base)
    for lic in licitacoes:
        analise = analisar_licitacao(lic, lic.get("texto_edital", ""))
        politica: PolicyResult = aplicar_politica(lic, analise)
        resultados.append({"licitacao": lic, "analise": analise, "politica": politica})
    logger.info("Pipeline concluido: %s licitacoes processadas", len(resultados))
    return resultados
