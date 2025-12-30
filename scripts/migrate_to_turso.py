#!/usr/bin/env python3
"""
Migração simples e robusta para Turso.
Usa uma conexão por tabela e sync frequente.
"""

import os
import sys
import sqlite3
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / '.env')

import libsql_experimental as libsql

TURSO_URL = os.getenv('TURSO_DATABASE_URL')
TURSO_TOKEN = os.getenv('TURSO_AUTH_TOKEN')

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / 'data'

LOCAL_DBS = [
    DATA_DIR / 'medcal.db',
    DATA_DIR / 'financeiro.db',
    DATA_DIR / 'financeiro_historico.db',
]

def migrate_table(local_conn: sqlite3.Connection, table_name: str):
    """Migra uma tabela usando nova conexão Turso."""
    print(f"   📋 {table_name}...")
    
    # Nova conexão para cada tabela (evita timeout)
    turso = libsql.connect('data/turso_cache.db', sync_url=TURSO_URL, auth_token=TURSO_TOKEN)
    turso.sync()
    
    try:
        # Pega schema
        schema = local_conn.execute(
            f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table_name}'"
        ).fetchone()
        
        if not schema or not schema[0]:
            print(f"      ⚠️ Schema não encontrado")
            return 0
        
        # Cria tabela (IF NOT EXISTS)
        create_sql = schema[0].replace(
            f"CREATE TABLE {table_name}", 
            f"CREATE TABLE IF NOT EXISTS {table_name}"
        ).replace(
            f'CREATE TABLE "{table_name}"', 
            f'CREATE TABLE IF NOT EXISTS "{table_name}"'
        )
        
        try:
            turso.execute(create_sql)
            turso.commit()
        except Exception as e:
            if 'already exists' not in str(e).lower():
                print(f"      ⚠️ Erro criando tabela: {e}")
        
        # Conta registros locais
        total = local_conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        if total == 0:
            print(f"      → Tabela vazia")
            turso.sync()
            return 0
        
        # Pega colunas
        cursor = local_conn.execute(f"SELECT * FROM {table_name} LIMIT 1")
        columns = [desc[0] for desc in cursor.description]
        
        # Insere em batches
        BATCH_SIZE = 1000
        inserted = 0
        offset = 0
        
        while offset < total:
            rows = local_conn.execute(
                f"SELECT * FROM {table_name} LIMIT {BATCH_SIZE} OFFSET {offset}"
            ).fetchall()
            
            if not rows:
                break

            # Prepara dados para executemany
            placeholders = ', '.join(['?' for _ in columns])
            cols_str = ', '.join([f'"{c}"' for c in columns])
            
            data_batch = [tuple(row) for row in rows]
            
            try:
                # Tenta inserir em lote primeiro (mais rápido)
                turso.executemany(
                    f"INSERT OR IGNORE INTO {table_name} ({cols_str}) VALUES ({placeholders})",
                    data_batch
                )
                inserted += len(rows)
            except Exception:
                # Fallback para linha a linha se falhar batch
                for row_data in data_batch:
                    try:
                        turso.execute(
                            f"INSERT OR IGNORE INTO {table_name} ({cols_str}) VALUES ({placeholders})",
                            row_data
                        )
                        inserted += 1
                    except Exception:
                        pass
            
            # Commit e sync a cada batch
            turso.commit()
            turso.sync()
            offset += BATCH_SIZE
            print(f"      → {min(offset, total)}/{total} processados...", end='\r')
        
        print(f"      ✅ {inserted}/{total} inseridos         ")
        return inserted
        
    except Exception as e:
        print(f"      ❌ Erro: {e}")
        return 0


def main():
    print("=" * 50)
    print("🚀 MIGRAÇÃO ROBUSTA PARA TURSO")
    print("=" * 50)
    
    if not TURSO_URL or not TURSO_TOKEN:
        print("❌ Configure TURSO_DATABASE_URL e TURSO_AUTH_TOKEN no .env")
        sys.exit(1)
    
    print(f"📍 URL: {TURSO_URL[:40]}...")
    
    for db_path in LOCAL_DBS:
        if not db_path.exists():
            print(f"\n⚠️ {db_path.name} não encontrado")
            continue
        
        print(f"\n📦 {db_path.name}...")
        
        local = sqlite3.connect(str(db_path))
        local.row_factory = sqlite3.Row
        
        tables = local.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        
        for (table_name,) in tables:
            migrate_table(local, table_name)
        
        local.close()
    
    # Verifica resultado final
    print("\n" + "=" * 50)
    print("📊 VERIFICAÇÃO FINAL")
    print("=" * 50)
    
    turso = libsql.connect('data/turso_final.db', sync_url=TURSO_URL, auth_token=TURSO_TOKEN)
    turso.sync()
    
    tables = turso.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    
    for (table_name,) in tables:
        count = turso.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        print(f"   {table_name}: {count} registros")
    
    print("\n✅ Migração concluída!")


if __name__ == "__main__":
    main()
