from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
import os

Base = declarative_base()

# Configuração do Banco Financeiro Separado
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, 'data', 'financeiro.db')

engine = create_engine(f'sqlite:///{DB_PATH}', echo=False)
Session = sessionmaker(bind=engine)

def init_finance_db():
    """Inicializa o banco de dados financeiro (cria tabelas)"""
    # Importar modelos para garantir que sejam registrados no Base
    from .bank_models import ExtratoBB, ResumoMensal
    Base.metadata.create_all(engine)

def get_finance_session():
    """Retorna uma nova sessão para o banco financeiro"""
    return Session()
