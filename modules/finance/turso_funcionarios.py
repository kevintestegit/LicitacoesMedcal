"""
Módulo para gerenciamento de Funcionários e Pagamentos via Turso (conexão direta)
Usa libsql_experimental para conexão direta com Turso, garantindo sincronização
"""
from datetime import date, datetime
from typing import List, Optional
from dataclasses import dataclass
from ..database.database_config import is_using_turso, get_turso_url, get_turso_token


@dataclass
class FuncionarioDTO:
    """Data Transfer Object para Funcionário"""
    id: int
    nome: str
    ativo: bool
    criado_em: Optional[datetime] = None


@dataclass  
class PagamentoDTO:
    """Data Transfer Object para Pagamento"""
    id: int
    funcionario_id: int
    funcionario_nome: str
    tipo: str
    valor: float
    data: date
    descricao: Optional[str] = None
    criado_em: Optional[datetime] = None


# Tipos de pagamento disponíveis
TIPOS_PAGAMENTO = [
    "Gasolina",
    "Adiantamento",
    "Bônus",
    "Reembolso",
    "Outros"
]


def _get_conn():
    """Retorna conexão com Turso"""
    if not is_using_turso():
        raise RuntimeError("Turso não está configurado")
    
    import libsql_experimental as libsql
    return libsql.connect(
        get_turso_url(),
        auth_token=get_turso_token()
    )


