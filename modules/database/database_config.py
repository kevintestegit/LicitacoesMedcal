# Configuração de Banco de Dados - LicitacoesMedcal
# Suporte para SQLite local (desenvolvimento) e Turso (produção online)

import os
from pathlib import Path

# Carrega variáveis de ambiente
from dotenv import load_dotenv
load_dotenv()

# Diretório base do projeto
BASE_DIR = Path(__file__).parent.parent.parent
DATA_DIR = BASE_DIR / 'data'

# =============================================================================
# CONFIGURAÇÃO DO BANCO DE DADOS
# =============================================================================
# Para usar Turso (banco online), defina no .env:
#   TURSO_DATABASE_URL=libsql://xxx.turso.io
#   TURSO_AUTH_TOKEN=xxx
# 
# Se não estiverem definidas, usa SQLite local
# =============================================================================

TURSO_URL = os.getenv("TURSO_DATABASE_URL", "")
TURSO_TOKEN = os.getenv("TURSO_AUTH_TOKEN", "")


def is_using_turso() -> bool:
    """Verifica se está usando Turso (banco online)."""
    return bool(TURSO_URL and TURSO_TOKEN)


def get_turso_url() -> str:
    """Retorna a URL do Turso."""
    return TURSO_URL


def get_turso_token() -> str:
    """Retorna o token do Turso."""
    return TURSO_TOKEN


def get_turso_connection():
    """
    Retorna conexão com Turso usando libsql.
    Com embedded replica (cache local + sync com nuvem).
    """
    if not is_using_turso():
        raise ValueError("Turso não configurado. Defina TURSO_DATABASE_URL e TURSO_AUTH_TOKEN")
    
    import libsql_experimental as libsql
    
    # Usa cache local para performance, sincroniza com nuvem
    cache_path = str(DATA_DIR / 'turso_sync.db')
    
    conn = libsql.connect(
        cache_path,
        sync_url=TURSO_URL,
        auth_token=TURSO_TOKEN
    )
    # Sincroniza com a nuvem
    conn.sync()
    
    return conn


def get_sqlite_path(db_name: str = "medcal") -> str:
    """Retorna o caminho do banco SQLite local (fallback)."""
    db_paths = {
        "medcal": str(DATA_DIR / 'medcal.db'),
        "financeiro": str(DATA_DIR / 'financeiro.db'),
        "financeiro_historico": str(DATA_DIR / 'financeiro_historico.db'),
    }
    return db_paths.get(db_name, db_paths["medcal"])


def get_database_url(db_name: str = "medcal") -> str:
    """
    Retorna URL para SQLAlchemy.
    Quando Turso está ativo, usa o cache local sincronizado.
    """
    if is_using_turso():
        # Usa o cache local que é sincronizado com Turso
        cache_path = DATA_DIR / 'turso_sync.db'
        return f'sqlite:///{cache_path}'
    else:
        # Usa SQLite local puro
        db_path = get_sqlite_path(db_name)
        return f'sqlite:///{db_path}'


# Para compatibilidade com código existente
def is_using_postgres() -> bool:
    """Mantido para compatibilidade - sempre False."""
    return False


def get_connection_args() -> dict:
    """Retorna argumentos de conexão para SQLite."""
    return {
        "check_same_thread": False,
        "timeout": 30
    }


def sync_with_turso():
    """
    Sincroniza o cache local com o Turso remoto.
    Chame esta função após escritas importantes.
    """
    if not is_using_turso():
        return False
    
    try:
        conn = get_turso_connection()
        conn.sync()
        return True
    except Exception as e:
        print(f"Erro ao sincronizar com Turso: {e}")
        return False
