"""
Modelo de banco de dados para extratos bancários do Banco do Brasil
Estrutura simplificada baseada no formato de extrato padrão BB
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, Date
from datetime import datetime

# Importa Base do módulo financeiro dedicado
from .database import Base


class ExtratoBB(Base):
    """
    Lançamentos de extratos bancários do Banco do Brasil
    
    Estrutura baseada nas colunas padrão do extrato BB:
    Status | Dt. balancete | Ag. origem | Lote | Histórico | Documento | Valor R$ | Fatura | Tipo
    """
    __tablename__ = 'extratos_bb'

    id = Column(Integer, primary_key=True)
    
    # === COLUNAS DO EXTRATO BB ===
    status = Column(String(20))  # Baixado, Pendente
    dt_balancete = Column(Date, nullable=False)  # Data do lançamento
    ag_origem = Column(String(10))  # Agência de origem
    lote = Column(String(20))  # Número do lote
    historico = Column(String(255), nullable=False)  # Descrição da transação
    documento = Column(String(50))  # Número do documento
    valor = Column(Float, nullable=False)  # Valor em R$
    fatura = Column(String(100))  # Referência da fatura (FT 3538, FTs 3094 e 3115, etc.)
    tipo = Column(String(50))  # Categoria: Coagulação, Ionograma, Hematologia, Base, etc.
    
    # === CAMPOS DE CONTROLE ===
    historico_complementar = Column(Text)  # Linha complementar do histórico (ex: nome do pagador)
    mes_referencia = Column(String(10))  # Jan, Fev, Mar... (aba de origem)
    ano_referencia = Column(Integer)  # 2025
    data_upload = Column(DateTime, default=datetime.now)
    arquivo_origem = Column(String(255))  # Nome do arquivo importado
    hash_lancamento = Column(String(64), unique=True)  # Para evitar duplicatas
    observacoes = Column(Text)

    def __repr__(self):
        status_emoji = "✅" if self.status == "Baixado" else "⏳"
        return f"<ExtratoBB({status_emoji} {self.dt_balancete} | R$ {self.valor:.2f} | {self.tipo or 'N/A'})>"
    
    @property
    def is_baixado(self) -> bool:
        """Verifica se o lançamento foi baixado"""
        return self.status and self.status.lower() == 'baixado'
    
    @property
    def is_pendente(self) -> bool:
        """Verifica se o lançamento está pendente"""
        return self.status and self.status.lower() == 'pendente'
    
    @property
    def tem_fatura(self) -> bool:
        """Verifica se o lançamento tem fatura vinculada"""
        return bool(self.fatura and self.fatura.strip())


class ResumoMensal(Base):
    """
    Resumo mensal do extrato para dashboard
    Calculado automaticamente ao importar extratos
    """
    __tablename__ = 'resumos_mensais'
    
    id = Column(Integer, primary_key=True)
    mes = Column(String(10), nullable=False)  # Jan, Fev, Mar...
    ano = Column(Integer, nullable=False)
    
    # Totais
    total_lancamentos = Column(Integer, default=0)
    total_valor = Column(Float, default=0.0)
    total_entradas = Column(Float, default=0.0) # Créditos
    total_saidas = Column(Float, default=0.0) # Débitos (Absoluto)
    total_aportes = Column(Float, default=0.0) # Aportes de capital
    total_entradas_sem_aportes = Column(Float, default=0.0) # Entradas sem contar aportes
    total_baixados = Column(Integer, default=0)
    valor_baixados = Column(Float, default=0.0)
    total_pendentes = Column(Integer, default=0)
    valor_pendentes = Column(Float, default=0.0)
    
    # Por tipo
    total_hematologia = Column(Float, default=0.0)
    total_coagulacao = Column(Float, default=0.0)
    total_ionograma = Column(Float, default=0.0)
    total_base = Column(Float, default=0.0)
    total_outros = Column(Float, default=0.0)
    
    data_atualizacao = Column(DateTime, default=datetime.now)

    def __repr__(self):
        return f"<ResumoMensal({self.mes}/{self.ano} - R$ {self.total_valor:.2f})>"