def init_tables():
    """Cria tabelas se não existirem"""
    if not is_using_turso():
        return
    
    conn = _get_conn()
    
    conn.execute('''
        CREATE TABLE IF NOT EXISTS funcionarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome VARCHAR(100) NOT NULL,
            ativo INTEGER DEFAULT 1,
            criado_em TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.execute('''
        CREATE TABLE IF NOT EXISTS pagamentos_funcionarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            funcionario_id INTEGER NOT NULL,
            tipo VARCHAR(50) NOT NULL,
            valor REAL NOT NULL,
            data TEXT DEFAULT CURRENT_DATE,
            descricao TEXT,
            criado_em TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (funcionario_id) REFERENCES funcionarios(id)
        )
    ''')
    
    conn.commit()


# ==================== FUNCIONÁRIOS ====================

def listar_funcionarios(apenas_ativos: bool = True) -> List[FuncionarioDTO]:
    """Lista funcionários"""
    conn = _get_conn()
    
    if apenas_ativos:
        cur = conn.execute("SELECT id, nome, ativo, criado_em FROM funcionarios WHERE ativo = 1 ORDER BY nome")
    else:
        cur = conn.execute("SELECT id, nome, ativo, criado_em FROM funcionarios ORDER BY nome")
    
    resultado = []
    for row in cur.fetchall():
        resultado.append(FuncionarioDTO(
            id=row[0],
            nome=row[1],
            ativo=bool(row[2]),
            criado_em=row[3]
        ))
    
    return resultado


def buscar_funcionario(funcionario_id: int) -> Optional[FuncionarioDTO]:
    """Busca funcionário por ID"""
    conn = _get_conn()
    cur = conn.execute("SELECT id, nome, ativo, criado_em FROM funcionarios WHERE id = ?", (funcionario_id,))
    row = cur.fetchone()
    
    if row:
        return FuncionarioDTO(id=row[0], nome=row[1], ativo=bool(row[2]), criado_em=row[3])
    return None


def buscar_funcionario_por_nome(nome: str) -> Optional[FuncionarioDTO]:
    """Busca funcionário por nome"""
    conn = _get_conn()
    cur = conn.execute("SELECT id, nome, ativo, criado_em FROM funcionarios WHERE nome = ?", (nome,))
    row = cur.fetchone()
    
    if row:
        return FuncionarioDTO(id=row[0], nome=row[1], ativo=bool(row[2]), criado_em=row[3])
    return None


def criar_funcionario(nome: str) -> FuncionarioDTO:
    """Cria novo funcionário"""
    conn = _get_conn()
    cur = conn.execute(
        "INSERT INTO funcionarios (nome, ativo) VALUES (?, 1) RETURNING id, nome, ativo, criado_em",
        (nome,)
    )
    row = cur.fetchone()
    conn.commit()
    
    return FuncionarioDTO(id=row[0], nome=row[1], ativo=bool(row[2]), criado_em=row[3])


def desativar_funcionario(funcionario_id: int) -> bool:
    """Desativa funcionário"""
    conn = _get_conn()
    conn.execute("UPDATE funcionarios SET ativo = 0 WHERE id = ?", (funcionario_id,))
    conn.commit()
    return True


# ==================== PAGAMENTOS ====================

def listar_pagamentos(
    funcionario_nome: Optional[str] = None,
    tipo: Optional[str] = None,
    mes: Optional[int] = None
) -> List[PagamentoDTO]:
    """Lista pagamentos com filtros opcionais"""
    conn = _get_conn()
    
    query = """
        SELECT p.id, p.funcionario_id, f.nome, p.tipo, p.valor, p.data, p.descricao, p.criado_em
        FROM pagamentos_funcionarios p
        JOIN funcionarios f ON p.funcionario_id = f.id
        WHERE 1=1
    """
    params = []
    
    if funcionario_nome and funcionario_nome != "Todos":
        query += " AND f.nome = ?"
        params.append(funcionario_nome)
    
    if tipo and tipo != "Todos":
        query += " AND p.tipo = ?"
        params.append(tipo)
    
    if mes:
        query += " AND CAST(strftime('%m', p.data) AS INTEGER) = ?"
        params.append(mes)
    
    query += " ORDER BY p.data DESC"
    
    cur = conn.execute(query, tuple(params))
    
    resultado = []
    for row in cur.fetchall():
        resultado.append(PagamentoDTO(
            id=row[0],
            funcionario_id=row[1],
            funcionario_nome=row[2],
            tipo=row[3],
            valor=row[4],
            data=row[5] if isinstance(row[5], date) else datetime.strptime(row[5], "%Y-%m-%d").date() if row[5] else None,
            descricao=row[6],
            criado_em=row[7]
        ))
    
    return resultado


def criar_pagamento(
    funcionario_id: int,
    tipo: str,
    valor: float,
    data_pagamento: date,
    descricao: Optional[str] = None
) -> PagamentoDTO:
    """Cria novo pagamento"""
    conn = _get_conn()
    
    # Busca nome do funcionário
    cur = conn.execute("SELECT nome FROM funcionarios WHERE id = ?", (funcionario_id,))
    func_row = cur.fetchone()
    funcionario_nome = func_row[0] if func_row else "Desconhecido"
    
    cur = conn.execute(
        """INSERT INTO pagamentos_funcionarios (funcionario_id, tipo, valor, data, descricao)
           VALUES (?, ?, ?, ?, ?) RETURNING id, criado_em""",
        (funcionario_id, tipo, valor, data_pagamento.isoformat(), descricao)
    )
    row = cur.fetchone()
    conn.commit()
    
    return PagamentoDTO(
        id=row[0],
        funcionario_id=funcionario_id,
        funcionario_nome=funcionario_nome,
        tipo=tipo,
        valor=valor,
        data=data_pagamento,
        descricao=descricao,
        criado_em=row[1]
    )


def remover_pagamento(pagamento_id: int) -> bool:
    """Remove pagamento"""
    conn = _get_conn()
    conn.execute("DELETE FROM pagamentos_funcionarios WHERE id = ?", (pagamento_id,))
    conn.commit()
    return True


def remover_pagamentos(ids: List[int]) -> int:
    """Remove múltiplos pagamentos"""
    conn = _get_conn()
    count = 0
    for pid in ids:
        conn.execute("DELETE FROM pagamentos_funcionarios WHERE id = ?", (pid,))
        count += 1
    conn.commit()
    return count
