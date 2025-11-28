# Como Usar as Otimizações

## 1. Funções Otimizadas

Substitua no `dashboard.py`:

```python
# Importe as funções otimizadas
from modules.utils.performance_helpers import (
    salvar_produtos_otimizado,
    paginate_dataframe,
    load_licitacoes_cached,
    load_produtos_cached
)

# Substitua salvar_produtos() por:
def salvar_produtos(df_editor):
    total = salvar_produtos_otimizado(df_editor)
    st.success(f"Catálogo atualizado! {total} produtos salvos.")

# Para tabelas grandes, use paginação:
df_paginado = paginate_dataframe(df_grande, page_size=50)
st.dataframe(df_paginado)

# Use cache para queries frequentes:
licitacoes = load_licitacoes_cached(status='Nova', limit=100)
produtos = load_produtos_cached()
```

## 2. Índices de Banco de Dados

Os índices foram adicionados automaticamente. Agora as queries em:
- `status`
- `data_captura`
- `pncp_id`
- `licitacao_id`
- `produto_match_id`

São muito mais rápidas!

## 3. Configuração do Streamlit

A configuração foi aplicada automaticamente em `.streamlit/config.toml`.

## 4. Substituir iterrows()

Sempre que tiver um loop como:

```python
# ❌ LENTO
for idx, row in df.iterrows():
    # processar row
```

Substitua por:

```python
# ✅ RÁPIDO
for row in df.itertuples():
    # processar row (acesse campos como row.nome_coluna)
```

Ou melhor ainda, use operações vetorizadas:

```python
# ✅ MUITO RÁPIDO
df['nova_coluna'] = df['coluna'].apply(funcao)
# ou
df['nova_coluna'] = df['col1'] + df['col2']  # operação vetorizada
```

## 5. Verificar Melhorias

Execute novamente o teste de performance:

```bash
python scripts/performance_test.py
```

Compare os resultados antes e depois!
