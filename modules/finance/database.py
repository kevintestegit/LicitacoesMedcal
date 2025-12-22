from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker
import os

Base = declarative_base()

# Configuração do Banco Financeiro Separado
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, 'data', 'financeiro.db')
DB_PATH_HIST = os.path.join(BASE_DIR, 'data', 'financeiro_historico.db')

engine = create_engine(
    f'sqlite:///{DB_PATH}',
    echo=False,
    connect_args={"check_same_thread": False, "timeout": 30},
    pool_pre_ping=True,
)
Session = sessionmaker(bind=engine)

# Banco histórico: usa o mesmo modelo, mas em arquivo próprio
engine_hist = create_engine(
    f'sqlite:///{DB_PATH_HIST}',
    echo=False,
    connect_args={"check_same_thread": False, "timeout": 30},
    pool_pre_ping=True,
)
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


@event.listens_for(engine_hist, "connect")
def _on_connect_hist(dbapi_connection, connection_record):
    _set_pragmas(dbapi_connection)

def init_finance_db():
    """Inicializa o banco de dados financeiro (cria tabelas)"""
    # Importar modelos para garantir que sejam registrados no Base
    from .bank_models import ExtratoBB, ResumoMensal
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
