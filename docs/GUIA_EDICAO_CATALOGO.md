# 📝 Guia: Como Editar o Catálogo de Produtos

## 📋 Índice
1. [Visão Geral](#visão-geral)
2. [Método 1: Editar JSON (Recomendado)](#método-1-editar-json-recomendado)
3. [Método 2: Editar Script Python](#método-2-editar-script-python)
4. [Estrutura dos Dados](#estrutura-dos-dados)
5. [Exemplos Práticos](#exemplos-práticos)

---

## 🎯 Visão Geral

Existem **2 formas** de ajustar o catálogo de produtos:

| Método | Arquivo | Facilidade | Recomendado |
|--------|---------|------------|-------------|
| **Método 1** | `data/catalogo_produtos.json` | ⭐⭐⭐⭐⭐ Muito Fácil | ✅ Sim |
| **Método 2** | `scripts/restore_catalogo.py` | ⭐⭐⭐ Médio | Para devs |

---

## 🌟 Método 1: Editar JSON (Recomendado)

### **Por que usar JSON?**
- ✅ Não precisa mexer em código Python
- ✅ Fácil de editar (qualquer editor de texto)
- ✅ Fácil de versionar no Git
- ✅ Pode ser editado no Excel/Google Sheets (via conversão)
- ✅ Menos chances de erro

### **Passo a Passo:**

#### **1. Abrir o Arquivo**

```bash
# No VS Code
code data/catalogo_produtos.json

# Ou use seu editor favorito
notepad data/catalogo_produtos.json
```

#### **2. Estrutura do Arquivo**

```json
[
  {
    "nome": "Nome do Produto",
    "palavras_chave": "PALAVRA1, PALAVRA2, PALAVRA3",
    "preco_custo": 1000.00,
    "margem_minima": 25.0
  },
  {
    "nome": "Outro Produto",
    "palavras_chave": "TERMO1, TERMO2",
    "preco_custo": 500.00,
    "margem_minima": 30.0
  }
]
```

#### **3. Editar Produtos**

**✏️ Editar produto existente:**
```json
{
  "nome": "Analisador Hematológico Automatizado",
  "palavras_chave": "HEMATOLOGIA, ANALISADOR, HEMOGRAMA, CBC",
  "preco_custo": 90000.00,    ← Mudei de 85000 para 90000
  "margem_minima": 30.0       ← Mudei de 25 para 30
}
```

**➕ Adicionar novo produto:**

No final do arquivo, antes do `]`, adicione:
```json
  ,
  {
    "nome": "Meu Novo Produto",
    "palavras_chave": "PALAVRA1, PALAVRA2, PALAVRA3",
    "preco_custo": 1500.00,
    "margem_minima": 25.0
  }
```

**⚠️ ATENÇÃO:** Não esqueça a vírgula `,` entre os produtos!

**🗑️ Remover produto:**

Apague o bloco inteiro `{ ... },` incluindo a vírgula.

#### **4. Validar JSON (Opcional)**

Antes de importar, você pode validar se o JSON está correto:

- **Online:** [jsonlint.com](https://jsonlint.com/)
- **VS Code:** Já valida automaticamente (mostra erros em vermelho)

#### **5. Importar para o Banco**

```bash
# Importar substituindo produtos existentes
python scripts/import_catalogo_json.py --substituir

# Ou adicionar aos produtos existentes
python scripts/import_catalogo_json.py
```

**Pronto!** Os produtos foram importados.

---

## 🔧 Método 2: Editar Script Python

### **Quando usar:**
- Você é desenvolvedor Python
- Quer manter tudo em código
- Não quer arquivo separado

### **Passo a Passo:**

#### **1. Abrir o Script**

```bash
code scripts/restore_catalogo.py
```

#### **2. Localizar a Lista de Produtos**

Procure pela linha **33** (aproximadamente):

```python
produtos = [
    {
        "nome": "Analisador Hematológico Automatizado",
        "palavras_chave": "HEMATOLOGIA, ...",
        "preco_custo": 85000.00,
        "margem_minima": 25.0
    },
    # ... mais produtos
]
```

#### **3. Editar**

Mesma lógica do JSON, mas dentro do Python.

**Adicionar novo produto:**
```python
    {
        "nome": "Meu Novo Produto",
        "palavras_chave": "PALAVRA1, PALAVRA2",
        "preco_custo": 1000.00,
        "margem_minima": 25.0
    },
```

#### **4. Salvar e Rodar**

```bash
python scripts/restore_catalogo.py --substituir
```

---

## 📊 Estrutura dos Dados

### **Campos Obrigatórios:**

| Campo | Tipo | Descrição | Exemplo |
|-------|------|-----------|---------|
| `nome` | String | Nome do produto | "Analisador Hematológico" |
| `palavras_chave` | String | Palavras separadas por vírgula (MAIÚSCULAS) | "HEMATOLOGIA, ANALISADOR, CBC" |
| `preco_custo` | Float | Preço de custo em reais | 85000.00 |
| `margem_minima` | Float | Margem mínima em % | 25.0 |

### **Campos Opcionais:**

| Campo | Tipo | Descrição | Padrão |
|-------|------|-----------|--------|
| `preco_referencia` | Float | Preço de mercado/referência | 0.0 |
| `fonte_referencia` | String | Fonte do preço (ex: "Empresa X") | "" |

### **Regras:**

1. **Palavras-chave:**
   - Sempre em MAIÚSCULAS
   - Separadas por vírgula e espaço
   - Quanto mais palavras, melhor o match
   - Incluir sinônimos e variações

2. **Preços:**
   - Usar ponto `.` para decimais (não vírgula)
   - Exemplo: `1500.00` não `1.500,00`

3. **Margem:**
   - Em porcentagem (25 = 25%)
   - Número decimal: `25.0` não `0.25`

---

## 💡 Exemplos Práticos

### **Exemplo 1: Adicionar Produto Novo**

**Produto:** Seringa Descartável 10ml

**No JSON:**
```json
{
  "nome": "Seringa Descartável 10ml",
  "palavras_chave": "SERINGA, SERINGA DESCARTAVEL, SERINGA 10ML, SERINGA ESTERIL, SERINGAS",
  "preco_custo": 0.50,
  "margem_minima": 45.0
}
```

**Importar:**
```bash
python scripts/import_catalogo_json.py --substituir
```

### **Exemplo 2: Atualizar Preço**

**Antes:**
```json
{
  "nome": "Luvas de Procedimento",
  "palavras_chave": "LUVA, LUVAS, LUVA PROCEDIMENTO",
  "preco_custo": 25.00,
  "margem_minima": 35.0
}
```

**Depois:**
```json
{
  "nome": "Luvas de Procedimento",
  "palavras_chave": "LUVA, LUVAS, LUVA PROCEDIMENTO",
  "preco_custo": 30.00,    ← Atualizado
  "margem_minima": 35.0
}
```

**Importar:**
```bash
python scripts/import_catalogo_json.py --substituir
```

### **Exemplo 3: Adicionar Palavras-Chave**

**Antes:**
```json
{
  "nome": "Cateter Venoso Central",
  "palavras_chave": "CATETER VENOSO CENTRAL, CVC",
  "preco_custo": 45.00,
  "margem_minima": 35.0
}
```

**Depois:**
```json
{
  "nome": "Cateter Venoso Central",
  "palavras_chave": "CATETER VENOSO CENTRAL, CVC, CATETER CENTRAL, ACESSO CENTRAL, DUPLO LUMEN, TRIPLO LUMEN, INTRACATH",
  "preco_custo": 45.00,
  "margem_minima": 35.0
}
```

### **Exemplo 4: Remover Produto**

Simplesmente **apague o bloco inteiro** do JSON:

```json
{
  "nome": "Produto que não quero mais",
  "palavras_chave": "...",
  "preco_custo": 100.00,
  "margem_minima": 25.0
},  ← Apague tudo isso
```

---

## 🔄 Workflow Completo

### **Editar → Importar → Testar → Versionar**

```bash
# 1. Editar o JSON
code data/catalogo_produtos.json

# 2. Importar para o banco
python scripts/import_catalogo_json.py --substituir

# 3. Testar no dashboard
streamlit run dashboard.py

# 4. Se estiver OK, versionar
git add data/catalogo_produtos.json
git commit -m "Atualiza catálogo: adiciona 5 novos produtos"
git push
```

---

## 🎨 Dicas de Palavras-Chave

### **Boas Práticas:**

1. **Use sinônimos:**
   ```
   "CATETER, CATETER IV, JELCO, ABOCATH, CATETER INTRAVENOSO"
   ```

2. **Inclua variações:**
   ```
   "SONDA VESICAL, SONDA FOLEY, SVD, CATETER FOLEY"
   ```

3. **Adicione termos técnicos e coloquiais:**
   ```
   "EQUIPO, EQUIPO SORO, EQUIPO MACROGOTAS, SET INFUSAO"
   ```

4. **Separação:**
   - Use vírgula + espaço: `"TERMO1, TERMO2, TERMO3"`
   - Não use apenas vírgula: ~~`"TERMO1,TERMO2"`~~

5. **MAIÚSCULAS:**
   - Sempre em maiúsculas
   - Facilita a busca no sistema

---

## 📁 Localização dos Arquivos

```
LicitacoesMedcal/
├── data/
│   └── catalogo_produtos.json          ← Editar aqui (Método 1)
│
├── scripts/
│   ├── import_catalogo_json.py         ← Importar JSON
│   └── restore_catalogo.py             ← Método 2 (hardcoded)
│
└── CATALOGO_BACKUP.md                  ← Apenas visualização
```

---

## ❓ FAQ

**Q: Qual método é melhor?**
A: JSON (Método 1) é mais fácil e flexível.

**Q: Posso editar o JSON no Excel?**
A: Não diretamente, mas pode converter JSON→CSV, editar no Excel, e converter CSV→JSON.

**Q: O que acontece se eu cometer erro no JSON?**
A: O script mostrará erro e não importará. Use um validador JSON antes.

**Q: Posso ter os dois? JSON e Python?**
A: Sim, mas escolha um como "fonte da verdade" para evitar confusão.

**Q: Como adicionar 100 produtos de uma vez?**
A: Melhor usar JSON. Você pode gerar o JSON programaticamente ou converter de planilha.

**Q: O CATALOGO_BACKUP.md serve para quê?**
A: Apenas documentação/visualização. Não é usado pelos scripts.

---

## 🎓 Recursos

- **Validador JSON:** https://jsonlint.com/
- **Conversor CSV→JSON:** https://www.convertcsv.com/csv-to-json.htm
- **Editor JSON Visual:** https://jsoneditoronline.org/

---

**Última atualização:** 27 de novembro de 2025
