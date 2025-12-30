#!/usr/bin/env python3
"""
Script de migração de dados SQLite local para Supabase PostgreSQL.

Execute com: python scripts/migrate_to_supabase.py

Antes de executar:
1. Certifique-se de que DATABASE_URL está configurada no .env
2. O banco Supabase deve estar vazio (ou as tabelas serão criadas/sobrescritas)
"""

import os
import sys

# Adiciona o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import sqlite3

# Configuração
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')

# Carrega variáveis de ambiente do .env
from dotenv import load_dotenv
load_dotenv(os.path.join(BASE_DIR, '.env'))

SUPABASE_URL = os.getenv('DATABASE_URL')

if not SUPABASE_URL:
    print("❌ ERRO: DATABASE_URL não encontrada no .env")
    print("   Adicione: DATABASE_URL=postgresql://postgres:SENHA@db.xxx.supabase.co:5432/postgres")
    sys.exit(1)


def get_sqlite_data(db_path: str, table_name: str) -> list[dict]:
    """Extrai todos os dados de uma tabela SQLite."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        cursor.execute(f"SELECT * FROM {table_name}")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except sqlite3.OperationalError as e:
        print(f"   ⚠️ Tabela {table_name} não encontrada: {e}")
        return []
    finally:
        conn.close()


def get_sqlite_tables(db_path: str) -> list[str]:
    """Lista todas as tabelas de um banco SQLite."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()
    return tables


def migrate_database(sqlite_path: str, pg_engine, db_name: str):
    """Migra um banco SQLite completo para PostgreSQL."""
    print(f"\n📦 Migrando {db_name}...")
    
    if not os.path.exists(sqlite_path):
        print(f"   ⚠️ Banco não encontrado: {sqlite_path}")
        return
    
    tables = get_sqlite_tables(sqlite_path)
    print(f"   Tabelas encontradas: {tables}")
    
    # Importa os modelos para criar as tabelas no PostgreSQL
    if db_name == "medcal":
        from modules.database.database import Base, engine
        Base.metadata.create_all(pg_engine)
    else:
        from modules.finance.database import Base
        from modules.finance.bank_models import ExtratoBB, ResumoMensal, SesapPagamento, FinanceAuditLog
        Base.metadata.create_all(pg_engine)
    
    Session = sessionmaker(bind=pg_engine)
    
    for table in tables:
        print(f"   📋 Migrando tabela: {table}")
        data = get_sqlite_data(sqlite_path, table)
        
        if not data:
            print(f"      → Tabela vazia ou não acessível")
            continue
        
        print(f"      → {len(data)} registros encontrados")
        
        # Insere dados usando SQL raw (funciona com qualquer estrutura)
        with Session() as session:
            try:
                for row in data:
                    # Constrói INSERT dinâmico
                    columns = ', '.join(f'"{k}"' for k in row.keys())
                    placeholders = ', '.join(f':{k}' for k in row.keys())
                    sql = f'INSERT INTO {table} ({columns}) VALUES ({placeholders})'
                    
                    try:
                        session.execute(text(sql), row)
                    except Exception as e:
                        # Ignora duplicatas (registro já existe)
                        if 'duplicate' in str(e).lower() or 'unique' in str(e).lower():
                            continue
                        else:
                            print(f"      ⚠️ Erro ao inserir: {e}")
                
                session.commit()
                print(f"      ✅ Migração concluída")
            except Exception as e:
                session.rollback()
                print(f"      ❌ Erro na migração: {e}")


def main():
    print("=" * 60)
    print("🚀 MIGRAÇÃO SQLite → Supabase PostgreSQL")
    print("=" * 60)
    
    # Cria engine do PostgreSQL
    pg_engine = create_engine(SUPABASE_URL, echo=False, pool_pre_ping=True)
    
    # Testa conexão
    print("\n🔌 Testando conexão com Supabase...")
    try:
        with pg_engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            print(f"   ✅ Conectado! PostgreSQL: {version[:50]}...")
    except Exception as e:
        print(f"   ❌ Falha na conexão: {e}")
        sys.exit(1)
    
    # Migra cada banco
    migrate_database(
        os.path.join(DATA_DIR, 'medcal.db'),
        pg_engine,
        "medcal"
    )
    
    migrate_database(
        os.path.join(DATA_DIR, 'financeiro.db'),
        pg_engine,
        "financeiro"
    )
    
    migrate_database(
        os.path.join(DATA_DIR, 'financeiro_historico.db'),
        pg_engine,
        "financeiro_historico"
    )
    
    print("\n" + "=" * 60)
    print("✅ MIGRAÇÃO CONCLUÍDA!")
    print("=" * 60)
    print("\nPróximos passos:")
    print("1. Verifique os dados no dashboard do Supabase")
    print("2. Teste o sistema com: streamlit run dashboard.py")
    print("3. Se tudo funcionar, pode remover DATABASE_URL do .env para voltar ao SQLite local")


if __name__ == "__main__":
    main()
