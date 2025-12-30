#!/usr/bin/env python3
"""
Script de treinamento do modelo de classificação de licitações
Carrega dados históricos do banco e treina modelo ML
"""
import sys
from pathlib import Path

# Adiciona o diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.database.database import get_session, Licitacao
from modules.ml.classifier import LicitacaoClassifier
from modules.utils.logging_config import get_logger

logger = get_logger(__name__)


def load_training_data():
    """
    Carrega dados de treinamento do banco
    
    Returns:
        Tuple de (licitacoes, labels)
        Labels: 1 = Salva (relevante), 0 = Nova/Não Salva (não relevante)
    """
    session = get_session()
    
    # Busca licitações salvas (relevantes)
    salvas = session.query(Licitacao).filter(Licitacao.status == 'Salva').all()
    
    # Busca licitações não salvas (não relevantes)
    nao_salvas = session.query(Licitacao).filter(Licitacao.status != 'Salva').limit(len(salvas) * 3).all()
    
    session.close()
    
    logger.info(f"Dados carregados: {len(salvas)} salvas, {len(nao_salvas)} não salvas")
    
    # Converte para dicionários
    licitacoes_dict = []
    labels = []
    
    for lic in salvas:
        licitacoes_dict.append({
            'orgao': lic.orgao,
            'uf': lic.uf,
            'modalidade': lic.modalidade,
            'objeto': lic.objeto,
            'itens': [{'descricao': item.descricao} for item in lic.itens] if lic.itens else [],
            'data_encerramento_proposta': lic.data_encerramento_proposta,
        })
        labels.append(1)  # Relevante
    
    for lic in nao_salvas:
        licitacoes_dict.append({
            'orgao': lic.orgao,
            'uf': lic.uf,
            'modalidade': lic.modalidade,
            'objeto': lic.objeto,
            'itens': [{'descricao': item.descricao} for item in lic.itens] if lic.itens else [],
            'data_encerramento_proposta': lic.data_encerramento_proposta,
        })
        labels.append(0)  # Não relevante
    
    return licitacoes_dict, labels


def main():
    """Função principal de treinamento"""
    print("=" * 60)
    print("TREINAMENTO DO MODELO DE CLASSIFICAÇÃO")
    print("=" * 60)
    
    # Carrega dados
    print("\n1. Carregando dados do banco...")
    licitacoes, labels = load_training_data()
    
    if len(licitacoes) < 10:
        print(f"❌ ERRO: Dados insuficientes para treinamento ({len(licitacoes)} licitações)")
        print("   Marque pelo menos 10 licitações como 'Salva' antes de treinar o modelo.")
        sys.exit(1)
    
    print(f"   ✓ {len(licitacoes)} licitações carregadas")
    print(f"   ✓ Distribuição: {sum(labels)} relevantes, {len(labels) - sum(labels)} não relevantes")
    
    # Treina modelo
    print("\n2. Treinando modelo...")
    classifier = LicitacaoClassifier()
    
    try:
        metrics = classifier.train(licitacoes, labels)
        
        print(f"   ✓ Treinamento concluído!")
        print(f"\n3. Métricas de Performance:")
        print(f"   - Acurácia: {metrics['accuracy']:.2%}")
        print(f"   - F1-Score: {metrics['f1_score']:.2f}")
        print(f"   - Tamanho treino: {metrics['train_size']}")
        print(f"   - Tamanho teste: {metrics['test_size']}")
        print(f"   - Features: {metrics['n_features']}")
        
        # Salva modelo
        print("\n4. Salvando modelo...")
        classifier.save_model()
        print("   ✓ Modelo salvo em: data/models/licitacao_classifier.pkl")
        
        print("\n" + "=" * 60)
        print("✅ TREINAMENTO CONCLUÍDO COM SUCESSO")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ ERRO NO TREINAMENTO: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
