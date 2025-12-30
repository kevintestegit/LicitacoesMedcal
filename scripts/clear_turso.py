import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import libsql_experimental as libsql

# Carrega .env
BASE_DIR = Path(__file__).parent.parent
load_dotenv(BASE_DIR / '.env')

TURSO_URL = os.getenv('TURSO_DATABASE_URL')
TURSO_TOKEN = os.getenv('TURSO_AUTH_TOKEN')

def clear_turso():
    if not TURSO_URL or not TURSO_TOKEN:
        print("❌ Turso não configurado")
        return

    print(f"🧹 Limpando banco Turso: {TURSO_URL[:30]}...")
    
    # Conecta e sincroniza
    conn = libsql.connect('data/clean_temp.db', sync_url=TURSO_URL, auth_token=TURSO_TOKEN)
    conn.sync()
    
    # Lista tabelas
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()
    
    if not tables:
        print("✨ O banco já está vazio.")
        return

    print(f"Encontradas {len(tables)} tabelas. Removendo...")
    
    for (table_name,) in tables:
        print(f"  🗑️ Removendo {table_name}...")
        try:
            conn.execute(f"DROP TABLE \"{table_name}\"")
        except Exception as e:
            print(f"    Erro ao remover {table_name}: {e}")
            
    conn.commit()
    conn.sync()
    print("✅ Banco Turso limpo com sucesso!")

if __name__ == "__main__":
    clear_turso()
