"""
Modelos de Funcionários e Pagamentos
Para registro de transferências por fora (gasolina, adiantamentos, etc)
"""
from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Date, Text, ForeignKey
from sqlalchemy.orm import relationship

# Importa Base do módulo financeiro
from .database import Base


class Funcionario(Base):
    """Funcionários que recebem pagamentos por fora"""
    __tablename__ = 'funcionarios'
    
    id = Column(Integer, primary_key=True)
    nome = Column(String(100), nullable=False)
    ativo = Column(Boolean, default=True)
    criado_em = Column(DateTime, default=datetime.now)
    
    # Relacionamento com pagamentos
    pagamentos = relationship("PagamentoFuncionario", back_populates="funcionario", lazy="dynamic")
    
    def __repr__(self):
        return f"<Funcionario({self.nome})>"
    
    @property
    def total_pagamentos(self) -> float:
        """Total de pagamentos recebidos"""
        return sum(p.valor for p in self.pagamentos.all())


class PagamentoFuncionario(Base):
    """Registros de pagamentos/transferências a funcionários"""
    __tablename__ = 'pagamentos_funcionarios'
    
    id = Column(Integer, primary_key=True)
    funcionario_id = Column(Integer, ForeignKey('funcionarios.id'), nullable=False)
    tipo = Column(String(50), nullable=False)  # gasolina, adiantamento, bonus, outros
    valor = Column(Float, nullable=False)
    data = Column(Date, default=date.today)
    descricao = Column(Text)
    criado_em = Column(DateTime, default=datetime.now)
    
    # Relacionamento
    funcionario = relationship("Funcionario", back_populates="pagamentos")
    
    # Tipos disponíveis
    TIPOS = [
        "Gasolina",
        "Adiantamento",
        "Bônus",
        "Reembolso",
        "Outros"
    ]
    
    def __repr__(self):
        return f"<Pagamento({self.tipo}: R$ {self.valor:.2f})>"
