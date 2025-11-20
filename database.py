from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime

Base = declarative_base()

class Produto(Base):
    __tablename__ = 'produtos'
    
    id = Column(Integer, primary_key=True)
    nome = Column(String, nullable=False)
    palavras_chave = Column(String, nullable=False) # Separadas por vírgula
    preco_custo = Column(Float, nullable=False)
    margem_minima = Column(Float, default=20.0) # Em porcentagem
    
    # Novos campos para Comparativo de Mercado
    preco_referencia = Column(Float, default=0.0) # Preço de mercado/concorrente
    fonte_referencia = Column(String, default="") # Ex: "Empresa X", 
    
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
    data_inicio_proposta = Column(DateTime) # Novo campo para filtro
    data_encerramento_proposta = Column(DateTime) # Novo campo para prazo
    objeto = Column(String)
    link = Column(String)
    
    # Novos campos para Gestão (Kanban)
    status = Column(String, default='Nova') # Nova, Em Análise, Participar, Ganha, Perdida, Ignorada
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
    valor_unitario = Column(Float, nullable=True) # Novo campo
    
    # Match
    produto_match_id = Column(Integer, ForeignKey('produtos.id'), nullable=True)
    match_score = Column(Float, default=0.0)
    
    licitacao = relationship("Licitacao", back_populates="itens")
    produto_match = relationship("Produto")

class Configuracao(Base):
    __tablename__ = 'configuracoes'
    
    id = Column(Integer, primary_key=True)
    chave = Column(String, unique=True, nullable=False) # Ex: 'termos_busca_padrao'
    valor = Column(String) # Ex: "TERMO1, TERMO2, TERMO3"

# Configuração do Banco
engine = create_engine('sqlite:///medcal.db', echo=False)
Session = sessionmaker(bind=engine)

def init_db():
    Base.metadata.create_all(engine)

def get_session():
    return Session()
