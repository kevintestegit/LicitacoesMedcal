from typing import Any, Dict, List

from agent.scrape_service import coletar_licitacoes
from agent.analyze_service import analisar_licitacao
from agent.decision.policy import aplicar_politica, PolicyResult
from modules.utils.logging_config import get_logger

logger = get_logger(__name__)


def executar(filtros_base: Dict[str, Any] | None = None, persistir: bool = False) -> List[Dict[str, Any]]:
    """
    Executa pipeline completo (coleta -> analise -> politica).
    
    Args:
        filtros_base: Filtros de busca (termos, estados, dias, etc)
        persistir: Se True, usa SearchEngine para salvar no banco e enviar alertas
        
    Returns:
        Lista de dicts com licitacao, analise e politica
    """
    resultados = []
    logger.info("Iniciando coleta (filtros=%s, persistir=%s)", filtros_base, persistir)
    licitacoes = coletar_licitacoes(filtros_base)
    
    # Se persistir=True, usa SearchEngine para salvar e notificar
    if persistir:
        from modules.core.search_engine import SearchEngine
        engine = SearchEngine()
        # Converte para formato esperado pelo run_search_pipeline
        engine.run_search_pipeline(licitacoes, send_immediate_alerts=True)
        logger.info("Licitações persistidas via SearchEngine")
    
    for lic in licitacoes:
        analise = analisar_licitacao(lic, lic.get("texto_edital", ""))
        politica: PolicyResult = aplicar_politica(lic, analise)
        resultados.append({"licitacao": lic, "analise": analise, "politica": politica})
    logger.info("Pipeline concluido: %s licitacoes processadas", len(resultados))
    return resultados
