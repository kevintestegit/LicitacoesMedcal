from typing import Any, Dict, List

from modules.ai.semantic_filter import SemanticFilter
from modules.ai.improved_matcher import SemanticMatcher
from modules.ai.smart_analyzer import SmartAnalyzer
from modules.ai.eligibility_checker import EligibilityChecker


def _normalizar_matches(matches: List) -> List[Dict[str, Any]]:
    normalizados = []
    for prod, score in matches:
        normalizados.append(
            {
                "produto_id": getattr(prod, "id", None),
                "produto_nome": getattr(prod, "nome", ""),
                "score": float(score),
            }
        )
    return normalizados


def analisar_licitacao(licitacao: Dict[str, Any], texto_edital: str = "") -> Dict[str, Any]:
    """
    Combina filtro semantico, matcher de catalogo, analise de viabilidade e checagem de elegibilidade.
    """
    objeto = licitacao.get("objeto", "") if licitacao else ""

    try:
        filtro = SemanticFilter()
        relevante = filtro.is_relevant(objeto)
    except Exception as exc:
        print(f"[WARN] Filtro semantico indisponivel: {exc}")
        relevante = True

    try:
        matcher = SemanticMatcher()
        matches = matcher.find_matches(objeto)
    except Exception as exc:
        print(f"[WARN] Matcher indisponivel: {exc}")
        matches = []
    matches_norm = _normalizar_matches(matches)

    try:
        analyzer = SmartAnalyzer()
        viabilidade = analyzer.analisar_viabilidade(texto_edital or objeto)
    except Exception as exc:
        print(f"[WARN] Analisador IA indisponivel: {exc}")
        viabilidade = {
            "resumo_objeto": objeto[:200],
            "score_viabilidade": 0,
            "justificativa_score": f"Falha IA: {exc}",
            "pontos_atencao": [],
            "documentos_habilitacao": [],
            "red_flags": [],
            "produtos_principais": [],
        }
    score_viabilidade = float(viabilidade.get("score_viabilidade") or 0)

    eleg_checker = EligibilityChecker()
    try:
        elegibilidade = eleg_checker.check_eligibility(licitacao, viabilidade)
    finally:
        try:
            eleg_checker.session.close()
        except Exception:
            pass

    # Score final pondera IA + match de produto; penaliza se IA reprovou.
    bonus_catalogo = 0
    if matches_norm:
        # usa melhor match (cosine) para dar ate +20 pontos
        melhor = max(m["score"] for m in matches_norm)
        bonus_catalogo = min(20, round(melhor * 100 * 0.2, 1))

    score_final = max(0, min(100, score_viabilidade + bonus_catalogo))
    if not relevante:
        score_final = min(score_final, 40)

    return {
        "relevante": relevante,
        "matches": matches_norm,
        "viabilidade": viabilidade,
        "elegibilidade": elegibilidade,
        "score_final": score_final,
    }
