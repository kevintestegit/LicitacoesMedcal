import streamlit as st
import json
import time
from datetime import datetime
from components.config import init_page_config
from components.sidebar import render_sidebar
from modules.database.database import get_session, Configuracao
from modules.utils.notifications import WhatsAppNotifier
from modules.utils.system_backup import system_backup

# Configuração da página e CSS
init_page_config(page_title="Medcal - Configurações")

# Renderiza sidebar
render_sidebar()

st.header("⚙️ Configurações do Sistema")

session = get_session()

# --- Seção 1: Configuração IA ---
st.subheader("🤖 Configuração da IA")
st.markdown("""
Configure a chave de API do OpenRouter (IA do sistema).
""")

st.markdown("**🆓 OpenRouter**")
st.caption("Modelos gratuitos disponíveis no OpenRouter (sujeitos às políticas do provedor)")
    
config_openrouter = session.query(Configuracao).filter_by(chave='openrouter_api_key').first()
if not config_openrouter:
    config_openrouter = Configuracao(chave='openrouter_api_key', valor='')
    session.add(config_openrouter)
    session.commit()
    
nova_openrouter_key = st.text_input("OpenRouter API Key", value=config_openrouter.valor, type="password", key="openrouter_key")
if st.button("Salvar OpenRouter Key"):
    config_openrouter.valor = nova_openrouter_key
    session.commit()
    st.success("✅ OpenRouter Key salva!")
    
st.caption("Obtenha em: https://openrouter.ai/keys")
    
st.divider()
    
# --- Seção 2: Notificações WhatsApp (Multi-usuário) ---
st.subheader("🔔 Notificações WhatsApp (CallMeBot)")
st.markdown("""
Gerencie a lista de pessoas que receberão os alertas de licitações.
""")

# Carrega configuração de contatos (Lista JSON)
config_contacts = session.query(Configuracao).filter_by(chave='whatsapp_contacts').first()

# Migração Automática (Se tiver configuração antiga, converte para lista)
if not config_contacts:
    old_phone = session.query(Configuracao).filter_by(chave='whatsapp_phone').first()
    old_key = session.query(Configuracao).filter_by(chave='whatsapp_apikey').first()
    
    initial_list = []
    if old_phone and old_key and old_phone.valor:
        initial_list.append({"nome": "Principal (Migrado)", "phone": old_phone.valor, "apikey": old_key.valor})
        
    config_contacts = Configuracao(chave='whatsapp_contacts', valor=json.dumps(initial_list))
    session.add(config_contacts)
    session.commit()

# Parse da lista
try:
    contacts_list = json.loads(config_contacts.valor) if config_contacts.valor else []
except:
    contacts_list = []

# Lista de Contatos
if contacts_list:
    msg_padrao = "🔔 Teste de notificação Medcal realizado com sucesso!"
    msg_custom_global = st.text_area(
        "Mensagem de teste (será enviada para todos)",
        value=msg_padrao,
        key="msg_wpp_global"
    )
    st.write("**Contatos Cadastrados:**")
    for idx, contact in enumerate(contacts_list):
        with st.container():
            c1, c2, c3, c4 = st.columns([3, 3, 1, 1])
            c1.markdown(f"👤 **{contact.get('nome', 'Sem Nome')}**")
            c2.text(f"📞 {contact.get('phone', '')}")
            
            if c3.button("🔔", key=f"test_wpp_{idx}", help="Enviar mensagem de teste"):
                notifier = WhatsAppNotifier(contact.get('phone'), contact.get('apikey'))
                texto = (msg_custom_global or "").strip() or msg_padrao
                if notifier.enviar_mensagem(texto):
                    st.toast(f"Mensagem enviada para {contact.get('nome')}!", icon="✅")
                else:
                    erro_msg = notifier.ultimo_erro or "Erro desconhecido"
                    st.error(f"Erro ao enviar para {contact.get('nome')}: {erro_msg}")

            if c4.button("🗑️", key=f"del_wpp_{idx}", help="Excluir este contato"):
                contacts_list.pop(idx)
                config_contacts.valor = json.dumps(contacts_list)
                session.commit()
                st.rerun()
            st.divider()
else:
    st.info("Nenhum contato cadastrado ainda.")
    
