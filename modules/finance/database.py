from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker
import os

# Importa configuração do database usando import relativo
from ..database.database_config import (
    is_using_turso, get_turso_url, get_turso_token
)

Base = declarative_base()

# Conexão global libsql para Turso (usada diretamente)
_libsql_conn = None

def get_turso_connection():
    """Retorna conexão libsql direta ao Turso (para uso direto, não SQLAlchemy)"""
    global _libsql_conn
    if is_using_turso():
        import libsql_experimental as libsql
        # Sempre cria nova conexão para evitar problemas
        return libsql.connect(
            get_turso_url(),
            auth_token=get_turso_token()
        )
    return None


# Configuração do Banco Financeiro
# SQLite local - funciona sempre como fallback
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, 'data', 'financeiro.db')
DB_PATH_HIST = os.path.join(BASE_DIR, 'data', 'financeiro_historico.db')

engine = create_engine(
    f'sqlite:///{DB_PATH}',
    echo=False,
    connect_args={"check_same_thread": False, "timeout": 30},
    pool_pre_ping=True,
)
engine_hist = create_engine(
    f'sqlite:///{DB_PATH_HIST}',
    echo=False,
    connect_args={"check_same_thread": False, "timeout": 30},
    pool_pre_ping=True,
)

Session = sessionmaker(bind=engine)
SessionHist = sessionmaker(bind=engine_hist)


def _set_pragmas(dbapi_connection):
    try:
        cur = dbapi_connection.cursor()
        cur.execute("PRAGMA journal_mode=WAL;")
        cur.execute("PRAGMA synchronous=NORMAL;")
        cur.execute("PRAGMA busy_timeout=5000;")
        cur.close()
    except Exception:
        pass


@event.listens_for(engine, "connect")
def _on_connect(dbapi_connection, connection_record):
    _set_pragmas(dbapi_connection)


if engine_hist != engine:
    @event.listens_for(engine_hist, "connect")
    def _on_connect_hist(dbapi_connection, connection_record):
        _set_pragmas(dbapi_connection)


def init_finance_db():
    """Inicializa o banco de dados financeiro (cria tabelas)"""
    from .bank_models import ExtratoBB, ResumoMensal, SesapPagamento, FinanceAuditLog
    from .funcionarios_models import Funcionario, PagamentoFuncionario
    Base.metadata.create_all(engine)


def init_finance_historico_db():
    """Inicializa o banco de dados financeiro histórico (cria tabelas)"""
    from .bank_models import ExtratoBB, ResumoMensal
    Base.metadata.create_all(engine_hist)


def get_finance_session():
    """Retorna uma nova sessão para o banco financeiro"""
    return Session()


def get_finance_historico_session():
    """Retorna nova sessão para o banco financeiro histórico"""
    return SessionHist()


def sync_finance_to_cloud():
    """Sincroniza dados financeiros com Turso (não necessário com conexão direta)"""
    pass
