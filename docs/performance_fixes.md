# Guia de Correções de Performance

Este documento lista os problemas de performance identificados e suas soluções.

## 🐌 Problemas Identificados

### 1. Uso de `.iterrows()` em Pandas (CRÍTICO)

**Localização:**
- `dashboard.py:229` - função `salvar_produtos()`
- `dashboard.py:1657` - processamento de extratos editados
- `modules/finance/extrato_parser.py:77, 183` - parsing de planilhas
- `modules/utils/importer.py:72` - importação de dados

**Problema:**
`.iterrows()` é 10-100x mais lento que operações vetorizadas do Pandas.

**Solução:**
```python
# ❌ LENTO - iterrows
for index, row in df.iterrows():
    produto = Produto(
        nome=row['Nome do Produto'],
        preco_custo=float(row['Preço de Custo'])
    )
    session.add(produto)

# ✅ RÁPIDO - operações vetorizadas + bulk insert
produtos = [
    Produto(
        nome=row['Nome do Produto'],
        preco_custo=float(row['Preço de Custo'])
    )
    for _, row in df.itertuples(index=True, name=None)
]
session.bulk_save_objects(produtos)
```

---

### 2. Tabelas Grandes no Streamlit

**Localização:**
- `dashboard.py:640, 1186, 1623` - `st.dataframe()` e `st.data_editor()`

**Problema:**
Streamlit renderiza todas as linhas de uma vez, causando travamento com muitos dados.

**Solução:**
```python
# ✅ Implementar paginação
import streamlit as st

def paginate_dataframe(df, page_size=50):
    """Pagina dataframe para melhor performance"""
    total_pages = len(df) // page_size + (1 if len(df) % page_size > 0 else 0)

    page = st.number_input(
        'Página',
        min_value=1,
        max_value=max(1, total_pages),
        value=1
    )

    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size

    st.info(f"Mostrando {start_idx+1}-{min(end_idx, len(df))} de {len(df)} registros")

    return df.iloc[start_idx:end_idx]

# Uso:
df_paginado = paginate_dataframe(df_grande, page_size=50)
st.dataframe(df_paginado)
```

---

### 3. Queries de Banco de Dados Não Otimizadas

**Problema:**
- Falta de índices nas colunas mais consultadas
- N+1 queries ao carregar relacionamentos (itens, produtos)

**Solução:**
```python
# ✅ Adicionar índices no banco
from sqlalchemy import Index

class Licitacao(Base):
    __tablename__ = 'licitacoes'
    # ... colunas ...

    __table_args__ = (
        Index('idx_status', 'status'),
        Index('idx_data_captura', 'data_captura'),
        Index('idx_pncp_id', 'pncp_id'),
    )

class ItemLicitacao(Base):
    __tablename__ = 'itens_licitacao'
    # ... colunas ...

    __table_args__ = (
        Index('idx_licitacao_id', 'licitacao_id'),
        Index('idx_produto_match_id', 'produto_match_id'),
    )

# ✅ Usar joinedload para evitar N+1 queries
from sqlalchemy.orm import joinedload

licitacoes = session.query(Licitacao)\
    .options(joinedload(Licitacao.itens))\
    .filter(Licitacao.status == 'Nova')\
    .all()
```

---

### 4. Parsing de Excel Lento

**Localização:**
- `modules/finance/extrato_parser.py:38-49` - lê todas as abas

**Problema:**
Lê todas as abas do Excel, mesmo que não sejam necessárias.

**Solução:**
```python
# ✅ Ler apenas abas necessárias
with pd.ExcelFile(file_path, engine='openpyxl') as xl:
    # Filtra abas antes de processar
    sheet_names = [s for s in xl.sheet_names if s.lower() != 'geral']

    for sheet_name in sheet_names:
        mes = self._identificar_mes(sheet_name)
        if not mes:
            continue  # Pula aba sem processar

        # Usa chunksize para arquivos muito grandes
        df = pd.read_excel(
            xl,
            sheet_name=sheet_name,
            engine='openpyxl',
            # dtype para evitar inferência de tipos (mais rápido)
            dtype={'Status': str, 'Lote': str}
        )
```

---

### 5. Matching de Produtos Ineficiente

