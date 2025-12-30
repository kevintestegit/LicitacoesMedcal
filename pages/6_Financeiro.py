import streamlit as st
import pandas as pd
import time
import os
from datetime import datetime
from io import BytesIO
from sqlalchemy import func, or_, not_
from components.config import init_page_config
from components.sidebar import render_sidebar
from modules.finance.bank_models import ExtratoBB, ResumoMensal
from modules.finance.extrato_parser import importar_extrato_bb, processar_texto_extrato
from modules.finance import (
    get_finance_session,
    get_finance_historico_session,
    importar_extrato_historico,
)
from modules.finance.backup_manager import BackupManager
from pathlib import Path

# Configuração da página e CSS
init_page_config(page_title="Medcal - Gestão Financeira")

# Renderiza sidebar
render_sidebar()

st.header("💰 Gestão Financeira - Extratos Banco do Brasil")
st.info("Importe e visualize seus extratos bancários (Formato Excel BB).")

col_base, _ = st.columns([1, 4])
with col_base:
    base_escolhida = st.radio(
        "Base de dados",
        ["Financeiro Atual", "Financeiro Histórico"],
        horizontal=True,
        help="Escolha onde salvar/consultar: ativo (2025 em diante) ou histórico (anos anteriores)."
    )
is_historico = base_escolhida == "Financeiro Histórico"
session_factory = get_finance_historico_session if is_historico else get_finance_session
session = session_factory()
base_label = "Histórico" if is_historico else "Atual"

# === BUSCA GLOBAL POR FATURA/OBS ===
with st.expander("🔎 Busca Global por Fatura/Obs (todas as bases e meses)", expanded=False):
    termo_fatura_global = st.text_input("Informe parte da fatura/obs/histórico (ex: 3194)", key="busca_fatura_global")
    if termo_fatura_global:
        query_base = session.query(ExtratoBB).filter(
            or_(
                ExtratoBB.fatura.ilike(f"%{termo_fatura_global}%"),
                ExtratoBB.observacoes.ilike(f"%{termo_fatura_global}%"),
                ExtratoBB.historico.ilike(f"%{termo_fatura_global}%")
            )
        ).order_by(ExtratoBB.dt_balancete.desc()).limit(200).all()

        if is_historico:
            outra_session = get_finance_session()
            outra_label = "Financeiro Atual"
        else:
            outra_session = get_finance_historico_session()
            outra_label = "Financeiro Histórico"

        query_outra = outra_session.query(ExtratoBB).filter(
            or_(
                ExtratoBB.fatura.ilike(f"%{termo_fatura_global}%"),
                ExtratoBB.observacoes.ilike(f"%{termo_fatura_global}%"),
                ExtratoBB.historico.ilike(f"%{termo_fatura_global}%")
            )
        ).order_by(ExtratoBB.dt_balancete.desc()).limit(200).all()

        def montar_df(lst, label):
            data = []
            for l in lst:
                data.append({
                    "Base": label,
                    "Data": l.dt_balancete,
                    "Mês": l.mes_referencia,
                    "Ano": l.ano_referencia,
                    "Status": l.status,
                    "Histórico": l.historico,
                    "Documento": l.documento,
                    "Valor": l.valor,
                    "Fatura/Obs": l.fatura or l.observacoes
                })
            return pd.DataFrame(data)

        df_base = montar_df(query_base, base_label)
        df_outra = montar_df(query_outra, outra_label)
        df_result = pd.concat([df_base, df_outra], ignore_index=True)

        if df_result.empty:
            st.info("Nada encontrado nas duas bases.")
        else:
            st.caption("Mostrando até 200 resultados por base, ordenados pela data mais recente.")
            st.dataframe(df_result, use_container_width=True, hide_index=True)
            csv_data = df_result.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Baixar resultados (CSV)", data=csv_data, file_name=f"busca_fatura_global_{termo_fatura_global}.csv", mime="text/csv")

# === SEÇÃO DE UPLOAD ===
col_up1, col_up2 = st.columns(2)

