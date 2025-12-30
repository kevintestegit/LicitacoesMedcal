"""
Classificador de relevância de licitações usando Machine Learning
Usa TF-IDF + RandomForest para classificar licitações como relevantes ou não
"""
import os
import joblib
import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score, f1_score

from modules.ml.preprocessor import TextPreprocessor, FeatureExtractor
from modules.utils.logging_config import get_logger

logger = get_logger(__name__)


class LicitacaoClassifier:
    """
    Classificador de relevância de licitações
    
    Usa TF-IDF para vetorizar texto + features numéricas + RandomForest
    """
    
    def __init__(self, model_path: Optional[str] = None):
        """
        Args:
            model_path: Caminho para modelo salvo. Se None, usa padrão.
        """
        self.model_path = model_path or "data/models/licitacao_classifier.pkl"
        self.vectorizer: Optional[TfidfVectorizer] = None
        self.classifier: Optional[RandomForestClassifier] = None
        self.trained = False
        
        # Tenta carregar modelo existente
        self.load_model()
    
    def train(self, licitacoes: List[Dict[str, Any]], labels: List[int]) -> Dict[str, Any]:
        """
        Treina o classificador com dados históricos
        
        Args:
            licitacoes: Lista de dicionários com dados de licitações
            labels: Lista de labels (1 = relevante/salva, 0 = ignorada)
            
        Returns:
            Dict com métricas de treinamento
        """
        if len(licitacoes) != len(labels):
            raise ValueError("Número de licitações e labels deve ser igual")
        
        if len(licitacoes) < 10:
            raise ValueError("Mínimo de 10 licitações necessárias para treinamento")
        
        logger.info(f"Iniciando treinamento com {len(licitacoes)} licitações")
        
        # Extrai textos
        textos = [TextPreprocessor.extract_features_from_licitacao(lic) for lic in licitacoes]
        
        # Vetoriza textos com TF-IDF
        self.vectorizer = TfidfVectorizer(
            max_features=500,
            ngram_range=(1, 2),
            min_df=2,
            max_df=0.8
        )
        X_text = self.vectorizer.fit_transform(textos).toarray()
        
        # Extrai features numéricas
        X_numerical = np.array([
            FeatureExtractor.extract_numerical_features(lic)
            for lic in licitacoes
        ])
        
        # Combina features
        X = np.hstack([X_text, X_numerical])
        y = np.array(labels)
        
        logger.info(f"Features extraídas: {X.shape[1]} (texto: {X_text.shape[1]}, numéricas: {X_numerical.shape[1]})")
        
        # Split train/test
        X_train, X_test, y_train, y_test = train_test_split(
            X, y,
            test_size=0.2,
            random_state=42,
            stratify=y if len(np.unique(y)) > 1 else None
        )
        
        # Treina RandomForest
        self.classifier = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            min_samples_split=5,
            random_state=42,
            n_jobs=-1
        )
        
        self.classifier.fit(X_train, y_train)
        self.trained = True
        
        # Avalia no conjunto de teste
        y_pred = self.classifier.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        f1 = f1_score(y_test, y_pred, average='binary')
        
        logger.info(f"Treinamento concluído - Acurácia: {accuracy:.2%}, F1: {f1:.2f}")
        
        # Relatório detalhado
        report = classification_report(y_test, y_pred, output_dict=True)
        
        metrics = {
            'accuracy': accuracy,
            'f1_score': f1,
            'train_size': len(X_train),
            'test_size': len(X_test),
            'n_features': X.shape[1],
            'report': report,
            'trained_at': datetime.now().isoformat()
        }
        
        return metrics
    
    def predict_proba(self, licitacao: Dict[str, Any]) -> float:
        """
        Prediz probabilidade de relevância de uma licitação
        
        Returns:
            Float entre 0 e 1 (probabilidade de ser relevante)
        """
        if not self.trained or self.vectorizer is None or self.classifier is None:
            logger.warning("Modelo não treinado, retornando relevância padrão")
            return 0.5
        
        try:
            # Extrai texto
            texto = TextPreprocessor.extract_features_from_licitacao(licitacao)
            
            # Vetoriza
            X_text = self.vectorizer.transform([texto]).toarray()
            
            # Features numéricas
            X_numerical = FeatureExtractor.extract_numerical_features(licitacao).reshape(1, -1)
            
            # Combina
            X = np.hstack([X_text, X_numerical])
            
            # Predição
            proba = self.classifier.predict_proba(X)[0][1]  # Probabilidade classe 1 (relevante)
            
            return float(proba)
        except Exception as e:
            logger.error(f"Erro na predição: {e}", exc_info=True)
            return 0.5
    
    def predict(self, licitacao: Dict[str, Any], threshold: float = 0.5) -> int:
        """
        Prediz se licitação é relevante (1) ou não (0)
        
        Args:
            licitacao: Dicionário com dados da licitação
            threshold: Limiar de decisão (padrão 0.5)
            
        Returns:
            1 se relevante, 0 caso contrário
        """
        proba = self.predict_proba(licitacao)
        return 1 if proba >= threshold else 0
    
    def save_model(self, path: Optional[str] = None):
        """Salva modelo treinado"""
        if not self.trained:
            raise ValueError("Modelo não treinado")
        
        save_path = path or self.model_path
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        
        model_data = {
            'vectorizer': self.vectorizer,
            'classifier': self.classifier,
            'trained_at': datetime.now().isoformat()
        }
        
        joblib.dump(model_data, save_path)
        logger.info(f"Modelo salvo em: {save_path}")
    
    def load_model(self, path: Optional[str] = None) -> bool:
        """
        Carrega modelo salvo
        
        Returns:
            True se carregou com sucesso, False caso contrário
        """
        load_path = path or self.model_path
        
        if not os.path.exists(load_path):
            logger.debug(f"Modelo não encontrado em: {load_path}")
            return False
        
        try:
            model_data = joblib.load(load_path)
            self.vectorizer = model_data['vectorizer']
            self.classifier = model_data['classifier']
            self.trained = True
            
            logger.info(f"Modelo carregado de: {load_path} (treinado em {model_data.get('trained_at', 'N/A')})")
            return True
        except Exception as e:
            logger.error(f"Erro ao carregar modelo: {e}", exc_info=True)
            return False
