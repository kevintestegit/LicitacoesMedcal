#!/usr/bin/env python3
import os
import sys
import sqlite3
import time
from pathlib import Path
from dotenv import load_dotenv
import libsql_experimental as libsql

# Setup paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / 'data'
load_dotenv(BASE_DIR / '.env')

TURSO_URL = os.getenv('TURSO_DATABASE_URL')
TURSO_TOKEN = os.getenv('TURSO_AUTH_TOKEN')

# Dbs to migrate
DBS = {
    'medcal': DATA_DIR / 'medcal.db',
    'financeiro': DATA_DIR / 'financeiro.db',
    'historico': DATA_DIR / 'financeiro_historico.db'
}

def get_turso_conn():
    # Retenta conexão se falhar
    for attempt in range(5):
        try:
            conn = libsql.connect('data/migration_cache.db', sync_url=TURSO_URL, auth_token=TURSO_TOKEN)
            conn.sync()
            return conn
        except Exception as e:
            print(f"  ⚠️ Erro ao conectar ao Turso (tentativa {attempt+1}): {e}")
            time.sleep(2)
    raise Exception("Não foi possível conectar ao Turso após 5 tentativas.")

def migrate_db_tables(db_name, db_path):
    print(f"\n📦 Processando {db_name} ({db_path.name})...", flush=True)
    if not db_path.exists():
        print(f"  ⚠️ Arquivo não encontrado.", flush=True)
        return

    local_conn = sqlite3.connect(db_path)
    local_conn.row_factory = sqlite3.Row
    
    tables = local_conn.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()
    
    for table in tables:
        table_name = table['name']
        create_sql = table['sql']
        
        print(f"  📋 Tabela {table_name}:", flush=True)
        
        # Conexão Turso fresca
        turso = get_turso_conn()
        
        try:
            clean_create = create_sql.replace(f"CREATE TABLE {table_name}", f"CREATE TABLE IF NOT EXISTS {table_name}")
            clean_create = clean_create.replace(f'CREATE TABLE "{table_name}"', f'CREATE TABLE IF NOT EXISTS "{table_name}"')
            turso.execute(clean_create)
            turso.commit()
            turso.sync() # Sync schema immediately
        except:
            pass

        count = local_conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        if count == 0:
            print("    → Vazia", flush=True)
            turso.close()
            continue

        rows = local_conn.execute(f"SELECT * FROM {table_name}").fetchall()
        cols = [d[0] for d in local_conn.execute(f"SELECT * FROM {table_name} LIMIT 1").description]
        
        placeholders = ", ".join(["?" for _ in cols])
        cols_str = ", ".join([f'"{c}"' for c in cols])
        insert_sql = f"INSERT OR IGNORE INTO {table_name} ({cols_str}) VALUES ({placeholders})"
        
        BATCH_SIZE = 1000 # Aumentado para velocidade
        inserted = 0
        
        for i in range(0, len(rows), BATCH_SIZE):
            batch = [tuple(r) for r in rows[i:i+BATCH_SIZE]]
            
            success = False
            for attempt in range(3):
                try:
                    turso.executemany(insert_sql, batch)
                    turso.commit()
                    # Sincroniza apenas a cada 2000 registros para reduzir overhead de rede
                    if (inserted + len(batch)) % 2000 == 0:
                        turso.sync()
                    success = True
                    break
                except Exception as e:
                    print(f"\n    ⚠️ Falha no lote (tentativa {attempt+1}): {e}", flush=True)
                    # Se stream error, abre nova conexão
                    if "stream not found" in str(e).lower() or "not found" in str(e).lower() or "expired" in str(e).lower():
                        try:
                            turso.close()
                        except:
                            pass
                        turso = get_turso_conn()
                    time.sleep(1)
            
            if not success:
                print(f"\n    ❌ Tentando linha a linha após falhas no lote...", flush=True)
                for r in batch:
                    try:
                        turso.execute(insert_sql, tuple(r))
                    except:
                        pass
                try:
                    turso.commit()
                except:
                    pass

            inserted += len(batch)
            print(f"    → {min(inserted, count)}/{count} processados...", end='\r', flush=True)
        
        print(f"    ✅ {inserted} registros migrados/verificados.", flush=True)
        try:
            turso.sync()
            turso.close()
        except:
            pass
    
    local_conn.close()

def final_report():
    print("\n" + "="*50, flush=True)
    print("📊 RELATÓRIO FINAL (TURSO)", flush=True)
    print("="*50, flush=True)
    try:
        turso = get_turso_conn()
        tables = ['extratos_bb', 'licitacoes', 'produtos', 'resumos_mensais']
        for t in tables:
            try:
                count = turso.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                print(f"  {t.ljust(20)}: {count}", flush=True)
                if t == 'extratos_bb':
                    anos = turso.execute("SELECT DISTINCT ano_referencia FROM extratos_bb ORDER BY ano_referencia").fetchall()
                    print(f"    Anos: {[a[0] for a in anos]}", flush=True)
            except:
                print(f"  {t.ljust(20)}: Não encontrada", flush=True)
        turso.close()
    except Exception as e:
        print(f"Erro no relatório: {e}")

if __name__ == "__main__":
    print("🚀 Iniciando migração UNIFICADA com RETRY...", flush=True)
    try:
        migrate_db_tables('Medcal', DBS['medcal'])
        migrate_db_tables('Financeiro', DBS['financeiro'])
        migrate_db_tables('Histórico', DBS['historico'])
        final_report()
        print("\n✨ Missão cumprida!", flush=True)
    except KeyboardInterrupt:
        print("\n\n🛑 Migração interrompida pelo usuário.")
    except Exception as e:
        print(f"\n\n💥 Erro fatal: {e}")
