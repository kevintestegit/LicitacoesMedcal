"""
Módulo de sincronização com Turso (banco online SQLite distribuído).

O Turso usa libsql que é compatível com SQLite, mas precisa de sincronização
manual entre o banco local e o remoto.

Uso:
    from modules.database.turso_sync import sync_to_turso, sync_from_turso

    # Push local → Turso
    sync_to_turso()
    
    # Pull Turso → local  
    sync_from_turso()
"""

import os
import sqlite3
from pathlib import Path

# Carrega variáveis de ambiente
from dotenv import load_dotenv
load_dotenv()

BASE_DIR = Path(__file__).parent.parent.parent
DATA_DIR = BASE_DIR / 'data'

TURSO_URL = os.getenv('TURSO_DATABASE_URL', '')
TURSO_TOKEN = os.getenv('TURSO_AUTH_TOKEN', '')

# Bancos locais para sincronizar
LOCAL_DBS = {
    'medcal': DATA_DIR / 'medcal.db',
    'financeiro': DATA_DIR / 'financeiro.db',
    'financeiro_historico': DATA_DIR / 'financeiro_historico.db',
}


def is_turso_configured() -> bool:
    """Verifica se Turso está configurado."""
    return bool(TURSO_URL and TURSO_TOKEN)


def get_turso_connection(db_name: str = 'medcal'):
    """
    Retorna conexão com Turso usando libsql.
    O banco local é usado como cache/embedded replica.
    """
    if not is_turso_configured():
        raise ValueError("Turso não configurado. Defina TURSO_DATABASE_URL e TURSO_AUTH_TOKEN no .env")
    
    import libsql_experimental as libsql
    
    local_path = str(LOCAL_DBS.get(db_name, LOCAL_DBS['medcal']))
    
    conn = libsql.connect(
        local_path,
        sync_url=TURSO_URL,
        auth_token=TURSO_TOKEN
    )
    
    return conn


def sync_from_turso(db_name: str = 'medcal') -> bool:
    """
    Sincroniza dados DO Turso → local.
    Faz download das mudanças do banco remoto.
    """
    try:
        conn = get_turso_connection(db_name)
        conn.sync()
        print(f"✅ Sync Turso → local ({db_name}) concluído!")
        return True
    except Exception as e:
        print(f"❌ Erro ao sincronizar do Turso: {e}")
        return False


def sync_to_turso(db_name: str = 'medcal') -> bool:
    """
    Sincroniza dados local → Turso.
    Faz upload das mudanças locais pro banco remoto.
    
    Nota: libsql embedded replica sincroniza automaticamente ao fazer operações.
    Esta função força um sync explícito.
    """
    try:
        conn = get_turso_connection(db_name)
        conn.sync()
        print(f"✅ Sync local → Turso ({db_name}) concluído!")
        return True
    except Exception as e:
        print(f"❌ Erro ao sincronizar para Turso: {e}")
        return False


def migrate_local_to_turso() -> dict:
    """
    Migra todos os dados dos bancos locais para o Turso.
    Copia tabelas e registros do SQLite local para o Turso remoto.
    
    Returns:
        dict: Relatório de migração com contagem de tabelas/registros
    """
    if not is_turso_configured():
        return {"error": "Turso não configurado"}
    
    import libsql_experimental as libsql
    
    report = {}
    
    # Conecta ao Turso remoto
    turso_conn = libsql.connect(
        'temp_turso_migration',
        sync_url=TURSO_URL,
        auth_token=TURSO_TOKEN
    )
    
    for db_name, local_path in LOCAL_DBS.items():
        if not local_path.exists():
            report[db_name] = {"status": "skip", "reason": "arquivo não existe"}
            continue
        
        print(f"\n📦 Migrando {db_name}...")
        
        # Conecta ao SQLite local
        local_conn = sqlite3.connect(str(local_path))
        local_conn.row_factory = sqlite3.Row
        
        # Lista tabelas
        tables = local_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        
        db_report = {"tables": {}}
        
        for (table_name,) in tables:
            print(f"   📋 Tabela: {table_name}")
            
            # Pega schema da tabela
            schema = local_conn.execute(
                f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table_name}'"
            ).fetchone()[0]
            
            # Cria tabela no Turso (IF NOT EXISTS)
            create_sql = schema.replace(f"CREATE TABLE {table_name}", f"CREATE TABLE IF NOT EXISTS {table_name}")
            try:
                turso_conn.execute(create_sql)
            except Exception as e:
                print(f"      ⚠️ Tabela já existe ou erro: {e}")
            
            # Copia dados
            rows = local_conn.execute(f"SELECT * FROM {table_name}").fetchall()
            
            if rows:
                columns = [desc[0] for desc in local_conn.execute(f"SELECT * FROM {table_name} LIMIT 1").description]
                placeholders = ', '.join(['?' for _ in columns])
                columns_str = ', '.join([f'"{c}"' for c in columns])
                
                inserted = 0
                for row in rows:
                    try:
                        turso_conn.execute(
                            f"INSERT OR IGNORE INTO {table_name} ({columns_str}) VALUES ({placeholders})",
                            tuple(row)
                        )
                        inserted += 1
                    except Exception as e:
                        pass  # Ignora duplicatas
                
                print(f"      → {inserted}/{len(rows)} registros inseridos")
                db_report["tables"][table_name] = {"total": len(rows), "inserted": inserted}
            else:
                db_report["tables"][table_name] = {"total": 0, "inserted": 0}
        
        local_conn.close()
        report[db_name] = db_report
    
    # Sincroniza com o servidor remoto
    turso_conn.sync()
    print("\n✅ Migração concluída e sincronizada com Turso!")
    
    return report


if __name__ == "__main__":
    print("=" * 60)
    print("🚀 MIGRAÇÃO LOCAL → TURSO")
    print("=" * 60)
    
    if not is_turso_configured():
        print("❌ Configure TURSO_DATABASE_URL e TURSO_AUTH_TOKEN no .env")
    else:
        print(f"📍 URL: {TURSO_URL}")
        report = migrate_local_to_turso()
        print("\n📊 Relatório:")
        for db, info in report.items():
            print(f"  - {db}: {info}")
