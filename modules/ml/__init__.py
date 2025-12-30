"""
Módulo ML (Machine Learning) para classificação de licitações
"""

from .preprocessor import TextPreprocessor, FeatureExtractor
from .classifier import LicitacaoClassifier

__all__ = [
    'TextPreprocessor',
    'FeatureExtractor',
    'LicitacaoClassifier',
]
