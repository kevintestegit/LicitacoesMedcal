#!/usr/bin/env python3
"""
Script de teste para o pipeline ETL
Testa transformações e validações com dados de exemplo
"""
import sys
from pathlib import Path

# Adiciona o diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.etl import process_licitacoes, ETLPipeline, LicitacaoTransformer
from modules.etl.pipeline import (
    remove_duplicates,
    normalize_licitacoes,
    validate_required_fields,
    enrich_metadata
)


def test_transformers():
    """Testa transformadores individuais"""
    print("=" * 60)
    print("TESTE 1: Transformadores Individuais")
    print("=" * 60)
    
    # Teste de normalização de órgão
    orgaos = [
        "PREFEITURA MUNICIPAL DE NATAL",
        "PM DE PARNAMIRIM",
        "Fundo Municipal de Saúde de Mossoró",
        "CAMARA MUNICIPAL DE JOÃO PESSOA"
    ]
    
    print("\n1.1 Normalização de Órgãos:")
    for orgao in orgaos:
        normalizado = LicitacaoTransformer.normalize_orgao(orgao)
        print(f"  {orgao[:40]:40} -> {normalizado}")
    
    # Teste de extração de valor
    valores = ["R$ 1.234,56", "1234.56", "R$ 100.000,00", "50000"]
    print("\n1.2 Extração de Valores:")
    for valor in valores:
        extraido = LicitacaoTransformer.extract_valor(valor)
        print(f"  {valor:20} -> {extraido}")
    
    # Teste de validação de UF
    ufs = ["RN", "rn", "PB", "XX", None, "SP"]
    print("\n1.3 Validação de UF:")
    for uf in ufs:
        validado = LicitacaoTransformer.validate_uf(uf)
        print(f"  {str(uf):10} -> {validado}")


def test_pipeline():
    """Testa pipeline completo"""
    print("\n" + "=" * 60)
    print("TESTE 2: Pipeline Completo")
    print("=" * 60)
    
    # Dados de teste simulando resultados de scraper
    dados_teste = [
        {
            'orgao': 'PREFEITURA MUNICIPAL DE NATAL',
            'uf': 'RN',
            'modalidade': 'PREGAO ELETRONICO',
            'objeto': '  Aquisição de   medicamentos para   saúde  ',
            'data_publicacao': '2024-01-15',
        },
        {
            'orgao': 'PM DE NATAL',  # Duplicata
            'uf': 'rn',
            'modalidade': 'Pregão',
            'objeto': 'Aquisição de medicamentos para saúde',
            'data_publicacao': '2024-01-15T00:00:00',
        },
        {
            'orgao': 'Fundo Municipal de Saúde de Mossoró',
            'uf': 'RN',
            'modalidade': 'DISPENSA',
            'objeto': 'Compra de equipamentos médicos',
            'data_publicacao': '25/01/2024',
        },
        {
            'orgao': '',  # Inválido - sem órgão
            'objeto': 'Teste inválido',
        },
        {
            'orgao': 'CAMARA MUNICIPAL DE João Pessoa',
            'uf': 'PB',
            'modalidade': 'TOMADA DE PRECOS',
            'objeto': 'Reforma do prédio',
            'data_publicacao': '2024-02-01',
        }
    ]
    
    print(f"\nDados originais: {len(dados_teste)} registros")
    for i, item in enumerate(dados_teste, 1):
        print(f"  {i}. {item.get('orgao', 'SEM ÓRGÃO')[:40]}")
    
    # Processa com pipeline padrão
    dados_processados = process_licitacoes(dados_teste)
    
    print(f"\nDados processados: {len(dados_processados)} registros")
    print("\nResultado:")
    for i, item in enumerate(dados_processados, 1):
        print(f"\n  {i}. Órgão: {item.get('orgao')}")
        print(f"     UF: {item.get('uf')}")
        print(f"     Modalidade: {item.get('modalidade')}")
        print(f"     Objeto: {item.get('objeto')[:50]}...")
        if 'etl_processed_at' in item:
            print(f"     ✓ Processado em: {item['etl_processed_at'].strftime('%H:%M:%S')}")


def test_custom_pipeline():
    """Testa pipeline customizado"""
    print("\n" + "=" * 60)
    print("TESTE 3: Pipeline Customizado")
    print("=" * 60)
    
    dados = [
        {'orgao': 'PM DE NATAL', 'objeto': 'Teste 1'},
        {'orgao': 'PM DE NATAL', 'objeto': 'Teste 1'},  # Duplicata
        {'orgao': 'PM DE PARNAMIRIM', 'objeto': 'Teste 2'},
    ]
    
    # Cria pipeline customizado
    pipeline = ETLPipeline()
    pipeline.add_transform(remove_duplicates)
    pipeline.add_transform(normalize_licitacoes)
    
    resultado = pipeline.run(dados)
    stats = pipeline.get_stats()
    
    print(f"\nEstatísticas do pipeline:")
    print(f"  Processados: {stats['processados']}")
    print(f"  Resultado final: {len(resultado)} registros")
    print(f"  Transformações aplicadas: {stats['transformacoes']}")
    print(f"  Erros: {stats['erros']}")


if __name__ == "__main__":
    print("\n🧪 TESTES DO PIPELINE ETL")
    print("=" * 60)
    
    try:
        test_transformers()
        test_pipeline()
        test_custom_pipeline()
        
        print("\n" + "=" * 60)
        print("✅ TODOS OS TESTES CONCLUÍDOS COM SUCESSO")
        print("=" * 60 + "\n")
    except Exception as e:
        print(f"\n❌ ERRO NOS TESTES: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
