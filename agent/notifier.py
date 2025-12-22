from datetime import datetime
import json
from typing import Any, Dict, Iterable, List

from modules.database.database import AlertSent, Configuracao, get_session
from modules.utils.notifications import WhatsAppNotifier


def _load_contacts(session) -> List[Dict[str, str]]:
    config_contacts = session.query(Configuracao).filter_by(chave="whatsapp_contacts").first()
    if config_contacts and config_contacts.valor:
        try:
            contatos = json.loads(config_contacts.valor)
            if isinstance(contatos, list):
                return contatos
        except Exception:
            pass

    # Fallback legado
    phone = session.query(Configuracao).filter_by(chave="whatsapp_phone").first()
    key = session.query(Configuracao).filter_by(chave="whatsapp_apikey").first()
    if phone and key and phone.valor and key.valor:
        return [{"nome": "Principal", "phone": phone.valor, "apikey": key.valor}]
    return []


def _formatar_mensagens(licitacoes: Iterable[Dict[str, Any]], resumo: str) -> List[str]:
    lic_list = list(licitacoes)
    if not lic_list:
        return []

    linhas_header = ["MEDCAL - Alertas de Licitacoes", resumo.strip(), ""]
    mensagens = []
    bloco = []

    for idx, lic in enumerate(lic_list, 1):
        orgao = lic.get("orgao", "N/I")
        uf = lic.get("uf", "BR")
        modalidade = lic.get("modalidade", "N/I")
        prazo = lic.get("data_encerramento_proposta")
        prazo_str = ""
        if prazo:
            try:
                prazo_dt = prazo.date() if hasattr(prazo, "date") else prazo
                prazo_str = prazo_dt.strftime("%d/%m")
            except Exception:
                prazo_str = ""
        link = lic.get("link", "")
        score = lic.get("score_final")
        linha = f"{idx}. {orgao} ({uf}) | {modalidade}"
        if prazo_str:
            linha += f" | Prazo {prazo_str}"
        if score is not None:
            linha += f" | Score {score:.1f}"
        if link:
            linha += f"\n{link}"
        bloco.append(linha)

        # envia em blocos de 8 licitacoes para evitar mensagens gigantes
        if len(bloco) == 8:
            mensagens.append("\n".join(linhas_header + bloco))
            bloco = []

    if bloco:
        mensagens.append("\n".join(linhas_header + bloco))

    return mensagens


def enviar_alerta(licitacoes_top: List[Dict[str, Any]], resumo_run: str, run_id: int | None = None) -> bool:
    session = get_session()
    contatos = _load_contacts(session)
    if not contatos:
        return False

    mensagens = _formatar_mensagens(licitacoes_top, resumo_run)
    if not mensagens:
        return False

    sucesso = False
    for contato in contatos:
        notifier = WhatsAppNotifier(contato.get("phone"), contato.get("apikey"))
        for msg in mensagens:
            ok = notifier.enviar_mensagem(msg)
            sucesso = sucesso or ok
            registro = AlertSent(
                run_id=run_id,
                destino=contato.get("phone"),
                mensagem=msg,
                enviado_em=datetime.now(),
                sucesso=bool(ok),
            )
            session.add(registro)
        session.commit()

    session.close()
    return sucesso
