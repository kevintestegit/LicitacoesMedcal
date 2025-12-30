import streamlit as st
import pandas as pd
import time
from datetime import datetime, date
from components.config import init_page_config
from components.sidebar import render_sidebar
from modules.database.database_config import is_using_turso

# Configuração da página e CSS
init_page_config(page_title="Medcal - Pagamentos")

# Renderiza sidebar
render_sidebar()

st.header("💸 Pagamentos")

# Verifica se usa Turso (conexão direta) ou SQLite local
if is_using_turso():
    # Usa módulo Turso direto
    from modules.finance import turso_funcionarios as tf
    
    # Inicializa tabelas
    tf.init_tables()
    
    # Lista funcionários
    funcionarios_list = tf.listar_funcionarios()
    funcionarios_nomes = [f.nome for f in funcionarios_list]
    TIPOS = tf.TIPOS_PAGAMENTO
    
    # === SEÇÃO: NOVO PAGAMENTO ===
    with st.expander("➕ Registrar Novo Pagamento", expanded=True):
        col1, col2 = st.columns(2)
        
        with col1:
            funcionario_selecionado = st.selectbox(
                "Funcionário",
                funcionarios_nomes,
                index=0 if funcionarios_nomes else None,
                key="sel_func"
            )
            
            tipo_pagamento = st.selectbox(
                "Tipo",
                TIPOS,
                key="sel_tipo"
            )
            
        with col2:
            valor = st.number_input(
                "Valor (R$)",
                min_value=0.0,
                step=50.0,
                format="%.2f",
                key="input_valor"
            )
            
            data_pagamento = st.date_input(
                "Data",
                value=date.today(),
                format="DD/MM/YYYY",
                key="input_data"
            )
        
        descricao = st.text_input("Descrição (opcional)", key="input_desc")
        
        if st.button("💾 Salvar Pagamento", type="primary", use_container_width=True):
            if not funcionario_selecionado:
                st.error("Selecione um funcionário!")
            elif valor <= 0:
                st.error("Valor deve ser maior que zero!")
            else:
                func = tf.buscar_funcionario_por_nome(funcionario_selecionado)
                
                with st.spinner("💾 Salvando pagamento..."):
                    time.sleep(0.3)
                    tf.criar_pagamento(
                        funcionario_id=func.id,
                        tipo=tipo_pagamento,
                        valor=valor,
                        data_pagamento=data_pagamento,
                        descricao=descricao if descricao else None
                    )
                
                st.success(f"✅ Pagamento de R$ {valor:.2f} registrado para {funcionario_selecionado}!")
                time.sleep(1)
                st.rerun()
    
    st.divider()
    
    # === SEÇÃO: HISTÓRICO DE PAGAMENTOS ===
    st.subheader("📋 Histórico de Pagamentos")
    
    # Filtros
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        filtro_func = st.selectbox(
            "Funcionário",
            ["Todos"] + funcionarios_nomes,
            key="filtro_func"
        )
    with col_f2:
        filtro_mes = st.selectbox(
            "Mês",
            ["Todos", "Dezembro", "Novembro", "Outubro", "Setembro", "Agosto", 
             "Julho", "Junho", "Maio", "Abril", "Março", "Fevereiro", "Janeiro"],
            key="filtro_mes"
        )
    with col_f3:
        filtro_tipo = st.selectbox(
            "Tipo",
            ["Todos"] + TIPOS,
            key="filtro_tipo"
        )
    
    # Mapeamento de meses
    meses_map = {
        "Janeiro": 1, "Fevereiro": 2, "Março": 3, "Abril": 4,
        "Maio": 5, "Junho": 6, "Julho": 7, "Agosto": 8,
        "Setembro": 9, "Outubro": 10, "Novembro": 11, "Dezembro": 12
    }
    
    mes_num = meses_map.get(filtro_mes, None) if filtro_mes != "Todos" else None
    
    pagamentos = tf.listar_pagamentos(
        funcionario_nome=filtro_func if filtro_func != "Todos" else None,
        tipo=filtro_tipo if filtro_tipo != "Todos" else None,
        mes=mes_num
    )
    
    if not pagamentos:
        st.info("Nenhum pagamento encontrado.")
    else:
        total = sum(p.valor for p in pagamentos)
        
        data = []
        for p in pagamentos:
            data.append({
                "ID": p.id,
                "Data": p.data.strftime("%d/%m/%Y") if p.data else "N/A",
                "Funcionário": p.funcionario_nome,
                "Tipo": p.tipo,
                "Valor": f"R$ {p.valor:.2f}",
                "Descrição": p.descricao or "-"
            })
        
        df = pd.DataFrame(data)
        st.dataframe(df.drop(columns=["ID"]), use_container_width=True, hide_index=True)
        st.markdown(f"### 💰 Total: **R$ {total:,.2f}**")
        
        with st.expander("🗑️ Remover Pagamentos"):
            pagamentos_del = st.multiselect(
                "Selecione os IDs para remover",
                [p.id for p in pagamentos],
                format_func=lambda x: f"#{x} - R$ {next(p.valor for p in pagamentos if p.id == x):.2f}"
            )
            
            if st.button("Remover Selecionados", type="secondary"):
                if pagamentos_del:
                    tf.remover_pagamentos(pagamentos_del)
                    st.success(f"✅ {len(pagamentos_del)} pagamento(s) removido(s)!")
                    st.rerun()
    
    st.divider()
    
    # === SEÇÃO: GERENCIAR FUNCIONÁRIOS ===
    with st.expander("⚙️ Gerenciar Funcionários", expanded=False):
        st.subheader("Funcionários Cadastrados")
        
        for func in funcionarios_list:
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.write(f"**{func.nome}**")
            with col2:
                status = "✅ Ativo" if func.ativo else "❌ Inativo"
                st.caption(status)
            with col3:
                if st.button("🗑️", key=f"del_{func.id}"):
                    tf.desativar_funcionario(func.id)
                    st.rerun()
        
        st.divider()
        st.subheader("Adicionar Novo Funcionário")
        
        novo_nome = st.text_input("Nome do funcionário", key="novo_func_nome")
        if st.button("➕ Adicionar Funcionário"):
            if novo_nome.strip():
                tf.criar_funcionario(novo_nome.strip())
                st.success(f"✅ Funcionário {novo_nome} cadastrado!")
                st.rerun()
            else:
                st.error("Informe o nome do funcionário!")

