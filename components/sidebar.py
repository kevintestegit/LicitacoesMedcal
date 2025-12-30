import streamlit as st
from datetime import datetime

def render_sidebar():
    with st.sidebar:
        st.markdown("""
            <div class="sidebar-header-custom">
                <div style="font-size: 20px; font-weight: 700; color: #ffffff; letter-spacing: -0.03em;">Medcal</div>
            </div>
        """, unsafe_allow_html=True)
        
        # === STATUS DE BUSCA EM BACKGROUND ===
        # Tenta obter status, mas se a tabela agent_runs não existir, ignora silenciosamente
        try:
            from modules.core.background_search import background_manager
            search_status = background_manager.get_current_status()
        except Exception:
            # Tabela agent_runs pode não existir no banco Turso - ignora o erro
            search_status = {'status': 'idle'}
        
        if search_status.get('status') == 'running':
            elapsed = search_status.get('elapsed_seconds', 0)
            mins = elapsed // 60
            secs = elapsed % 60
            st.markdown(f"""
                <div style="background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%); 
                            padding: 16px; border-radius: 16px; margin: 12px; text-align: center;
                            box-shadow: 0 8px 20px rgba(99,102,241,0.2); border: 1px solid rgba(255,255,255,0.1);">
                    <div style="font-size: 22px; margin-bottom: 8px; animation: spin 2s linear infinite;">🔄</div>
                    <div style="font-size: 12px; color: white; font-weight: 600;">Buscando Oportunidades</div>
                    <div style="font-size: 10px; color: rgba(255,255,255,0.8); margin-top: 4px;">Ativo há {mins}m {secs}s</div>
                </div>
            """, unsafe_allow_html=True)
            
            # Botão de refresh manual
            if st.button("🔄", key="sidebar_refresh", help="Atualizar status"):
                st.rerun()
            
        elif search_status.get('status') == 'completed' and search_status.get('finished_at'):
            finished = search_status['finished_at']
            if isinstance(finished, datetime) and (datetime.now() - finished).total_seconds() < 60:
                st.markdown("""
                    <div style="background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); 
                                padding: 10px; border-radius: 8px; margin-bottom: 12px; text-align: center;">
                        <div style="font-size: 20px; margin-bottom: 4px;">✅</div>
                        <div style="font-size: 11px; color: white; font-weight: 500;">Busca Concluída!</div>
                        <div style="font-size: 9px; color: rgba(255,255,255,0.7);">{} novas</div>
                    </div>
                """.format(search_status.get('total_novos', 0)), unsafe_allow_html=True)

        # Espaçador
        st.markdown("<div style='flex-grow: 1; min-height: 50px;'></div>", unsafe_allow_html=True)
        
        # Versão
        st.markdown("""
            <div style="text-align: center; padding: 16px 0; margin-top: auto;">
                <div style="font-size: 10px; color: rgba(255,255,255,0.3);">v2.3 • 2025</div>
            </div>
        """, unsafe_allow_html=True)