**Localização:**
- `dashboard.py:66-186` - função `best_match_against_keywords()`
- `dashboard.py:244-272` - função `match_itens()`

**Problema:**
Matching é feito repetidamente para os mesmos produtos/itens.

**Solução:**
```python
# ✅ Cache de resultados de matching
from functools import lru_cache
import hashlib

@lru_cache(maxsize=1000)
def cached_match(item_hash, produto_hash):
    """Cache de matching para evitar recálculo"""
    # ... lógica de matching ...
    return score, keyword

def match_itens_cached(session, licitacao_id, limiar=75):
    """Versão otimizada com cache"""
    licitacao = session.query(Licitacao).filter_by(id=licitacao_id).first()
    produtos = session.query(Produto).all()

    # Pré-computa hashes
    produtos_hash = {
        p.id: hashlib.md5(f"{p.nome}_{p.palavras_chave}".encode()).hexdigest()
        for p in produtos
    }

    count = 0
    for item in licitacao.itens:
        item_hash = hashlib.md5((item.descricao or "").encode()).hexdigest()

        melhor_match = None
        melhor_score = 0

        for prod in produtos:
            score, _ = cached_match(item_hash, produtos_hash[prod.id])
            if score > melhor_score:
                melhor_match = prod
                melhor_score = score

        if melhor_match and melhor_score >= limiar:
            item.produto_match_id = melhor_match.id
            item.match_score = melhor_score
            count += 1

    session.commit()
    return count
```

---

## 🚀 Otimizações Adicionais

### 6. Configuração do Streamlit

Adicionar ao arquivo `.streamlit/config.toml`:

```toml
[server]
maxUploadSize = 200
enableXsrfProtection = true
enableCORS = false

[runner]
magicEnabled = false
fastReruns = true

[client]
showErrorDetails = true
toolbarMode = "minimal"

[browser]
gatherUsageStats = false
```

### 7. Lazy Loading de Dados

```python
# ✅ Carregar dados apenas quando necessário
import streamlit as st

@st.cache_data(ttl=300)  # Cache por 5 minutos
def load_licitacoes(status=None, limit=100):
    """Carrega licitações com cache"""
    session = get_session()
    query = session.query(Licitacao)

    if status:
        query = query.filter(Licitacao.status == status)

    query = query.order_by(Licitacao.data_captura.desc())
    query = query.limit(limit)

    licitacoes = query.all()
    session.close()

    return licitacoes
```

### 8. Processamento em Background

Para operações pesadas (importação, matching):

```python
import concurrent.futures
import streamlit as st

def processar_licitacoes_paralelo(licitacoes_ids):
    """Processa licitações em paralelo"""
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(match_itens, session, lic_id)
            for lic_id in licitacoes_ids
        ]

        # Mostra progresso
        progress_bar = st.progress(0)
        for i, future in enumerate(concurrent.futures.as_completed(futures)):
            progress_bar.progress((i + 1) / len(futures))

        results = [f.result() for f in futures]

    return results
```

---

## 📊 Monitoramento

Execute o teste de performance regularmente:

```bash
python scripts/performance_test.py
```

Isso irá gerar um relatório identificando os gargalos mais críticos.

---

## ✅ Checklist de Otimizações

- [ ] Substituir todos os `.iterrows()` por `.itertuples()` ou operações vetorizadas
- [ ] Adicionar índices nas tabelas do banco de dados
- [ ] Implementar paginação em todas as tabelas grandes do Streamlit
- [ ] Adicionar cache (`@st.cache_data`) em funções de consulta
- [ ] Usar `bulk_save_objects()` para inserções em lote
- [ ] Implementar lazy loading com `joinedload()`
- [ ] Adicionar cache de resultados de matching
- [ ] Configurar `.streamlit/config.toml`
- [ ] Testar com dados reais de produção
- [ ] Monitorar performance após otimizações

---

## 🎯 Impacto Esperado

Após implementar todas as otimizações:

- ⚡ **10-50x mais rápido** em operações com Pandas
- ⚡ **3-5x mais rápido** em queries de banco de dados
- ⚡ **Redução de 80-90%** no tempo de renderização de tabelas
- ⚡ **Melhor responsividade** geral do sistema
