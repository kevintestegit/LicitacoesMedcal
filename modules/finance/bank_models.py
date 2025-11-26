"""
Modelos de banco de dados para gestão de extratos bancários e faturas
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Text, Date
from sqlalchemy.orm import relationship
from datetime import datetime

# Importa Base do módulo principal para usar a mesma MetaData
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from modules.database.database import Base

class ContaBancaria(Base):
    """Cadastro de contas bancárias da empresa"""
    __tablename__ = 'contas_bancarias'

    id = Column(Integer, primary_key=True)
    banco = Column(String, nullable=False)  # Ex: "Banco do Brasil"
    agencia = Column(String, nullable=False)
    conta = Column(String, nullable=False)
    tipo_conta = Column(String, default='Corrente')  # Corrente, Poupança
    nome_conta = Column(String)  # Nome amigável, ex: "Conta Principal"
    ativo = Column(Boolean, default=True)
    saldo_atual = Column(Float, default=0.0)
    data_criacao = Column(DateTime, default=datetime.now)

    extratos = relationship("ExtratoBancario", back_populates="conta")

    def __repr__(self):
        return f"<ContaBancaria({self.banco} - Ag: {self.agencia} C/C: {self.conta})>"

class ExtratoBancario(Base):
    """Lançamentos de extratos bancários"""
    __tablename__ = 'extratos_bancarios'

    id = Column(Integer, primary_key=True)
    conta_id = Column(Integer, ForeignKey('contas_bancarias.id'), nullable=False)

    # Dados do lançamento
    data_lancamento = Column(Date, nullable=False)
    data_processamento = Column(Date)  # Data de processamento pelo banco
    descricao = Column(String, nullable=False)
    documento = Column(String)  # Número do documento/cheque
    valor = Column(Float, nullable=False)  # Positivo para crédito, negativo para débito
    tipo = Column(String)  # DÉBITO, CRÉDITO, TRANSFERÊNCIA, TAXA, etc.
    categoria = Column(String)  # Categoria automática ou manual

    # Controle
    conciliado = Column(Boolean, default=False)
    observacoes = Column(Text)
    data_upload = Column(DateTime, default=datetime.now)
    arquivo_origem = Column(String)  # Nome do arquivo importado
    hash_lancamento = Column(String, unique=True)  # Para evitar duplicatas

    conta = relationship("ContaBancaria", back_populates="extratos")
    conciliacoes = relationship("Conciliacao", back_populates="extrato")

    def __repr__(self):
        tipo_emoji = "➕" if self.valor > 0 else "➖"
        return f"<Extrato({tipo_emoji} R$ {abs(self.valor):.2f} - {self.descricao[:30]})>"

class Fatura(Base):
    """Faturas a pagar/receber"""
    __tablename__ = 'faturas'

    id = Column(Integer, primary_key=True)

    # Dados da fatura
    tipo = Column(String, nullable=False)  # PAGAR, RECEBER
    fornecedor_cliente = Column(String, nullable=False)  # Nome do fornecedor ou cliente
    descricao = Column(String, nullable=False)
    numero_nota = Column(String)
    valor_original = Column(Float, nullable=False)
    valor_pago = Column(Float, default=0.0)

    # Datas
    data_emissao = Column(Date)
    data_vencimento = Column(Date, nullable=False)
    data_pagamento = Column(Date)

    # Status
    status = Column(String, default='PENDENTE')  # PENDENTE, PAGA, VENCIDA, PARCIAL
    forma_pagamento = Column(String)  # PIX, TED, BOLETO, CARTÃO, etc.
    conta_pagamento_id = Column(Integer, ForeignKey('contas_bancarias.id'))

    # Controle
    observacoes = Column(Text)
    data_criacao = Column(DateTime, default=datetime.now)

    # Relacionamentos
    conciliacoes = relationship("Conciliacao", back_populates="fatura")

    @property
    def valor_restante(self):
        return self.valor_original - self.valor_pago

    @property
    def esta_vencida(self):
        if self.status == 'PAGA':
            return False
        return self.data_vencimento < datetime.now().date()

    def __repr__(self):
        return f"<Fatura({self.fornecedor_cliente} - R$ {self.valor_original:.2f} - {self.status})>"

class Conciliacao(Base):
    """Relacionamento entre extratos e faturas (conciliação)"""
    __tablename__ = 'conciliacoes'

    id = Column(Integer, primary_key=True)
    extrato_id = Column(Integer, ForeignKey('extratos_bancarios.id'), nullable=False)
    fatura_id = Column(Integer, ForeignKey('faturas.id'), nullable=False)

    # Dados da conciliação
    valor_conciliado = Column(Float, nullable=False)  # Permite conciliações parciais
    tipo_match = Column(String)  # AUTO (automático), MANUAL
    score_match = Column(Float, default=0.0)  # Score do matching automático (0-100)

    # Auditoria
    data_conciliacao = Column(DateTime, default=datetime.now)
    usuario = Column(String)  # Quem fez a conciliação manual
    observacoes = Column(Text)

    # Relacionamentos
    extrato = relationship("ExtratoBancario", back_populates="conciliacoes")
    fatura = relationship("Fatura", back_populates="conciliacoes")

    def __repr__(self):
        return f"<Conciliacao(R$ {self.valor_conciliado:.2f} - {self.tipo_match})>"
