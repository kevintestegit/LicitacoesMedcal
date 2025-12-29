#!/usr/bin/env python3
"""
Script para categorizar licitações existentes no banco de dados.
Aplica a classificação automática a todas as licitações sem categoria.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.database.database import get_session, Licitacao, init_db
from modules.utils.category_classifier import classificar_licitacao, categoria_dominante


def categorizar_todas():
    """Categoriza todas as licitações sem categoria."""
    init_db()
    session = get_session()
    
    try:
        # Busca licitações sem categoria ou com categoria nula
        licitacoes = session.query(Licitacao).filter(
            (Licitacao.categoria == None) | (Licitacao.categoria == "")
        ).all()
        
        print(f"📋 Encontradas {len(licitacoes)} licitações sem categoria")
        
        stats = {"total": 0, "classificadas": 0, "por_categoria": {}}
        
        for lic in licitacoes:
            stats["total"] += 1
            
            # Tenta classificar pelo objeto
            categoria = classificar_licitacao(lic.objeto)
            
            # Se não conseguiu, tenta pelos itens
            if not categoria and lic.itens:
                itens_desc = [item.descricao for item in lic.itens if item.descricao]
                categoria = categoria_dominante(itens_desc)
            
            if categoria:
                lic.categoria = categoria
                stats["classificadas"] += 1
                stats["por_categoria"][categoria] = stats["por_categoria"].get(categoria, 0) + 1
                print(f"  ✅ [{categoria}] {lic.orgao[:40]}...")
            else:
                print(f"  ⚠️ [Não classificado] {lic.orgao[:40]}...")
        
        session.commit()
        
        print("\n" + "=" * 50)
        print("📊 RESULTADO:")
        print(f"   Total analisadas: {stats['total']}")
        print(f"   Classificadas: {stats['classificadas']}")
        print(f"   Não classificadas: {stats['total'] - stats['classificadas']}")
        print("\n📁 Por categoria:")
        for cat, count in sorted(stats["por_categoria"].items(), key=lambda x: -x[1]):
            print(f"   {cat}: {count}")
        print("=" * 50)
        
    finally:
        session.close()


if __name__ == "__main__":
    print("🏷️  CATEGORIZADOR DE LICITAÇÕES")
    print("=" * 50)
    categorizar_todas()