# Formulário para Adicionar
with st.expander("➕ Adicionar Novo Contato", expanded=False):
    with st.form("form_add_wpp"):
        st.markdown("Para obter a API Key: Adicione **+34 644 56 55 18** e envie `I allow callmebot to send me messages`.")
        col_n1, col_n2 = st.columns(2)
        n_nome = col_n1.text_input("Nome do Contato")
        n_phone = col_n2.text_input("Número (com DDI e DDD)", placeholder="5584999999999")
        n_key = st.text_input("API Key (CallMeBot)", type="password")
        
        if st.form_submit_button("Salvar Contato"):
            if n_nome and n_phone and n_key:
                contacts_list.append({"nome": n_nome, "phone": n_phone, "apikey": n_key})
                config_contacts.valor = json.dumps(contacts_list)
                session.commit()
                st.success("Contato adicionado com sucesso!")
                st.rerun()
            else:
                st.error("Preencha todos os campos obrigatórios.")

st.divider()

# --- Seção 3: Backup e Restore do Sistema ---
st.subheader("💾 Backup e Restore do Sistema")
st.markdown("""
Exporte todos os dados do sistema em um arquivo ZIP para transferir para outro computador,
ou importe um backup existente.
""")

col_export, col_import = st.columns(2)

with col_export:
    st.markdown("### 📤 Exportar Backup")
    
    descricao_bk = st.text_input("Descrição (opcional)", placeholder="Ex: Backup antes de migração", key="desc_backup_sys")
    
    if st.button("🔄 Gerar Backup", type="primary", key="btn_gerar_backup"):
        with st.spinner("Gerando backup..."):
            resultado = system_backup.export_backup(description=descricao_bk)
            
            if resultado["sucesso"]:
                st.success(f"✅ Backup criado: {resultado['nome']}")
                st.caption(f"📊 Tamanho: {resultado['tamanho_mb']} MB")
                st.caption(f"📁 Arquivos: {len(resultado['arquivos_incluidos'])}")
                
                # Botão de download
                backup_bytes = system_backup.get_backup_bytes(resultado["nome"])
                if backup_bytes:
                    st.download_button(
                        label="📥 Baixar Backup",
                        data=backup_bytes,
                        file_name=resultado["nome"],
                        mime="application/zip",
                        key="download_backup_sys"
                    )
            else:
                st.error(f"❌ Erro: {resultado['erro']}")
    
    # Lista backups existentes
    backups_existentes = system_backup.list_backups()
    if backups_existentes:
        with st.expander(f"📋 Backups anteriores ({len(backups_existentes)})", expanded=False):
            for bk in backups_existentes[:5]:  # Mostra últimos 5
                bk_dt = datetime.fromisoformat(bk["datetime"])
                st.caption(f"📅 {bk_dt.strftime('%d/%m/%Y %H:%M')} - {bk['tamanho_mb']} MB")
                if bk.get("description"):
                    st.caption(f"   _{bk['description']}_")

with col_import:
    st.markdown("### 📥 Importar Backup")
    st.warning("⚠️ Isso substituirá TODOS os dados atuais!")
    
    uploaded_backup = st.file_uploader(
        "Selecione o arquivo .zip de backup",
        type=["zip"],
        key="upload_backup_sys"
    )
    
    if uploaded_backup:
        st.info(f"📁 Arquivo: {uploaded_backup.name} ({round(uploaded_backup.size / 1024 / 1024, 2)} MB)")
        
        confirma = st.checkbox("Confirmo que desejo substituir todos os dados atuais", key="confirma_restore_sys")
        
        if st.button("♻️ Restaurar Backup", type="primary", disabled=not confirma, key="btn_restaurar_sys"):
            with st.spinner("Restaurando backup..."):
                # Salva arquivo temporário
                import tempfile
                with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
                    tmp.write(uploaded_backup.getbuffer())
                    tmp_path = tmp.name
                
                resultado = system_backup.import_backup(tmp_path)
                
                # Remove arquivo temporário
                import os
                os.unlink(tmp_path)
                
                if resultado["sucesso"]:
                    st.success("✅ Backup restaurado com sucesso!")
                    st.caption(f"📁 Arquivos restaurados: {len(resultado['arquivos_restaurados'])}")
                    st.warning("🔄 Reinicie o sistema para aplicar as alterações.")
                else:
                    st.error(f"❌ Erro: {resultado['erro']}")

session.close()
