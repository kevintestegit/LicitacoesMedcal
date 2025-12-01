"""
Script de migração para adicionar colunas total_aportes e total_entradas_sem_aportes
à tabela resumos_mensais
"""

import sqlite3
import os
from pathlib import Path

# Caminho do banco de dados
BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / 'data' / 'financeiro.db'

def migrate():
    """Adiciona novas colunas ao banco de dados"""
    if not DB_PATH.exists():
        print(f"❌ Banco de dados não encontrado: {DB_PATH}")
        return False

    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()

        # Verifica se as colunas já existem
        cursor.execute("PRAGMA table_info(resumos_mensais)")
        columns = [col[1] for col in cursor.fetchall()]

        migrations_done = []

        # Adiciona total_aportes se não existir
        if 'total_aportes' not in columns:
            cursor.execute("ALTER TABLE resumos_mensais ADD COLUMN total_aportes FLOAT DEFAULT 0.0")
            migrations_done.append("total_aportes")
            print("✅ Coluna 'total_aportes' adicionada")
        else:
            print("ℹ️  Coluna 'total_aportes' já existe")

        # Adiciona total_entradas_sem_aportes se não existir
        if 'total_entradas_sem_aportes' not in columns:
            cursor.execute("ALTER TABLE resumos_mensais ADD COLUMN total_entradas_sem_aportes FLOAT DEFAULT 0.0")
            migrations_done.append("total_entradas_sem_aportes")
            print("✅ Coluna 'total_entradas_sem_aportes' adicionada")
        else:
            print("ℹ️  Coluna 'total_entradas_sem_aportes' já existe")

        conn.commit()
        conn.close()

        if migrations_done:
            print(f"\n✅ Migração concluída! {len(migrations_done)} coluna(s) adicionada(s).")
        else:
            print("\nℹ️  Nenhuma migração necessária - banco já está atualizado.")

        return True

    except Exception as e:
        print(f"❌ Erro na migração: {e}")
        return False

if __name__ == "__main__":
    print("🔄 Iniciando migração do banco de dados financeiro...\n")
    migrate()
