"""
Cache de resultados do PNCP
Evita chamadas repetidas à API dentro de um período configurável
"""

import json
import os
import hashlib
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from modules.utils.logging_config import get_logger

logger = get_logger(__name__)

# Caminho do cache
BASE_DIR = Path(__file__).parent.parent.parent
CACHE_DIR = BASE_DIR / 'data' / 'cache'
PNCP_CACHE_FILE = CACHE_DIR / 'pncp_results_cache.json'

# Cache padrão: 30 minutos
DEFAULT_TTL_SECONDS = 1800


def _ensure_cache_dir():
    """Cria diretório de cache se não existir"""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _generate_cache_key(
    dias_busca: int,
    estados: List[str],
    termos_positivos: List[str] = None,
    apenas_abertas: bool = True
) -> str:
    """Gera chave única para os parâmetros de busca"""
    params = {
        'dias': dias_busca,
        'estados': sorted(estados) if estados else [],
        'termos': sorted(termos_positivos[:5]) if termos_positivos else [],
        'abertas': apenas_abertas,
    }
    params_str = json.dumps(params, sort_keys=True)
    return hashlib.sha256(params_str.encode()).hexdigest()[:16]


def get_cached_results(
    dias_busca: int,
    estados: List[str],
    termos_positivos: List[str] = None,
    apenas_abertas: bool = True,
    ttl_seconds: int = DEFAULT_TTL_SECONDS
) -> Optional[List[Dict[str, Any]]]:
    """
    Retorna resultados em cache se existirem e não estiverem expirados.
    
    Args:
        dias_busca: Dias de busca
        estados: Lista de UFs
        termos_positivos: Termos de busca
        apenas_abertas: Filtro de licitações abertas
        ttl_seconds: Tempo de vida do cache em segundos
    
    Returns:
        Lista de resultados ou None se cache inválido/expirado
    """
    _ensure_cache_dir()
    
    if not PNCP_CACHE_FILE.exists():
        return None
    
    try:
        with open(PNCP_CACHE_FILE, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)
        
        cache_key = _generate_cache_key(dias_busca, estados, termos_positivos, apenas_abertas)
        
        if cache_key not in cache_data:
            return None
        
        entry = cache_data[cache_key]
        cached_at = datetime.fromisoformat(entry['cached_at'])
        age_seconds = (datetime.now() - cached_at).total_seconds()
        
        if age_seconds > ttl_seconds:
            logger.info(f"Cache PNCP expirado ({age_seconds:.0f}s > {ttl_seconds}s)")
            return None
        
        results = entry.get('results', [])
        logger.info(f"✅ Cache PNCP válido: {len(results)} resultados (idade: {age_seconds:.0f}s)")
        return results
    
    except Exception as e:
        logger.warning(f"Erro ao ler cache PNCP: {e}")
        return None


