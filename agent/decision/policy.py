from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict


@dataclass
class PolicyResult:
    acao: str
    motivo: str
    prioridade: int = 0


def _to_date(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    try:
        return datetime.fromisoformat(str(value)).date()
    except Exception:
        return None


def aplicar_politica(licitacao: Dict[str, Any], analise: Dict[str, Any], hoje: date | None = None) -> PolicyResult:
    hoje = hoje or date.today()

    # 1) Prazo
    prazo = _to_date(licitacao.get("data_encerramento_proposta")) if licitacao else None
    if prazo and prazo < hoje:
        return PolicyResult("IGNORAR", "Prazo encerrado")

    # 2) Filtro semantico
    if not analise.get("relevante", True):
        return PolicyResult("IGNORAR", "IA reprovou relevancia do objeto")

    viabilidade = analise.get("viabilidade") or {}
    score_viab = float(viabilidade.get("score_viabilidade") or 0)
    red_flags = viabilidade.get("red_flags") or []

    eleg = analise.get("elegibilidade") or {}
    if not eleg.get("eligible", True):
        reasons = eleg.get("reasons") or []
        msg = "; ".join(reasons) if reasons else "Fora do perfil definido"
        return PolicyResult("IGNORAR", msg)

    if red_flags:
        return PolicyResult("REVISAR", f"Red flags: {', '.join(red_flags[:3])}")

    matches = analise.get("matches") or []
    score_final = float(analise.get("score_final") or score_viab)

    if score_final >= 80 or (score_viab >= 70 and matches):
        return PolicyResult("PARTICIPAR", "Alta aderencia e prazo aberto", prioridade=2)
    if score_final >= 60:
        return PolicyResult("REVISAR", "Aderencia media; revisar manualmente", prioridade=1)

    return PolicyResult("IGNORAR", "Baixa aderencia ao portfolio")
