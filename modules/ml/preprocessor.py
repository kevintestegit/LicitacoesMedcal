"""
Preprocessador de texto para ML/NLP
Limpeza, normalização e vetorização de textos de licitações
"""
import re
import unicodedata
from typing import List, Dict, Any
import numpy as np


class TextPreprocessor:
    """
    Preprocessador de texto para análise de licitações
    Remove stopwords, normaliza texto e prepara para vetorização
    """
    
    STOPWORDS_PT = {
        'a', 'o', 'e', 'de', 'da', 'do', 'em', 'para', 'com', 'por', 'um', 'uma',
        'os', 'as', 'dos', 'das', 'ao', 'aos', 'à', 'às', 'pelo', 'pela', 'pelos',
        'pelas', 'na', 'no', 'nas', 'nos', 'que', 'se', 'é', 'foi', 'são', 'mais',
        'como', 'mas', 'seu', 'sua', 'seus', 'suas', 'ou', 'quando', 'muito', 'já',
        'também', 'só', 'pelo', 'pela', 'até', 'isso', 'ela', 'entre', 'depois',
        'sem', 'mesmo', 'aos', 'ter', 'seus', 'quem', 'nas', 'me', 'esse', 'eles',
        'você', 'essa', 'num', 'nem', 'suas', 'meu', 'minha', 'numa', 'pelos',
        'elas', 'qual', 'nós', 'lhe', 'deles', 'essas', 'esses', 'pelas', 'este'
    }
    
    @staticmethod
    def remove_accents(text: str) -> str:
        """Remove acentuação mantendo significado"""
        try:
            text = unicodedata.normalize('NFD', text)
            text = text.encode('ascii', 'ignore').decode('utf-8')
            return text
        except:
            return text
    
    @staticmethod
    def clean_text(text: str) -> str:
        """Limpa texto removendo caracteres especiais e normalizando espaços"""
        if not text:
            return ""
        
        # Remove URLs
        text = re.sub(r'http\S+|www\S+', '', text)
        
        # Remove emails
        text = re.sub(r'\S+@\S+', '', text)
        
        # Remove números isolados (mas mantém códigos alfanuméricos)
        text = re.sub(r'\s\d+\s',' ', text)
        
        # Remove caracteres especiais (mantém letras, números e espaços)
        text = re.sub(r'[^\w\s]', ' ', text)
        
        # Normaliza espaços múltiplos
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()
    
    @staticmethod
    def tokenize(text: str, remove_stopwords: bool = True) -> List[str]:
        """Tokeniza texto em palavras"""
        if not text:
            return []
        
        # Converte para minúsculas
        text = text.lower()
        
        # Remove acentos
        text = TextPreprocessor.remove_accents(text)
        
        # Limpa texto
        text = TextPreprocessor.clean_text(text)
        
        # Tokeniza
        tokens = text.split()
        
        # Remove stopwords se solicitado
        if remove_stopwords:
            tokens = [t for t in tokens if t not in TextPreprocessor.STOPWORDS_PT and len(t) > 2]
        
        return tokens
    
    @staticmethod
    def preprocess_for_ml(text: str) -> str:
        """
        Preprocessa texto para ML mantendo informações relevantes
        Retorna texto limpo e normalizado como string
        """
        tokens = TextPreprocessor.tokenize(text, remove_stopwords=True)
        return ' '.join(tokens)
    
    @staticmethod
    def extract_features_from_licitacao(licitacao: Dict[str, Any]) -> str:
        """
        Extrai texto relevante de uma licitação para análise ML
        Combina objeto, órgão e modalidade
        """
        parts = []
        
        # Objeto (mais peso) - repete 3x
        objeto = licitacao.get('objeto', '')
        if objeto:
            parts.extend([objeto] * 3)
        
        # Órgão
        orgao = licitacao.get('orgao', '')
        if orgao:
            parts.append(orgao)
        
        # Modalidade
        modalidade = licitacao.get('modalidade', '')
        if modalidade:
            parts.append(modalidade)
        
        # Itens (se houver)
        itens = licitacao.get('itens', [])
        for item in itens[:5]:  # Primeiros 5 itens
            desc = item.get('descricao', '')
            if desc:
                parts.append(desc)
        
        # Combina tudo
        combined_text = ' '.join(parts)
        return TextPreprocessor.preprocess_for_ml(combined_text)


class FeatureExtractor:
    """Extrai features numéricas de licitações para ML"""
    
    @staticmethod
    def extract_numerical_features(licitacao: Dict[str, Any]) -> np.ndarray:
        """
        Extrai features numéricas de uma licitação
        
        Features:
        0. Tem objeto (bool)
        1. Tamanho do objeto (log)
        2. Número de itens
        3. Modalidade é Pregão (bool)
        4. UF is RN (bool)
        5. Tem data encerramento (bool)
        6. Dias restantes (normalizado)
        """
        features = []
        
        # Feature 0: Tem objeto
        objeto = licitacao.get('objeto', '')
        features.append(1.0 if objeto else 0.0)
        
        # Feature 1: Tamanho do objeto (log)
        if objeto:
            features.append(np.log1p(len(objeto)))
        else:
            features.append(0.0)
        
        # Feature 2: Número de itens
        num_itens = len(licitacao.get('itens', []))
        features.append(min(num_itens, 100) / 100.0)  # Normalizado
        
        # Feature 3: Modalidade é Pregão
        modalidade = licitacao.get('modalidade', '').upper()
        features.append(1.0 if 'PREGAO' in modalidade or 'PREGÃO' in modalidade else 0.0)
        
        # Feature 4: UF é RN
        uf = licitacao.get('uf', '').upper()
        features.append(1.0 if uf == 'RN' else 0.0)
        
        # Feature 5: Tem data de encerramento
        data_enc = licitacao.get('data_encerramento_proposta')
        features.append(1.0 if data_enc else 0.0)
        
        # Feature 6: Dias restantes (normalizado)
        dias_restantes = licitacao.get('dias_restantes', 0)
        if dias_restantes:
            features.append(max(0, min(dias_restantes, 30)) / 30.0)
        else:
            features.append(0.0)
        
        return np.array(features, dtype=np.float32)