with col_up1:
    with st.expander("📤 Importar Arquivo Excel", expanded=False):
        uploaded_file = st.file_uploader("Selecione o arquivo Excel (.xlsx)", type=['xlsx'])
        if uploaded_file:
            if st.button("Processar Arquivo"):
                temp_path = f"temp_extrato_{int(time.time())}.xlsx"
                with open(temp_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                try:
                    stats = importar_extrato_bb(temp_path, session)
                    st.success(f"✅ Importação concluída! {stats['importados']} lançamentos processados.")
                    if stats.get('duplicados', 0) > 0:
                        st.warning(f"{stats['duplicados']} lançamentos duplicados mantidos/ignorados.")
                finally:
                    if os.path.exists(temp_path): os.remove(temp_path)
                st.rerun()

    with st.expander("📤 Importar Arquivo Excel (Histórico flexível)", expanded=False):
        banco_origem = st.selectbox("Banco/Origem", ["Sicredi", "BB", "Outro"], key="hist_banco_origem")
        uploaded_hist = st.file_uploader("Selecione o arquivo Excel (.xlsx)", type=['xlsx'], key="hist_uploader")
        if uploaded_hist and st.button("Processar Histórico", key="btn_process_hist"):
            temp_path = f"temp_extrato_{int(time.time())}.xlsx"
            with open(temp_path, "wb") as f: f.write(uploaded_hist.getbuffer())
            try:
                stats = importar_extrato_historico(temp_path, session, banco_origem)
                st.success(f"✅ Histórico importado! {stats['importados']} lançamentos.")
            finally:
                if os.path.exists(temp_path): os.remove(temp_path)
            st.rerun()

with col_up2:
    ultimo_lanc = session.query(ExtratoBB).order_by(ExtratoBB.dt_balancete.desc()).first()
    lbl_expander = "📋 Importar Texto (Copiar/Colar)"
    if ultimo_lanc:
        ud = ultimo_lanc.dt_balancete
        prox_mes = ud.month + 1 if ud.month < 12 else 1
        prox_ano = ud.year if ud.month < 12 else ud.year + 1
        meses_pt = {1:'Janeiro', 2:'Fevereiro', 3:'Março', 4:'Abril', 5:'Maio', 6:'Junho', 7:'Julho', 8:'Agosto', 9:'Setembro', 10:'Outubro', 11:'Novembro', 12:'Dezembro'}
        lbl_expander = f"📋 Importar: {meses_pt[prox_mes]}/{prox_ano} (Copiar/Colar)"
    
    with st.expander(lbl_expander, expanded=False):
        texto_paste = st.text_area("Cole os dados aqui:", height=150)
        if st.button("Processar Texto"):
            if texto_paste:
                stats = processar_texto_extrato(texto_paste, session)
                st.success(f"✅ Importação concluída! {stats['importados']} lançamentos.")
                st.rerun()

st.divider()

# === IMPORTAR PLANILHA SESAP ===
with st.expander("📥 Importar Planilha SESAP", expanded=False):
    uploaded_sesap = st.file_uploader("Selecione a planilha SESAP (.xlsx)", type=['xlsx'])
    if uploaded_sesap and st.button("Processar Planilha SESAP"):
        temp_path = f"temp_sesap_{int(time.time())}.xlsx"
        with open(temp_path, "wb") as f: f.write(uploaded_sesap.getbuffer())
        try:
            from modules.finance import importar_planilha_sesap
            stats = importar_planilha_sesap(temp_path, session, arquivo_origem=uploaded_sesap.name)
            st.success(f"✅ SESAP importada: {stats['importados']} linhas.")
        finally:
            if os.path.exists(temp_path): os.remove(temp_path)
        st.rerun()

st.divider()

# === ASSISTENTE IA ===
with st.expander("🤖 Assistente Financeiro (IA)", expanded=True):
    col_ai1, col_ai2 = st.columns([4, 1])
    pergunta_usuario = col_ai1.text_input("Pergunte sobre suas finanças:")
    if col_ai2.button("Perguntar 🧠") and pergunta_usuario:
        from modules.finance.finance_ai import FinanceAI
        finance_ai = FinanceAI(session_factory=session_factory, fonte_nome=base_label)
        with st.spinner("Analisando dados..."):
            st.markdown(f"### 🤖 Resposta:\n{finance_ai.analisar_pergunta(pergunta_usuario)}")

st.divider()

# === DASHBOARD E VISUALIZAÇÃO ===
meses_disponiveis = session.query(ResumoMensal).order_by(ResumoMensal.ano.desc(), ResumoMensal.id.desc()).all()
if meses_disponiveis:
    opcoes_meses = [f"{m.mes}/{m.ano}" for m in meses_disponiveis]
    if 'mes_financeiro_idx' not in st.session_state: st.session_state.mes_financeiro_idx = 0
    
    col_sel_mes, _ = st.columns([1, 3])
    mes_selecionado_str = col_sel_mes.selectbox("📅 Mês", opcoes_meses, index=st.session_state.mes_financeiro_idx, key="selector_mes_topo")
    resumo_selecionado = meses_disponiveis[opcoes_meses.index(mes_selecionado_str)]

    st.subheader(f"📊 Resumo: {resumo_selecionado.mes}/{resumo_selecionado.ano}")
    
    m1, m2, m3, m4, m5 = st.columns(5)
    ent_op = getattr(resumo_selecionado, 'total_entradas_sem_aportes', 0.0)
    aportes = getattr(resumo_selecionado, 'total_aportes', 0.0)
    saidas = getattr(resumo_selecionado, 'total_saidas', 0.0)
    m1.metric("Entradas Operacionais", f"R$ {ent_op:,.2f}")
    m2.metric("Aportes de Capital", f"R$ {aportes:,.2f}")
    m3.metric("Saídas (-)", f"R$ {saidas:,.2f}")
    m4.metric("Res. Operacional", f"R$ {(ent_op - saidas):,.2f}")
    m5.metric("Res. Total", f"R$ {(ent_op + aportes - saidas):,.2f}")

    st.divider()
    
    # Tabela de Lançamentos
    st.markdown("#### 📋 Lançamentos do Mês")
    query = session.query(ExtratoBB).filter_by(mes_referencia=resumo_selecionado.mes, ano_referencia=resumo_selecionado.ano)
    lancamentos = query.order_by(ExtratoBB.dt_balancete.desc()).all()
    if lancamentos:
        df_edit = pd.DataFrame([{
            "id": l.id, "Data": l.dt_balancete, "Status": l.status, "Histórico": l.historico,
            "Valor": l.valor, "Tipo": l.tipo, "Fatura": l.fatura
        } for l in lancamentos]).set_index("id")
        
        st.data_editor(df_edit, column_config={"Data": st.column_config.DateColumn(disabled=True), "Valor": st.column_config.NumberColumn(format="R$ %.2f", disabled=True)}, width='stretch')

st.divider()

# === BACKUP ===
with st.expander("💾 Gerenciamento de Backups", expanded=False):
    backup_manager = BackupManager()
    if st.button("💾 Criar Backup Manual"):
        res = backup_manager.criar_backup(descricao="Manual via Dashboard")
        if res["sucesso"]: st.success("Backup criado!")

session.close()
