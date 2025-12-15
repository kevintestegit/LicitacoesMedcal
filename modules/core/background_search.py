"""
Módulo de Busca em Background
Permite executar buscas de licitações em segundo plano,
com status persistido no banco e notificações ao finalizar.
"""
import threading
import time
from datetime import datetime
from modules.database.database import get_session, AgentRun
from modules.core.search_engine import SearchEngine


class BackgroundSearchManager:
    """Gerencia buscas em background com status persistido"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        # Singleton para garantir uma única instância
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._current_thread = None
        self._current_run_id = None
        
        # Limpa execuções órfãs (ficaram "running" após restart)
        self._cleanup_orphan_runs()
    
    def _cleanup_orphan_runs(self):
        """Marca como 'cancelled' qualquer execução 'running' sem thread ativa"""
        try:
            session = get_session()
            orphans = session.query(AgentRun).filter_by(status='running').all()
            
            for run in orphans:
                # Se não há thread ativa, é órfão
                if not (self._current_thread and self._current_thread.is_alive()):
                    run.status = 'cancelled'
                    run.finished_at = datetime.now()
                    run.resumo = "Cancelado: sistema reiniciado"
                    print(f"[BACKGROUND] Execução órfã {run.id} marcada como cancelada")
            
            session.commit()
            session.close()
        except Exception as e:
            print(f"[BACKGROUND] Erro ao limpar órfãos: {e}")
    
    def is_running(self) -> bool:
        """Verifica se há uma busca em andamento"""
        if self._current_thread and self._current_thread.is_alive():
            return True
        
        # Também verifica no banco (para caso de restart do app)
        session = get_session()
        running = session.query(AgentRun).filter_by(status='running').first()
        session.close()
        
        return running is not None
    
    def get_current_status(self) -> dict:
        """Retorna o status atual da busca"""
        session = get_session()
        
        # Busca a última execução
        run = session.query(AgentRun).order_by(AgentRun.id.desc()).first()
        
        if not run:
            session.close()
            return {"status": "idle", "message": "Nenhuma busca realizada"}
        
        result = {
            "run_id": run.id,
            "status": run.status,
            "started_at": run.started_at,
            "finished_at": run.finished_at,
            "total_coletado": run.total_coletado,
            "total_novos": run.total_novos,
            "resumo": run.resumo
        }
        
        if run.status == 'running':
            elapsed = (datetime.now() - run.started_at).seconds
            result["message"] = f"Busca em andamento... ({elapsed}s)"
            result["elapsed_seconds"] = elapsed
        elif run.status == 'completed':
            result["message"] = f"Concluído: {run.total_novos} novas licitações"
        elif run.status == 'error':
            result["message"] = f"Erro: {run.resumo}"
        else:
            result["message"] = run.resumo or "Status desconhecido"
        
        session.close()
        return result
    
    def start_search(self, dias=60, estados=['RN', 'PB', 'PE', 'AL'], fontes=None) -> dict:
        """
        Inicia uma busca em background.
        
        Args:
            dias: Dias de histórico
            estados: Lista de UFs
            fontes: Lista de fontes. Ex: ['pncp'], ['pncp', 'femurn']. None = todas.
        """
        
        if self.is_running():
            return {
                "success": False,
                "message": "Já existe uma busca em andamento. Aguarde a conclusão."
            }
        
        # Cria registro no banco
        session = get_session()
        fontes_str = ', '.join(fontes) if fontes else 'TODAS'
        run = AgentRun(
            started_at=datetime.now(),
            status='running',
            resumo=f"Buscando em {', '.join(estados)} (fontes: {fontes_str})..."
        )
        session.add(run)
        session.commit()
        run_id = run.id
        session.close()
        
        self._current_run_id = run_id
        
        # Inicia thread de busca
        self._current_thread = threading.Thread(
            target=self._execute_search,
            args=(run_id, dias, estados, fontes),
            daemon=True
        )
        self._current_thread.start()
        
        return {
            "success": True,
            "run_id": run_id,
            "message": "Busca iniciada em background. Você pode navegar pelo sistema."
        }
    
    def _execute_search(self, run_id: int, dias: int, estados: list, fontes: list = None):
        """Executa a busca (roda em thread separada)"""
        session = get_session()
        run = session.query(AgentRun).get(run_id)
        
        try:
            engine = SearchEngine()
            
            # Atualiza status
            run.resumo = "Conectando às fontes..."
            session.commit()
            
            # Executa busca (passa fontes selecionadas)
            novos = engine.execute_full_search(dias=dias, estados=estados, fontes=fontes)
            
            # Atualiza resultado
            run.status = 'completed'
            run.finished_at = datetime.now()
            run.total_novos = novos
            run.resumo = f"✅ Concluído! {novos} novas licitações importadas."
            session.commit()
            
            # Envia notificação de conclusão via WhatsApp
            self._notify_completion(session, novos)
            
            # Log
            print(f"[BACKGROUND] Busca {run_id} concluída: {novos} novos")
            
        except Exception as e:
            run.status = 'error'
            run.finished_at = datetime.now()
            run.resumo = f"❌ Erro: {str(e)[:200]}"
            session.commit()
            print(f"[BACKGROUND] Erro na busca {run_id}: {e}")
        
        finally:
            session.close()
            self._current_run_id = None
    
    def _notify_completion(self, session, novos: int):
        """Envia notificação via WhatsApp quando a busca termina"""
        try:
            import json
            from modules.utils.notifications import WhatsAppNotifier
            from modules.database.database import Configuracao
            
            # Busca contatos
            config_contacts = session.query(Configuracao).filter_by(chave='whatsapp_contacts').first()
            
            if not config_contacts or not config_contacts.valor:
                return
            
            try:
                contacts_list = json.loads(config_contacts.valor)
            except:
                return
            
            if not contacts_list:
                return
            
            # Monta mensagem de conclusão
            msg = f"""🔔 *MEDCAL - Busca Concluída*

✅ Varredura finalizada com sucesso!
📊 *{novos}* novas licitações encontradas.

🔗 Acesse o Dashboard: https://x447rc96-8501.brs.devtunnels.ms/"""
            
            # Envia para todos os contatos
            for contact in contacts_list:
                try:
                    notifier = WhatsAppNotifier(contact.get('phone'), contact.get('apikey'))
                    notifier.enviar_mensagem(msg)
                except Exception as e:
                    print(f"Erro ao notificar {contact.get('nome')}: {e}")
                    
        except Exception as e:
            print(f"Erro na notificação de conclusão: {e}")
    
    def cancel_search(self) -> dict:
        """Tenta cancelar a busca atual (marca como cancelada no banco)"""
        if not self.is_running():
            return {"success": False, "message": "Nenhuma busca em andamento"}
        
        session = get_session()
        run = session.query(AgentRun).filter_by(status='running').first()
        
        if run:
            run.status = 'cancelled'
            run.finished_at = datetime.now()
            run.resumo = "Busca cancelada pelo usuário"
            session.commit()
        
        session.close()
        
        return {"success": True, "message": "Busca marcada como cancelada"}


# Instância global (singleton)
background_manager = BackgroundSearchManager()
