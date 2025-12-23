"""
Módulo de Métricas para Scrapers
Registra estatísticas de execução para monitoramento e otimização
"""

import json
import os
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict
from pathlib import Path

from modules.utils.logging_config import get_logger

logger = get_logger(__name__)

# Caminho do arquivo de métricas
BASE_DIR = Path(__file__).parent.parent.parent
METRICS_FILE = BASE_DIR / 'data' / 'scraper_metrics.json'


@dataclass
class ScraperRunMetrics:
    """Métricas de uma execução de scraper"""
    run_id: str
    fonte: str  # 'pncp', 'femurn', 'famup', etc
    inicio: str
    fim: Optional[str] = None
    duracao_segundos: Optional[float] = None
    
    # Contadores
    total_coletado: int = 0
    total_duplicados: int = 0
    total_filtrados: int = 0
    total_erros: int = 0
    total_retries: int = 0
    
    # Detalhes de erro
    erros: List[str] = None
    
    # Status
    sucesso: bool = True
    mensagem: Optional[str] = None
    
    def __post_init__(self):
        if self.erros is None:
            self.erros = []


class ScraperMetricsCollector:
    """Coletor de métricas para scrapers"""
    
    def __init__(self):
        self._current_run: Optional[ScraperRunMetrics] = None
        self._ensure_data_dir()
    
    def _ensure_data_dir(self):
        """Garante que o diretório data existe"""
        METRICS_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    def start_run(self, fonte: str) -> str:
        """Inicia uma nova execução e retorna o run_id"""
        run_id = f"{fonte}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self._current_run = ScraperRunMetrics(
            run_id=run_id,
            fonte=fonte,
            inicio=datetime.now().isoformat()
        )
        logger.info(f"Iniciando run de scraper: {run_id}")
        return run_id
    
    def record_collected(self, count: int = 1):
        """Registra itens coletados"""
        if self._current_run:
            self._current_run.total_coletado += count
    
    def record_duplicate(self, count: int = 1):
        """Registra itens duplicados (já existentes)"""
        if self._current_run:
            self._current_run.total_duplicados += count
    
    def record_filtered(self, count: int = 1):
        """Registra itens filtrados (removidos por regra)"""
        if self._current_run:
            self._current_run.total_filtrados += count
    
    def record_error(self, error_msg: str):
        """Registra um erro"""
        if self._current_run:
            self._current_run.total_erros += 1
            self._current_run.erros.append(error_msg[:200])  # Limita tamanho
            logger.warning(f"Erro registrado: {error_msg[:100]}")
    
    def record_retry(self):
        """Registra uma tentativa de retry"""
        if self._current_run:
            self._current_run.total_retries += 1
    
    def end_run(self, sucesso: bool = True, mensagem: str = None) -> Optional[ScraperRunMetrics]:
        """Finaliza a execução e salva métricas"""
        if not self._current_run:
            return None
        
        fim = datetime.now()
        inicio = datetime.fromisoformat(self._current_run.inicio)
        
        self._current_run.fim = fim.isoformat()
        self._current_run.duracao_segundos = (fim - inicio).total_seconds()
        self._current_run.sucesso = sucesso
        self._current_run.mensagem = mensagem
        
        # Salva no arquivo
        self._save_metrics(self._current_run)
        
        logger.info(
            f"Run {self._current_run.run_id} finalizado: "
            f"coletados={self._current_run.total_coletado}, "
            f"dupes={self._current_run.total_duplicados}, "
            f"erros={self._current_run.total_erros}, "
            f"duracao={self._current_run.duracao_segundos:.1f}s"
        )
        
        result = self._current_run
        self._current_run = None
        return result
    
    def _save_metrics(self, metrics: ScraperRunMetrics):
        """Salva métricas no arquivo JSON"""
        try:
            # Carrega histórico existente
            history = self._load_history()
            
            # Adiciona nova métrica
            history.append(asdict(metrics))
            
            # Mantém apenas últimas 100 execuções
            history = history[-100:]
            
            # Salva
            with open(METRICS_FILE, 'w', encoding='utf-8') as f:
                json.dump(history, f, indent=2, ensure_ascii=False)
        
        except Exception as e:
            logger.error(f"Erro ao salvar métricas: {e}")
    
    def _load_history(self) -> List[Dict]:
        """Carrega histórico de métricas"""
        if not METRICS_FILE.exists():
            return []
        
        try:
            with open(METRICS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []
    
    def get_recent_runs(self, fonte: str = None, limit: int = 10) -> List[Dict]:
        """Retorna execuções recentes, opcionalmente filtradas por fonte"""
        history = self._load_history()
        
        if fonte:
            history = [h for h in history if h.get('fonte') == fonte]
        
        return history[-limit:]
    
    def get_stats_summary(self, fonte: str = None) -> Dict:
        """Retorna resumo estatístico das execuções"""
        history = self._load_history()
        
        if fonte:
            history = [h for h in history if h.get('fonte') == fonte]
        
        if not history:
            return {'total_runs': 0}
        
        total_coletado = sum(h.get('total_coletado', 0) for h in history)
        total_erros = sum(h.get('total_erros', 0) for h in history)
        total_retries = sum(h.get('total_retries', 0) for h in history)
        runs_sucesso = sum(1 for h in history if h.get('sucesso', False))
        
        duracoes = [h.get('duracao_segundos', 0) for h in history if h.get('duracao_segundos')]
        duracao_media = sum(duracoes) / len(duracoes) if duracoes else 0
        
        return {
            'total_runs': len(history),
            'runs_sucesso': runs_sucesso,
            'taxa_sucesso': (runs_sucesso / len(history) * 100) if history else 0,
            'total_coletado': total_coletado,
            'total_erros': total_erros,
            'total_retries': total_retries,
            'duracao_media_segundos': round(duracao_media, 1),
        }


# Instância global
scraper_metrics = ScraperMetricsCollector()


def retry_with_backoff(
    func,
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: tuple = (Exception,),
    on_retry=None
):
    """
    Decorator/função para retry com backoff exponencial.
    
    Args:
        func: Função a executar
        max_attempts: Número máximo de tentativas
        initial_delay: Delay inicial em segundos
        backoff_factor: Fator de multiplicação do delay
        exceptions: Tupla de exceções para capturar
        on_retry: Callback opcional chamado a cada retry
    
    Returns:
        Resultado da função ou levanta última exceção
    """
    import time
    
    delay = initial_delay
    last_exception = None
    
    for attempt in range(1, max_attempts + 1):
        try:
            return func()
        except exceptions as e:
            last_exception = e
            
            if attempt == max_attempts:
                logger.error(f"Falha após {max_attempts} tentativas: {e}")
                raise
            
            if on_retry:
                on_retry(attempt, e)
            
            scraper_metrics.record_retry()
            logger.warning(f"Tentativa {attempt}/{max_attempts} falhou: {e}. Retry em {delay:.1f}s")
            time.sleep(delay)
            delay *= backoff_factor
    
    raise last_exception
