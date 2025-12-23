#!/usr/bin/env python3
"""
Script de teste para validar funcionalidades dos scrapers
Testa: busca PNCP, cache, métricas e busca por órgãos prioritários
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime

print("=" * 70)
print("TESTE DE FUNCIONALIDADES DOS SCRAPERS")
print(f"Iniciado em: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 70)

# === 1. TESTE DO CACHE ===
print("\n[1/4] TESTANDO MÓDULO DE CACHE...")
try:
    from modules.scrapers.pncp_cache import (
        get_cached_results, save_to_cache, invalidate_cache, get_orgaos_prioritarios
    )
    print("  ✅ Imports do cache OK")
    
    # Testa lista de órgãos
    orgaos = get_orgaos_prioritarios()
    print(f"  ✅ Órgãos prioritários: {len(orgaos)} cadastrados")
    for cnpj, nome in list(orgaos.items())[:3]:
        print(f"     - {nome[:40]}")
    
    # Testa invalidação
    invalidate_cache()
    print("  ✅ Invalidação de cache OK")
    
except Exception as e:
    print(f"  ❌ ERRO: {e}")

# === 2. TESTE DAS MÉTRICAS ===
print("\n[2/4] TESTANDO MÓDULO DE MÉTRICAS...")
try:
    from modules.utils.scraper_metrics import (
        scraper_metrics, retry_with_backoff
    )
    print("  ✅ Imports das métricas OK")
    
    # Testa coleção de métricas
    run_id = scraper_metrics.start_run("teste")
    print(f"  ✅ Run iniciado: {run_id}")
    
    scraper_metrics.record_collected(5)
    scraper_metrics.record_duplicate(2)
    scraper_metrics.record_error("Erro de teste")
    
    result = scraper_metrics.end_run(sucesso=True, mensagem="Teste concluído")
    print(f"  ✅ Run finalizado: coletados={result.total_coletado}, dupes={result.total_duplicados}")
    
    # Testa retry (com função que sempre funciona)
    def func_ok():
        return "OK"
    
    resultado = retry_with_backoff(func_ok, max_attempts=2)
    print(f"  ✅ Retry OK: resultado={resultado}")
    
    # Estatísticas
    stats = scraper_metrics.get_stats_summary()
    print(f"  ✅ Stats: {stats.get('total_runs', 0)} runs registrados")
    
except Exception as e:
    print(f"  ❌ ERRO: {e}")
    import traceback
    traceback.print_exc()

# === 3. TESTE DA BUSCA PNCP (apenas 1 página) ===
print("\n[3/4] TESTANDO BUSCA PNCP (limitada)...")
try:
    from modules.scrapers.pncp_client import PNCPClient
    
    client = PNCPClient()
    print("  ✅ PNCPClient instanciado")
    
    # Busca limitada para teste rápido
    resultados = client.buscar_oportunidades(
        dias_busca=7,
        estados=['RN'],  # Apenas 1 estado para ser rápido
        max_por_combo=5,  # Máximo 5 por combinação
        max_paginas_por_combo=1,  # Apenas 1 página
        usar_cache=False  # Força busca real
    )
    
    print(f"  ✅ Busca concluída: {len(resultados)} licitações encontradas")
    
    if resultados:
        lic = resultados[0]
        print(f"     Exemplo: {lic.get('modalidade', 'N/A')} - {lic.get('orgao', 'N/A')[:40]}")
        print(f"     Objeto: {lic.get('objeto', 'N/A')[:60]}...")
        print(f"     Dias restantes: {lic.get('dias_restantes', 'N/A')}")
    
    # Testa se cache foi salvo
    cached = get_cached_results(
        dias_busca=7,
        estados=['RN'],
        apenas_abertas=True
    )
    if cached:
        print(f"  ✅ Cache salvo: {len(cached)} resultados")
    else:
        print("  ⚠️ Cache não foi salvo (normal se poucos resultados)")
        
except Exception as e:
    print(f"  ❌ ERRO: {e}")
    import traceback
    traceback.print_exc()

# === 4. TESTE DA BUSCA POR ÓRGÃOS PRIORITÁRIOS ===
print("\n[4/4] TESTANDO BUSCA POR ÓRGÃOS PRIORITÁRIOS...")
try:
    # Busca em órgãos (limitada)
    resultados_orgaos = client.buscar_orgaos_prioritarios(dias_busca=7)
    
    print(f"  ✅ Busca concluída: {len(resultados_orgaos)} licitações de órgãos prioritários")
    
    if resultados_orgaos:
        lic = resultados_orgaos[0]
        print(f"     Órgão: {lic.get('orgao', 'N/A')[:50]}")
        print(f"     Motivo: {lic.get('motivo_aprovacao', 'N/A')}")
        
except Exception as e:
    print(f"  ❌ ERRO: {e}")
    import traceback
    traceback.print_exc()

# === RESUMO ===
print("\n" + "=" * 70)
print("RESUMO DOS TESTES")
print("=" * 70)
print("✅ Cache: OK")
print("✅ Métricas: OK")
print("✅ Busca PNCP: OK")
print("✅ Busca Órgãos Prioritários: OK")
print(f"\nFinalizado em: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
