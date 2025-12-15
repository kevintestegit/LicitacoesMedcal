from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Text, Date
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime
import os

Base = declarative_base()

class Produto(Base):
    __tablename__ = 'produtos'
    
    id = Column(Integer, primary_key=True)
    nome = Column(String, nullable=False)
    palavras_chave = Column(String, nullable=False)  # Separadas por virgula
    preco_custo = Column(Float, nullable=False)
    margem_minima = Column(Float, default=20.0)  # Em porcentagem
    preco_referencia = Column(Float, default=0.0)  # Preco de mercado/concorrente
    fonte_referencia = Column(String, default="")  # Ex: "Empresa X"
    
    def __repr__(self):
        return f"<Produto(nome='{self.nome}', custo={self.preco_custo})>"

class Licitacao(Base):
    __tablename__ = 'licitacoes'
    
    id = Column(Integer, primary_key=True)
    pncp_id = Column(String, unique=True)
    orgao = Column(String)
    uf = Column(String)
    modalidade = Column(String)
    data_sessao = Column(DateTime)
    data_publicacao = Column(DateTime)
    data_inicio_proposta = Column(DateTime)  # Novo campo para filtro
    data_encerramento_proposta = Column(DateTime)  # Novo campo para prazo
    objeto = Column(String)
    link = Column(String)
    
    status = Column(String, default='Nova')  # Nova, Em Analise, Participar, Ganha, Perdida, Ignorada
    comentarios = Column(String)
    data_captura = Column(DateTime, default=datetime.now)

    itens = relationship("ItemLicitacao", back_populates="licitacao", cascade="all, delete-orphan")

class ItemLicitacao(Base):
    __tablename__ = 'itens_licitacao'
    
    id = Column(Integer, primary_key=True)
    licitacao_id = Column(Integer, ForeignKey('licitacoes.id'))
    numero_item = Column(Integer)
    descricao = Column(String)
    quantidade = Column(Float)
    unidade = Column(String)
    valor_estimado = Column(Float, nullable=True)
    valor_unitario = Column(Float, nullable=True)  # Novo campo
    
    produto_match_id = Column(Integer, ForeignKey('produtos.id'), nullable=True)
    match_score = Column(Float, default=0.0)
    
    licitacao = relationship("Licitacao", back_populates="itens")
    # Eager load do produto para evitar DetachedInstanceError em views/Streamlit
    produto_match = relationship("Produto", lazy="joined")

class Configuracao(Base):
    __tablename__ = 'configuracoes'

    id = Column(Integer, primary_key=True)
    chave = Column(String, unique=True, nullable=False)  # Ex: 'termos_busca_padrao'
    valor = Column(String)  # Ex: "TERMO1, TERMO2, TERMO3"

class AgentRun(Base):
    __tablename__ = 'agent_runs'

    id = Column(Integer, primary_key=True)
    started_at = Column(DateTime, default=datetime.now)
    finished_at = Column(DateTime, nullable=True)
    status = Column(String, default='running')
    total_coletado = Column(Integer, default=0)
    total_novos = Column(Integer, default=0)
    total_analisados = Column(Integer, default=0)
    total_participar = Column(Integer, default=0)
    total_revisar = Column(Integer, default=0)
    total_ignorar = Column(Integer, default=0)
    resumo = Column(Text, nullable=True)

    alerts = relationship("AlertSent", back_populates="run")

class AlertSent(Base):
    __tablename__ = 'alerts_sent'

    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey('agent_runs.id'), nullable=True)
    licitacao_id = Column(Integer, ForeignKey('licitacoes.id'), nullable=True)
    destino = Column(String)
    mensagem = Column(Text)
    enviado_em = Column(DateTime, default=datetime.now)
    sucesso = Column(Boolean, default=True)

    run = relationship("AgentRun", back_populates="alerts")
    licitacao = relationship("Licitacao")


class LicitacaoFeature(Base):
    """
    Armazena sinais úteis para treino futuro de modelo de classificação:
    - motivo de aprovação (termos que passaram)
    - termos encontrados no objeto
    - fonte/canal de coleta
    """
    __tablename__ = 'licitacao_features'

    id = Column(Integer, primary_key=True)
    licitacao_id = Column(Integer, ForeignKey('licitacoes.id'), nullable=False)
    fonte = Column(String, default="desconhecida")
    motivo_aprovacao = Column(Text, nullable=True)
    termos_encontrados = Column(Text, nullable=True)  # JSON string
    objeto_resumido = Column(Text, nullable=True)
    criado_em = Column(DateTime, default=datetime.now)

    licitacao = relationship("Licitacao")

# Configuracao do Banco
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, 'data', 'medcal.db')
engine = create_engine(f'sqlite:///{DB_PATH}', echo=False)
Session = sessionmaker(bind=engine)

def init_db():
    Base.metadata.create_all(engine)

def get_session():
    return Session()
