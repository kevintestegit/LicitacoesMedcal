import streamlit as st
import pandas as pd
from datetime import datetime
from sqlalchemy import func
from components.config import init_page_config
from components.sidebar import render_sidebar
from components.utils import best_match_against_keywords
from modules.database.database import get_session, Licitacao, Configuracao
from modules.utils.deadline_alerts import is_prazo_urgente, get_dias_restantes
from modules.utils.notifications import WhatsAppNotifier
from modules.distance_calculator import get_road_distance

# Configuração da página e CSS
init_page_config(page_title="Medcal - Dashboard")

# Renderiza sidebar
render_sidebar()

st.header("Painel de Controle")

# Carrega classificador ML (se disponível)
ml_classifier = None
try:
    from modules.ml import LicitacaoClassifier
    ml_classifier = LicitacaoClassifier()
    if not ml_classifier.trained:
        ml_classifier = None
except Exception:
    pass

session = get_session()

# === FILTROS ===
col_filtro1, col_filtro2, col_filtro3 = st.columns(3)
with col_filtro1:
    apenas_salvas = st.checkbox("⭐ Mostrar apenas licitações Salvas", value=False)
with col_filtro2:
    from modules.utils.category_classifier import CATEGORIAS_DISPONIVEIS
    categoria_filtro = st.selectbox("📁 Categoria", CATEGORIAS_DISPONIVEIS, label_visibility="collapsed")
with col_filtro3:
    if ml_classifier:
        filtro_relevantes = st.checkbox("🎯 Apenas Relevantes (ML)", value=False, help="Mostra apenas licitações com score ≥ 50%")
    else:
        filtro_relevantes = False

query = session.query(Licitacao)
if apenas_salvas:
    query = query.filter(Licitacao.status == 'Salva')
if categoria_filtro != "Todas":
    query = query.filter(Licitacao.categoria == categoria_filtro)

licitacoes_db = query.all()

# Calcula scores ML se o classificador estiver disponível
def get_ml_score(lic):
    if not ml_classifier:
        return None
    try:
        lic_dict = {
            'orgao': lic.orgao,
            'uf': lic.uf,
            'modalidade': lic.modalidade,
            'objeto': lic.objeto,
            'itens': [{'descricao': item.descricao} for item in lic.itens] if lic.itens else [],
        }
        return ml_classifier.predict_proba(lic_dict)
    except:
        return None

# Ordenação com score ML
licitacoes_com_score = []
for lic in licitacoes_db:
    score = get_ml_score(lic)
    licitacoes_com_score.append((lic, score))

# Filtra por relevância se solicitado
if filtro_relevantes and ml_classifier:
    licitacoes_com_score = [(lic, score) for lic, score in licitacoes_com_score if score and score >= 0.5]

# Ordenação: score ML > matches > data
licitacoes_com_score.sort(
    key=lambda x: (
        x[1] or 0,  # Score ML primeiro
        sum(1 for i in x[0].itens if i.produto_match_id is not None),
        x[0].data_sessao or datetime.min
    ), 
    reverse=True
)

if not licitacoes_com_score:
    if filtro_relevantes:
        st.info("Nenhuma licitação relevante encontrada. Desmarque o filtro ML ou treine o modelo com mais dados.")
    else:
        st.info("Nenhuma licitação no banco. Vá em 'Buscar Licitações' para começar.")
else:
    urgentes = sum(1 for lic, _ in licitacoes_com_score if is_prazo_urgente(lic.data_encerramento_proposta) and lic.status == 'Salva')
    ml_info = " | 🧠 ML ativo" if ml_classifier else ""
    st.caption(f"📋 {len(licitacoes_com_score)} licitações" + (f" | ⚠️ {urgentes} urgentes" if urgentes > 0 else "") + ml_info)
    
    # Grid de Cards
    for i in range(0, len(licitacoes_com_score), 2):
        cols = st.columns(2)
        for col_idx, (lic, ml_score) in enumerate(licitacoes_com_score[i:i+2]):
            with cols[col_idx]:
                itens_com_match = [item for item in lic.itens if item.produto_match_id is not None]
                data_sessao_fmt = lic.data_sessao.strftime('%d/%m') if lic.data_sessao else "N/A"
                
                status_icon = "⭐" if lic.status == 'Salva' else ""
                prazo_urgente = is_prazo_urgente(lic.data_encerramento_proposta)
                urgente_badge = "<span class='badge-urgente'>⏰ URGENTE</span>" if prazo_urgente and lic.status == 'Salva' else ""
                
                # Badge de relevância ML
                ml_badge = ""
                if ml_score is not None:
                    if ml_score >= 0.7:
                        ml_badge = f"<span style='background:#22c55e;color:white;padding:2px 8px;border-radius:12px;font-size:11px;'>🎯 {ml_score:.0%}</span>"
                    elif ml_score >= 0.5:
                        ml_badge = f"<span style='background:#eab308;color:white;padding:2px 8px;border-radius:12px;font-size:11px;'>🎯 {ml_score:.0%}</span>"
                    else:
                        ml_badge = f"<span style='background:#6b7280;color:white;padding:2px 8px;border-radius:12px;font-size:11px;'>{ml_score:.0%}</span>"
                
                with st.container(border=True):
                    st.markdown(f"**[{lic.uf}] {lic.orgao} {status_icon}** {urgente_badge} {ml_badge}", unsafe_allow_html=True)
                    st.caption(f"📅 {data_sessao_fmt} | {lic.modalidade} | ✅ {len(itens_com_match)} matches")
                    st.write((lic.objeto or "")[:200] + "...")
                    
                    st.divider()
                    c1, c2, c3 = st.columns(3)
                    with c1: st.link_button("🔗 Link", lic.link, use_container_width=True)
                    with c2:
                        label = "⭐ Fixar" if lic.status != 'Salva' else "❌ Desafixar"
                        if st.button(label, key=f"save_card_{lic.id}", use_container_width=True):
                            lic.status = 'Salva' if lic.status != 'Salva' else 'Nova'
                            session.commit()
                            st.rerun()
                    with c3:
                        if st.button("📱 WhatsApp", key=f"wpp_card_{lic.id}", use_container_width=True):
                            st.toast("Enviando via WhatsApp...")

session.close()

