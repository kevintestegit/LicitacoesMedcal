# 📊 Módulo de Extratos BB

Sistema simplificado para gestão de extratos bancários do Banco do Brasil.

## 📋 Estrutura de Dados

O módulo trabalha com as seguintes colunas do extrato BB:

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| Status | String | `Baixado` ou `Pendente` |
| Dt. balancete | Date | Data do lançamento |
| Ag. origem | String | Agência de origem |
| Lote | String | Número do lote |
| Histórico | String | Descrição da transação |
| Documento | String | Número do documento |
| Valor R$ | Float | Valor do lançamento |
| Fatura | String | Referência da fatura (FT 3538, FTs 3094, etc.) |
| Tipo | String | Categoria (Hematologia, Coagulação, Ionograma, Base) |

## 🚀 Como Usar

### Importar Extrato

```python
from modules.finance import importar_extrato_bb
from modules.database.database import get_session

session = get_session()

# Importa extrato completo (todas as abas/meses)
stats = importar_extrato_bb(
    file_path='ExtratoBB2025.xlsx',
    session=session,
    ano=2025  # Opcional, detecta automaticamente
)

print(f"Importados: {stats['importados']}")
print(f"Duplicados: {stats['duplicados']}")
print(f"Erros: {stats['erros']}")
```

### Consultar Lançamentos

```python
from modules.finance import ExtratoBB

# Todos os pendentes
pendentes = session.query(ExtratoBB).filter_by(status='Pendente').all()

# Por tipo
hematologia = session.query(ExtratoBB).filter_by(tipo='Hematologia').all()

# Por mês
janeiro = session.query(ExtratoBB).filter_by(mes_referencia='Jan').all()

# Baixados com fatura
baixados_fatura = session.query(ExtratoBB).filter(
    ExtratoBB.status == 'Baixado',
    ExtratoBB.fatura.isnot(None)
).all()
```

### Resumos Mensais

```python
from modules.finance import ResumoMensal

# Resumo de julho
resumo = session.query(ResumoMensal).filter_by(mes='Jul', ano=2025).first()

print(f"Total: R$ {resumo.total_valor:,.2f}")
print(f"Baixados: R$ {resumo.valor_baixados:,.2f}")
print(f"Pendentes: R$ {resumo.valor_pendentes:,.2f}")
print(f"Hematologia: R$ {resumo.total_hematologia:,.2f}")
```

## 📁 Estrutura do Módulo

```
modules/finance/
├── __init__.py          # Exportações
├── bank_models.py       # Modelos SQLAlchemy (ExtratoBB, ResumoMensal)
├── extrato_parser.py    # Parser do arquivo Excel BB
└── README.md            # Esta documentação
```

## 🔧 Tabelas do Banco

### extratos_bb

Armazena cada lançamento do extrato:

- `id`: Chave primária
- `status`: Baixado/Pendente
- `dt_balancete`: Data
- `ag_origem`: Agência
- `lote`: Número do lote
- `historico`: Descrição
- `documento`: Número do documento
- `valor`: Valor R$
- `fatura`: Referência da fatura
- `tipo`: Categoria (Hematologia, etc.)
- `historico_complementar`: Linha complementar do histórico
- `mes_referencia`: Jan, Fev, Mar...
- `ano_referencia`: 2025
- `hash_lancamento`: Hash único (evita duplicatas)

### resumos_mensais

Totalizadores por mês:

- Contagem e soma total
- Separação por status (Baixado/Pendente)
- Separação por tipo (Hematologia, Coagulação, Ionograma, Base)

## ⚙️ Parser

O `ExtratoBBParser` foi desenvolvido especificamente para o formato do extrato BB:

- **Múltiplas abas**: Cada mês em uma aba (Jan, Fev, Mar...)
- **Linhas intercaladas**: Captura o histórico complementar
- **Detecção automática**: Localiza o cabeçalho automaticamente
- **Prevenção de duplicatas**: Hash único por lançamento

## 📝 Dependências

```
pandas>=2.0.0
openpyxl>=3.1.0
sqlalchemy>=2.0.0
```

---

**Desenvolvido para Medcal Gestão**
