"""
Pipeline ETL para processamento de dados de licitações
Extract → Transform → Load
"""
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
from modules.etl.transformers import LicitacaoTransformer, ItemTransformer
from modules.utils.logging_config import get_logger

logger = get_logger(__name__)


class ETLPipeline:
    """
    Pipeline modular para transformação de dados de licitações
    
    Uso:
        pipeline = ETLPipeline()
        pipeline.add_transform(remover_duplicatas)
        pipeline.add_transform(normalizar_orgaos)
        dados_limpos = pipeline.run(dados_brutos)
    """
    
    def __init__(self):
        self.transforms: List[Callable] = []
        self.stats = {
            'processados': 0,
            'duplicados_removidos': 0,
            'erros': 0,
            'transformacoes': 0
        }
    
    def add_transform(self, transform_func: Callable):
        """Adiciona uma transformação ao pipeline"""
        self.transforms.append(transform_func)
        return self
    
    def run(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Executa o pipeline completo"""
        self.stats['processados'] = len(data)
        logger.info(f"Iniciando pipeline ETL com {len(data)} registros")
        
        result = data
        for i, transform in enumerate(self.transforms):
            try:
                result = transform(result)
                self.stats['transformacoes'] += 1
                logger.debug(f"Transformação {i+1}/{len(self.transforms)} aplicada: {len(result)} registros")
            except Exception as e:
                logger.error(f"Erro na transformação {transform.__name__}: {e}", exc_info=True)
                self.stats['erros'] += 1
        
        logger.info(f"Pipeline concluído: {len(result)} registros finais")
        return result
    
    def get_stats(self) -> Dict[str, int]:
        """Retorna estatísticas do pipeline"""
        return self.stats.copy()


# === TRANSFORMAÇÕES PRÉ-DEFINIDAS ===

def remove_duplicates(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove duplicatas baseado em chave única"""
    seen_keys = set()
    unique_data = []
    
    for item in data:
        key = LicitacaoTransformer.deduplicate_key(item)
        if key not in seen_keys:
            seen_keys.add(key)
            unique_data.append(item)
    
    duplicados = len(data) - len(unique_data)
    if duplicados > 0:
        logger.info(f"Removidos {duplicados} registros duplicados")
    
    return unique_data


def normalize_licitacoes(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normaliza campos de licitações"""
    normalized = []
    
    for item in data:
        try:
            # Normaliza órgão
            if 'orgao' in item:
                item['orgao_original'] = item['orgao']
                item['orgao'] = LicitacaoTransformer.normalize_orgao(item['orgao'])
            
            # Valida e normaliza UF
            if 'uf' in item:
                item['uf'] = LicitacaoTransformer.validate_uf(item['uf'])
            
            # Normaliza modalidade
            if 'modalidade' in item:
                item['modalidade'] = LicitacaoTransformer.extract_modalidade(item['modalidade'])
            
            # Limpa objeto
            if 'objeto' in item:
                item['objeto'] = LicitacaoTransformer.clean_text(item['objeto'])
            
            # Normaliza datas
            date_fields = ['data_publicacao', 'data_sessao', 'data_encerramento_proposta']
            for field in date_fields:
                if field in item and isinstance(item[field], str):
                    parsed_date = LicitacaoTransformer.parse_date(item[field])
                    if parsed_date:
                        item[field] = parsed_date
            
            normalized.append(item)
        except Exception as e:
            logger.warning(f"Erro ao normalizar item: {e}")
            # Mantém o item original se houver erro
            normalized.append(item)
    
    return normalized


def validate_required_fields(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove registros sem campos obrigatórios"""
    required_fields = ['orgao', 'objeto']
    valid_data = []
    
    for item in data:
        if all(field in item and item[field] for field in required_fields):
            valid_data.append(item)
        else:
            logger.debug(f"Registro inválido removido: campos obrigatórios ausentes")
    
    removidos = len(data) - len(valid_data)
    if removidos > 0:
        logger.info(f"Removidos {removidos} registros inválidos")
    
    return valid_data


def enrich_metadata(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Adiciona metadados úteis"""
    for item in data:
        # Adiciona timestamp de processamento
        item['etl_processed_at'] = datetime.now()
        
        # Adiciona flag de urgência se tiver data de encerramento
        if 'data_encerramento_proposta' in item:
            try:
                data_enc = item['data_encerramento_proposta']
                if isinstance(data_enc, datetime):
                    dias_restantes = (data_enc - datetime.now()).days
                    item['dias_restantes'] = dias_restantes
                    item['urgente'] = dias_restantes <= 5
            except:
                pass
    
    return data


# === PIPELINE PADRÃO ===

def create_default_pipeline() -> ETLPipeline:
    """Cria pipeline padrão para licitações"""
    pipeline = ETLPipeline()
    pipeline.add_transform(validate_required_fields)
    pipeline.add_transform(normalize_licitacoes)
    pipeline.add_transform(remove_duplicates)
    pipeline.add_transform(enrich_metadata)
    return pipeline


def process_licitacoes(raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Função de conveniência para processar licitações com pipeline padrão
    
    Args:
        raw_data: Lista de dicionários com dados brutos de licitações
        
    Returns:
        Lista de dicionários com dados processados e limpos
    """
    pipeline = create_default_pipeline()
    return pipeline.run(raw_data)