def save_to_cache(
    results: List[Dict[str, Any]],
    dias_busca: int,
    estados: List[str],
    termos_positivos: List[str] = None,
    apenas_abertas: bool = True
) -> bool:
    """
    Salva resultados no cache.
    
    Returns:
        True se salvou com sucesso
    """
    _ensure_cache_dir()
    
    cache_key = _generate_cache_key(dias_busca, estados, termos_positivos, apenas_abertas)
    
    try:
        # Carrega cache existente
        cache_data = {}
        if PNCP_CACHE_FILE.exists():
            try:
                with open(PNCP_CACHE_FILE, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
            except Exception:
                cache_data = {}
        
        # Limpa entradas antigas (mais de 2 horas)
        now = datetime.now()
        keys_to_remove = []
        for key, entry in cache_data.items():
            try:
                cached_at = datetime.fromisoformat(entry.get('cached_at', ''))
                if (now - cached_at).total_seconds() > 7200:  # 2 horas
                    keys_to_remove.append(key)
            except Exception:
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del cache_data[key]
        
        # Adiciona nova entrada
        cache_data[cache_key] = {
            'cached_at': now.isoformat(),
            'dias_busca': dias_busca,
            'estados': estados,
            'count': len(results),
            'results': results,
        }
        
        # Salva
        with open(PNCP_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, default=str)
        
        logger.info(f"Cache PNCP salvo: {len(results)} resultados")
        return True
    
    except Exception as e:
        logger.error(f"Erro ao salvar cache PNCP: {e}")
        return False


def invalidate_cache() -> bool:
    """Invalida todo o cache PNCP"""
    try:
        if PNCP_CACHE_FILE.exists():
            os.remove(PNCP_CACHE_FILE)
            logger.info("Cache PNCP invalidado")
        return True
    except Exception as e:
        logger.error(f"Erro ao invalidar cache: {e}")
        return False


# Lista de CNPJs de órgãos prioritários (hospitais, secretarias de saúde)
# Estes órgãos serão buscados diretamente além da busca por termo
ORGAOS_PRIORITARIOS = {
    # RN - Rio Grande do Norte
    "08241754000145": "SESAP/RN - Secretaria de Estado da Saúde Pública",
    "14031955000110": "RN FES - Fundo Estadual de Saúde (Custeio SUS)",
    "08241739000105": "FUSERN - Fundo de Saúde do RN",
    "08241754013395": "FUSERN - Fundo de Saúde (filial)",
    "24365710000183": "UFRN - Universidade Federal do RN",
    "08242166000126": "Hospital Giselda Trigueiro - Natal/RN",
    "08365017000129": "Hospital Universitário Onofre Lopes - HUOL",
    "08167974000172": "Hospital Monsenhor Walfredo Gurgel",
    "08429630000135": "Hospital Regional Tarcísio Maia - Mossoró",
    "09349355000113": "Maternidade Escola Januário Cicco",
    "08154417000100": "Prefeitura Municipal de Natal",
    "00394429018581": "BANT - Base Aérea de Natal",
    "00394429020560": "Ala 10 - Comando da Aeronáutica (Parnamirim/RN)",
    
    # PB - Paraíba
    "08778268000156": "SES/PB - Secretaria de Estado da Saúde",
    "09052779000105": "Hospital de Trauma de João Pessoa",
    "08948420000164": "Hospital Universitário Lauro Wanderley - HULW",
    "09114478000119": "Hospital Edson Ramalho - João Pessoa",
    "08903232000144": "Hospital Regional de Campina Grande",
    "08922948000117": "Maternidade Frei Damião - João Pessoa",
    "09118658000195": "Complexo Hospitalar Clementino Fraga",
    
    # PE - Pernambuco
    "10572071000128": "SES/PE - Secretaria Estadual de Saúde",
    "10571940000180": "Hospital da Restauração",
    "24134488000108": "Hospital das Clínicas - UFPE",
    "10572048000168": "Hospital Getúlio Vargas - Recife",
    "10572022000219": "Hospital Agamenon Magalhães",
    "10571890000135": "Hospital Barão de Lucena",
    "09680299000182": "Hospital Universitário Oswaldo Cruz",
    "10566440000127": "HEMOPE - Hemocentro de Pernambuco",
    
    # AL - Alagoas
    "12200176000171": "SESAU/AL - Secretaria de Estado da Saúde",
    "07432517000103": "Hospital Escola Dr. Helvio Auto",
    "12307187000150": "Hospital Geral do Estado - Maceió",
    "07300838000103": "Hospital Universitário Prof. Alberto Antunes",
    "12264842000150": "Maternidade Escola Santa Mônica",
    "04034401000154": "HEMOAL - Centro de Hematologia e Hemoterapia",
}


def get_orgaos_prioritarios() -> Dict[str, str]:
    """Retorna dicionário de CNPJs prioritários"""
    return ORGAOS_PRIORITARIOS.copy()


def add_orgao_prioritario(cnpj: str, nome: str) -> bool:
    """Adiciona um órgão à lista de prioritários"""
    cnpj_clean = cnpj.replace('.', '').replace('-', '').replace('/', '')
    ORGAOS_PRIORITARIOS[cnpj_clean] = nome
    return True
