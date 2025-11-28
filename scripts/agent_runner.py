import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict, Tuple

# Garante import dos modulos locais quando executado via CLI
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.orchestrator import executar
from agent.notifier import enviar_alerta
from agent.decision.policy import PolicyResult
from modules.database.database import (
    AgentRun,
    ItemLicitacao,
    Licitacao,
    get_session,
    init_db,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)


def _to_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except Exception:
        return None


def _persistir_licitacao(session, data: Dict[str, Any]) -> Tuple[Licitacao, bool]:
    """Cria licitacao + itens se ainda nao existir. Retorna (objeto, criado?)."""
    existente = None
    pncp_id = data.get("pncp_id")
    if pncp_id:
        existente = session.query(Licitacao).filter_by(pncp_id=pncp_id).first()
    if existente:
        return existente, False

    existente = session.query(Licitacao).filter_by(orgao=data.get("orgao"), objeto=data.get("objeto")).first()
    if existente:
        return existente, False

    lic = Licitacao(
        pncp_id=pncp_id,
        orgao=data.get("orgao"),
        uf=data.get("uf"),
        modalidade=data.get("modalidade"),
        data_sessao=_to_datetime(data.get("data_sessao")),
        data_publicacao=_to_datetime(data.get("data_publicacao")),
        data_inicio_proposta=_to_datetime(data.get("data_inicio_proposta")),
        data_encerramento_proposta=_to_datetime(data.get("data_encerramento_proposta")),
        objeto=data.get("objeto"),
        link=data.get("link"),
    )
    session.add(lic)
    session.flush()

    for item in data.get("itens") or []:
        try:
            numero_item = int(item.get("numero_item") or item.get("numero") or 0)
        except Exception:
            numero_item = 0
        item_db = ItemLicitacao(
            licitacao_id=lic.id,
            numero_item=numero_item,
            descricao=item.get("descricao"),
            quantidade=item.get("quantidade") or 0,
            unidade=item.get("unidade"),
            valor_estimado=item.get("valor_estimado"),
            valor_unitario=item.get("valor_unitario"),
        )
        session.add(item_db)

    session.commit()
    return lic, True


def run_once(filtros_base: Dict[str, Any] | None = None, top_n: int = 5):
    """
    Roda o agente uma vez: coleta -> analisa -> aplica politica -> persiste -> notifica.
    """
    init_db()
    session = get_session()

    run = AgentRun(started_at=datetime.now(), status="running")
    session.add(run)
    session.commit()

    try:
        resultados = executar(filtros_base)
        run.total_coletado = len(resultados)

        novas = []
        for resultado in resultados:
            lic_data = resultado["licitacao"]
            lic_obj, criado = _persistir_licitacao(session, lic_data)
            if criado:
                novas.append((lic_obj, resultado))

        run.total_novos = len(novas)

        total_participar = total_revisar = total_ignorar = 0
        alertas_pool = []

        for lic_obj, resultado in novas:
            analise = resultado["analise"]
            politica: PolicyResult = resultado["politica"]

            if politica.acao == "PARTICIPAR":
                lic_obj.status = "Participar"
                total_participar += 1
                alert_entry = resultado["licitacao"].copy()
                alert_entry["score_final"] = analise.get("score_final")
                alertas_pool.append(alert_entry)
            elif politica.acao == "REVISAR":
                lic_obj.status = "Em Análise"
                total_revisar += 1
            else:
                lic_obj.status = "Ignorada"
                total_ignorar += 1

            lic_obj.comentarios = politica.motivo
            session.add(lic_obj)

        run.total_analisados = len(novas)
        run.total_participar = total_participar
        run.total_revisar = total_revisar
        run.total_ignorar = total_ignorar
        run.finished_at = datetime.now()
        run.status = "completed"
        run.resumo = (
            f"Coletadas {run.total_coletado}, novas {run.total_novos}, "
            f"participar {total_participar}, revisar {total_revisar}, ignorar {total_ignorar}"
        )
        session.add(run)
        session.commit()

        if alertas_pool:
            alertas_pool.sort(key=lambda x: x.get("score_final", 0), reverse=True)
            lic_top = alertas_pool[:top_n]
            enviar_alerta(lic_top, resumo_run=run.resumo, run_id=run.id)

        logging.info("Execucao concluida. Run ID=%s", run.id)
    except Exception as exc:
        logging.exception("Erro ao rodar agente: %s", exc)
        run.status = "failed"
        run.finished_at = datetime.now()
        run.resumo = f"Erro: {exc}"
        session.add(run)
        session.commit()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    run_once()