else:
    # Fallback: SQLite local com SQLAlchemy
    from modules.finance.database import get_finance_session, init_finance_db
    from modules.finance.funcionarios_models import Funcionario, PagamentoFuncionario
    
    init_finance_db()
    session = get_finance_session()
    
    funcionarios = session.query(Funcionario).filter(Funcionario.ativo == True).all()
    funcionarios_nomes = [f.nome for f in funcionarios]
    
    with st.expander("➕ Registrar Novo Pagamento", expanded=True):
        col1, col2 = st.columns(2)
        
        with col1:
            funcionario_selecionado = st.selectbox(
                "Funcionário",
                funcionarios_nomes,
                index=0 if funcionarios_nomes else None,
                key="sel_func"
            )
            
            tipo_pagamento = st.selectbox(
                "Tipo",
                PagamentoFuncionario.TIPOS,
                key="sel_tipo"
            )
            
        with col2:
            valor = st.number_input(
                "Valor (R$)",
                min_value=0.0,
                step=50.0,
                format="%.2f",
                key="input_valor"
            )
            
            data_pagamento = st.date_input(
                "Data",
                value=date.today(),
                format="DD/MM/YYYY",
                key="input_data"
            )
        
        descricao = st.text_input("Descrição (opcional)", key="input_desc")
        
        if st.button("💾 Salvar Pagamento", type="primary", use_container_width=True):
            if not funcionario_selecionado:
                st.error("Selecione um funcionário!")
            elif valor <= 0:
                st.error("Valor deve ser maior que zero!")
            else:
                func = session.query(Funcionario).filter(Funcionario.nome == funcionario_selecionado).first()
                
                novo_pagamento = PagamentoFuncionario(
                    funcionario_id=func.id,
                    tipo=tipo_pagamento,
                    valor=valor,
                    data=data_pagamento,
                    descricao=descricao if descricao else None
                )
                session.add(novo_pagamento)
                
                with st.spinner("💾 Salvando pagamento..."):
                    time.sleep(0.5)
                    session.commit()
                
                st.success(f"✅ Pagamento de R$ {valor:.2f} registrado para {funcionario_selecionado}!")
                time.sleep(1)
                st.rerun()
    
    st.divider()
    st.subheader("📋 Histórico de Pagamentos")
    
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        filtro_func = st.selectbox("Funcionário", ["Todos"] + funcionarios_nomes, key="filtro_func")
    with col_f2:
        filtro_mes = st.selectbox("Mês", ["Todos", "Dezembro", "Novembro", "Outubro", "Setembro", "Agosto", 
             "Julho", "Junho", "Maio", "Abril", "Março", "Fevereiro", "Janeiro"], key="filtro_mes")
    with col_f3:
        filtro_tipo = st.selectbox("Tipo", ["Todos"] + PagamentoFuncionario.TIPOS, key="filtro_tipo")
    
    query = session.query(PagamentoFuncionario).join(Funcionario)
    
    if filtro_func != "Todos":
        query = query.filter(Funcionario.nome == filtro_func)
    if filtro_tipo != "Todos":
        query = query.filter(PagamentoFuncionario.tipo == filtro_tipo)
    
    meses_map = {"Janeiro": 1, "Fevereiro": 2, "Março": 3, "Abril": 4, "Maio": 5, "Junho": 6,
                 "Julho": 7, "Agosto": 8, "Setembro": 9, "Outubro": 10, "Novembro": 11, "Dezembro": 12}
    
    if filtro_mes != "Todos":
        from sqlalchemy import extract
        mes_num = meses_map.get(filtro_mes, 0)
        if mes_num > 0:
            query = query.filter(extract('month', PagamentoFuncionario.data) == mes_num)
    
    pagamentos = query.order_by(PagamentoFuncionario.data.desc()).all()
    
    if not pagamentos:
        st.info("Nenhum pagamento encontrado.")
    else:
        total = sum(p.valor for p in pagamentos)
        
        data = []
        for p in pagamentos:
            data.append({
                "ID": p.id,
                "Data": p.data.strftime("%d/%m/%Y") if p.data else "N/A",
                "Funcionário": p.funcionario.nome,
                "Tipo": p.tipo,
                "Valor": f"R$ {p.valor:.2f}",
                "Descrição": p.descricao or "-"
            })
        
        df = pd.DataFrame(data)
        st.dataframe(df.drop(columns=["ID"]), use_container_width=True, hide_index=True)
        st.markdown(f"### 💰 Total: **R$ {total:,.2f}**")
        
        with st.expander("🗑️ Remover Pagamentos"):
            pagamentos_del = st.multiselect(
                "Selecione os IDs para remover",
                [p.id for p in pagamentos],
                format_func=lambda x: f"#{x} - R$ {next(p.valor for p in pagamentos if p.id == x):.2f}"
            )
            
            if st.button("Remover Selecionados", type="secondary"):
                if pagamentos_del:
                    for pid in pagamentos_del:
                        pag = session.query(PagamentoFuncionario).get(pid)
                        if pag:
                            session.delete(pag)
                    session.commit()
                    st.success(f"✅ {len(pagamentos_del)} pagamento(s) removido(s)!")
                    st.rerun()
    
    st.divider()
    
    with st.expander("⚙️ Gerenciar Funcionários", expanded=False):
        st.subheader("Funcionários Cadastrados")
        
        for func in funcionarios:
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.write(f"**{func.nome}**")
            with col2:
                status = "✅ Ativo" if func.ativo else "❌ Inativo"
                st.caption(status)
            with col3:
                if st.button("🗑️", key=f"del_{func.id}"):
                    func.ativo = False
                    session.commit()
                    st.rerun()
        
        st.divider()
        st.subheader("Adicionar Novo Funcionário")
        
        novo_nome = st.text_input("Nome do funcionário", key="novo_func_nome")
        if st.button("➕ Adicionar Funcionário"):
            if novo_nome.strip():
                novo_func = Funcionario(nome=novo_nome.strip(), ativo=True)
                session.add(novo_func)
                session.commit()
                st.success(f"✅ Funcionário {novo_nome} cadastrado!")
                st.rerun()
            else:
                st.error("Informe o nome do funcionário!")
    
    session.close()
