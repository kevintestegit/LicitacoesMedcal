"""
Cache de notificações WhatsApp para evitar envio duplicado.
Persiste em arquivo JSON separado do banco de dados principal.
"""
import json
import os
from datetime import datetime, date
from pathlib import Path


class NotificationCache:
    """
    Cache persistente para rastrear quais licitações já tiveram notificação enviada.
    Usa arquivo JSON separado do banco SQLite para evitar reenvio ao limpar o banco.
    """
    
    def __init__(self, cache_dir: str = None):
        """
        Inicializa o cache de notificações.
        
        Args:
            cache_dir: Diretório para salvar o cache. Default: data/
        """
        if cache_dir is None:
            # Usa o diretório data/ do projeto
            base_dir = Path(__file__).parent.parent.parent
            cache_dir = base_dir / "data"
        
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / "whatsapp_notifications_sent.json"
        self._cache = self._load_cache()
    
    def _load_cache(self) -> dict:
        """Carrega o cache do arquivo JSON."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {"sent": {}, "last_cleanup": None}
        return {"sent": {}, "last_cleanup": None}
    
    def _save_cache(self):
        """Salva o cache no arquivo JSON."""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self._cache, f, indent=2, ensure_ascii=False)
        except IOError as e:
            print(f"[NotificationCache] Erro ao salvar cache: {e}")
    
    def was_sent_today(self, pncp_id: str) -> bool:
        """
        Verifica se uma licitação já foi notificada hoje.
        """
        today = date.today().isoformat()
        sent_today = self._cache.get("sent", {}).get(today, [])
        return pncp_id in sent_today

    def was_already_sent(self, pncp_id: str) -> bool:
        """
        Verifica se uma licitação já foi notificada em qualquer dia registrado no cache.
        Ideal para evitar repetição quando o banco é apagado.
        """
        if "sent" not in self._cache:
            return False
            
        for date_key, sent_list in self._cache["sent"].items():
            if pncp_id in sent_list:
                return True
        return False
    
    def mark_as_sent(self, pncp_id: str):
        """
        Marca uma licitação como notificada hoje.
        
        Args:
            pncp_id: ID único da licitação
        """
        today = date.today().isoformat()
        
        if "sent" not in self._cache:
            self._cache["sent"] = {}
        
        if today not in self._cache["sent"]:
            self._cache["sent"][today] = []
        
        if pncp_id not in self._cache["sent"][today]:
            self._cache["sent"][today].append(pncp_id)
            self._save_cache()
    
    def mark_batch_as_sent(self, pncp_ids: list):
        """
        Marca várias licitações como notificadas hoje.
        
        Args:
            pncp_ids: Lista de IDs de licitações
        """
        today = date.today().isoformat()
        
        if "sent" not in self._cache:
            self._cache["sent"] = {}
        
        if today not in self._cache["sent"]:
            self._cache["sent"][today] = []
        
        for pncp_id in pncp_ids:
            if pncp_id not in self._cache["sent"][today]:
                self._cache["sent"][today].append(pncp_id)
        
        self._save_cache()
    
    def filter_not_sent_today(self, pncp_ids: list) -> list:
        """
        Filtra uma lista retornando apenas os que NÃO foram enviados hoje.
        
        Args:
            pncp_ids: Lista de IDs para verificar
        
        Returns:
            Lista de IDs que ainda não foram notificados hoje
        """
        return [pid for pid in pncp_ids if not self.was_sent_today(pid)]
    
    def cleanup_old_entries(self, days_to_keep: int = 7):
        """
        Remove entradas antigas do cache para não crescer indefinidamente.
        
        Args:
            days_to_keep: Quantidade de dias para manter no cache
        """
        from datetime import timedelta
        
        cutoff = (date.today() - timedelta(days=days_to_keep)).isoformat()
        
        if "sent" not in self._cache:
            return
        
        dates_to_remove = [d for d in self._cache["sent"].keys() if d < cutoff]
        
        for d in dates_to_remove:
            del self._cache["sent"][d]
        
        self._cache["last_cleanup"] = datetime.now().isoformat()
        self._save_cache()
    
    def get_stats(self) -> dict:
        """Retorna estatísticas do cache."""
        today = date.today().isoformat()
        sent_today = self._cache.get("sent", {}).get(today, [])
        total_days = len(self._cache.get("sent", {}))
        
        return {
            "sent_today": len(sent_today),
            "total_days_tracked": total_days,
            "last_cleanup": self._cache.get("last_cleanup")
        }


# Instância global do cache
notification_cache = NotificationCache()
