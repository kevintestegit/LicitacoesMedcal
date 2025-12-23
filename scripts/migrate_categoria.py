#!/usr/bin/env python3
"""
Script de migração para adicionar coluna 'categoria' na tabela licitacoes
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from modules.database.database import engine, init_db

def migrate():
    """Adiciona coluna categoria se não existir"""
    print("=" * 50)
    print("MIGRAÇÃO: Adicionar coluna 'categoria'")
    print("=" * 50)
    
    # Primeiro, garante que todas as tabelas existem
    init_db()
    
    with engine.connect() as conn:
        # Verifica se coluna já existe
        result = conn.execute(text("PRAGMA table_info(licitacoes)"))
        colunas = [row[1] for row in result.fetchall()]
        
        if 'categoria' in colunas:
            print("✅ Coluna 'categoria' já existe!")
        else:
            print("📝 Adicionando coluna 'categoria'...")
            conn.execute(text("ALTER TABLE licitacoes ADD COLUMN categoria TEXT"))
            conn.commit()
            print("✅ Coluna 'categoria' adicionada com sucesso!")
    
    print("=" * 50)
    print("Migração concluída!")
    print("=" * 50)

if __name__ == "__main__":
    migrate()
