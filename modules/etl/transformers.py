"""
Transformadores de dados para o pipeline ETL
Normalização, padronização e limpeza de dados de licitações
"""
import re
from typing import Dict, Any, Optional
from datetime import datetime


class LicitacaoTransformer:
    """Transformações específicas para licitações"""
    
    # Mapeamento de prefixos comuns para normalização
    PREFIXOS_ORGAOS = [
        "PREFEITURA MUNICIPAL DE ",
        "PREFEITURA DE ",
        "PM DE ",
        "MUNICIPIO DE ",
        "MUNICÍPIO DE ",
        "FUNDO MUNICIPAL DE SAUDE DE ",
        "FUNDO MUNICIPAL DE SAÚDE DE ",
        "FMS DE ",
        "SECRETARIA MUNICIPAL DE ",
        "CAMARA MUNICIPAL DE ",
        "CÂMARA MUNICIPAL DE ",
    ]
    
    UFS_VALIDAS = {
        'AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA',
        'MT', 'MS', 'MG', 'PA', 'PB', 'PR', 'PE', 'PI', 'RJ', 'RN',
        'RS', 'RO', 'RR', 'SC', 'SP', 'SE', 'TO'
    }
    
    @staticmethod
    def normalize_orgao(orgao: str) -> str:
        """
        Normaliza o nome do órgão removendo prefixos comuns
        
        Exemplo:
            "Prefeitura Municipal de Natal" -> "Natal"
            "PM DE PARNAMIRIM" -> "Parnamirim"
        """
        if not orgao:
            return ""
        
        orgao_upper = orgao.upper().strip()
        
        # Remove prefixos conhecidos
        for prefixo in LicitacaoTransformer.PREFIXOS_ORGAOS:
            if orgao_upper.startswith(prefixo):
                orgao_upper = orgao_upper[len(prefixo):]
                break
        
        # Capitaliza adequadamente
        return orgao_upper.title()
    
    @staticmethod
    def validate_uf(uf: Optional[str]) -> Optional[str]:
        """Valida e normaliza UF"""
        if not uf:
            return None
        
        uf_upper = uf.upper().strip()
        return uf_upper if uf_upper in LicitacaoTransformer.UFS_VALIDAS else None
    
    @staticmethod
    def extract_valor(texto: str) -> Optional[float]:
        """
        Extrai valor monetário de texto
        
        Exemplo:
            "R$ 1.234,56" -> 1234.56
            "1234.56" -> 1234.56
        """
        if not texto:
            return None
        
        # Remove caracteres não numéricos exceto . e ,
        texto_limpo = re.sub(r'[^\d,.]', '', str(texto))
        
        # Trata formato brasileiro (1.234,56 -> 1234.56)
        if ',' in texto_limpo and '.' in texto_limpo:
            texto_limpo = texto_limpo.replace('.', '').replace(',', '.')
        elif ',' in texto_limpo:
            texto_limpo = texto_limpo.replace(',', '.')
        
        try:
            return float(texto_limpo)
        except (ValueError, AttributeError):
            return None
    
    @staticmethod
    def parse_date(texto: str) -> Optional[datetime]:
        """
        Tenta fazer parse de data em vários formatos
        
        Formatos suportados:
            - DD/MM/YYYY
            - YYYY-MM-DD
            - DD-MM-YYYY
        """
        if not texto:
            return None
        
        formatos = [
            '%d/%m/%Y',
            '%Y-%m-%d',
            '%d-%m-%Y',
            '%d/%m/%Y %H:%M',
            '%Y-%m-%dT%H:%M:%S',
        ]
        
        for formato in formatos:
            try:
                return datetime.strptime(str(texto).strip(), formato)
            except (ValueError, AttributeError):
                continue
        
        return None
    
    @staticmethod
    def clean_text(texto: str) -> str:
        """Remove espaços extras, quebras de linha e caracteres especiais"""
        if not texto:
            return ""
        
        # Remove múltiplos espaços
        texto = re.sub(r'\s+', ' ', str(texto))
        
        # Remove espaços no início e fim
        return texto.strip()
    
    @staticmethod
    def extract_modalidade(texto: str) -> str:
        """Extrai e normaliza modalidade de licitação"""
        if not texto:
            return "Não Informada"
        
        texto_upper = texto.upper()
        
        # Mapeamento de modalidades conhecidas
        modalidades = {
            'PREGAO': 'Pregão Eletrônico',
            'PREGÃO': 'Pregão Eletrônico',
            'CONCORRENCIA': 'Concorrência',
            'CONCORRÊNCIA': 'Concorrência',
            'TOMADA DE PRECOS': 'Tomada de Preços',
            'TOMADA DE PREÇOS': 'Tomada de Preços',
            'CONVITE': 'Convite',
            'DISPENSA': 'Dispensa',
            'INEXIGIBILIDADE': 'Inexigibilidade',
        }
        
        for chave, valor in modalidades.items():
            if chave in texto_upper:
                return valor
        
        return texto.title()
    
    @staticmethod
    def deduplicate_key(licitacao: Dict[str, Any]) -> str:
        """
        Gera chave única para deduplicação
        
        Usa: orgao + modalidade + objeto (primeiros 100 chars) + data
        """
        orgao = licitacao.get('orgao', '')
        modalidade = licitacao.get('modalidade', '')
        objeto = licitacao.get('objeto', '')[:100]
        data = licitacao.get('data_publicacao', '')
        
        key_parts = [
            LicitacaoTransformer.normalize_orgao(orgao),
            modalidade,
            LicitacaoTransformer.clean_text(objeto),
            str(data)
        ]
        
        return '|'.join(key_parts).upper()


class ItemTransformer:
    """Transformações específicas para itens de licitação"""
    
    @staticmethod
    def normalize_unidade(unidade: str) -> str:
        """Normaliza unidades de medida"""
        if not unidade:
            return "UN"
        
        # Mapeamento de unidades comuns
        unidades = {
            'UNIDADE': 'UN',
            'UNID': 'UN',
            'UND': 'UN',
            'PC': 'UN',
            'PEÇA': 'UN',
            'METRO': 'M',
            'METROS': 'M',
            'LITRO': 'L',
            'LITROS': 'L',
            'QUILOGRAMA': 'KG',
            'QUILO': 'KG',
            'CAIXA': 'CX',
        }
        
        unidade_upper = unidade.upper().strip()
        return unidades.get(unidade_upper, unidade_upper)
    
    @staticmethod
    def extract_quantidade(texto: str) -> Optional[float]:
        """Extrai quantidade numérica de texto"""
        return LicitacaoTransformer.extract_valor(texto)
