# 🔄 Guia Completo: Backup e Sincronização entre Máquinas

## 📚 Índice
1. [Como Funciona](#como-funciona)
2. [Importar Catálogo Inicial](#importar-catálogo-inicial)
3. [Fazer Backup](#fazer-backup)
4. [Sincronizar via GitHub](#sincronizar-via-github)
5. [Restaurar em Outra Máquina](#restaurar-em-outra-máquina)
6. [Casos de Uso](#casos-de-uso)

---

## 🎯 Como Funciona

### O Problema
Cada máquina tem seu próprio banco de dados local (`.db`), e esses arquivos **NÃO** vão para o GitHub (por questões de segurança e boas práticas).

### A Solução
Sistema de **backup/restore em JSON**:
- ✅ Exporta dados para JSON (texto puro)
- ✅ JSON pode ser versionado no Git
- ✅ Importa JSON em qualquer máquina
- ✅ Simples, seguro e confiável

### Arquitetura

```
Máquina A                    GitHub                    Máquina B
┌─────────┐                ┌─────────┐                ┌─────────┐
│ medcal.db│──[backup]──>  │JSON file│──[pull]──>    │ medcal.db│
└─────────┘                └─────────┘                └─────────┘
```

---

## 📦 Importar Catálogo Inicial

### Primeira Vez: Importar Produtos do CATALOGO_BACKUP.md

O sistema já tem um catálogo padrão com **45 produtos** prontos para importar:

```bash
# Importar catálogo completo (substitui produtos existentes)
python scripts/restore_catalogo.py --substituir

# Ou adicionar aos produtos existentes (sem substituir)
python scripts/restore_catalogo.py
```

**Produtos incluídos:**
- 🔬 Equipamentos de Hematologia
- 🧪 Equipamentos de Bioquímica
- 🩸 Equipamentos de Coagulação
- 💉 Equipamentos de Imunologia/Hormônios
- ⚡ Equipamentos de Ionograma/Eletrólitos
- 🫁 Gasometria/POCT
- 🧫 Urinálise
- 🧴 Consumíveis (tubos, luvas, máscaras)
- 💉 Cateteres (periférico, central, umbilical, etc.)
- 🔧 Sondas (nasogástrica, vesical, endotraqueal, etc.)
- 🫁 Cânulas (Guedel, traqueostomia, alto fluxo, etc.)
- 💧 Equipos (macrogotas, microgotas, bomba de infusão, etc.)
- 🔬 Testes Rápidos
- ✅ Controle de Qualidade e Manutenção

**Total:** 45 produtos com palavras-chave otimizadas para busca.

---

## 💾 Fazer Backup

### Exportar Todos os Dados

```bash
python scripts/backup_db.py
```

**O que é exportado:**
- ✅ Produtos (catálogo)
- ✅ Configurações (API keys, WhatsApp)
- ✅ Licitações capturadas
- ✅ Itens de licitação com match

**Arquivos criados:**
```
backups/
├── backup_medcal_20250127_153045.json  # Com timestamp (local)
└── backup_medcal_latest.json           # Sempre o mais recente (vai pro Git)
```

**Exemplo de saída:**
```
✅ BACKUP CONCLUÍDO COM SUCESSO!
==================================================
📦 Produtos: 45
⚙️  Configurações: 5
📋 Licitações: 128
📝 Itens: 456
📁 Arquivo: backups/backup_medcal_20250127_153045.json
```

---

## 🔄 Sincronizar via GitHub

### 1. Fazer Backup
```bash
python scripts/backup_db.py
```

### 2. Adicionar ao Git
```bash
git add backups/backup_medcal_latest.json
git commit -m "Atualiza backup do catálogo (45 produtos)"
git push
```

**Importante:**
- ✅ Apenas `backup_medcal_latest.json` vai pro GitHub
- ❌ Arquivos `.db` são ignorados (`.gitignore`)
- ❌ Backups com timestamp são ignorados

---

## 📥 Restaurar em Outra Máquina

### Passo 1: Baixar do GitHub
```bash
git pull
```

### Passo 2: Restaurar Banco de Dados

**Opção A: Restaurar Tudo (Recomendado)**
```bash
python scripts/restore_db.py
```
- Importa: produtos, configurações, licitações, itens
- Pergunta se quer substituir ou adicionar

**Opção B: Restaurar Apenas Catálogo**
```bash
python scripts/restore_catalogo.py --substituir
```
- Importa apenas os 45 produtos padrão
- Mais rápido, ideal para nova instalação

**Opção C: Restaurar Backup Específico**
```bash
python scripts/restore_db.py backups/backup_medcal_20250127_153045.json
```

---

## 💡 Casos de Uso

### Caso 1: Nova Máquina do Zero

```bash
# 1. Clonar repositório
git clone [url-do-repositório]
cd LicitacoesMedcal

# 2. Criar ambiente virtual
python -m venv .venv
.\.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac

# 3. Instalar dependências
pip install -r requirements.txt

# 4. Criar estrutura do banco
python scripts/migrate_db.py
python scripts/setup_financeiro.py

# 5. Importar catálogo
python scripts/restore_catalogo.py --substituir

# 6. Rodar o sistema
streamlit run dashboard.py
```

### Caso 2: Atualizar Catálogo em Todas as Máquinas

**Máquina A (onde você edita):**
```bash
# 1. Edite produtos no dashboard ou banco
# 2. Faça backup
python scripts/backup_db.py

# 3. Envie para GitHub
git add backups/backup_medcal_latest.json
git commit -m "Adiciona novos produtos ao catálogo"
git push
```

**Máquina B (onde você quer sincronizar):**
```bash
# 1. Baixe as alterações
git pull

# 2. Restaure o backup
python scripts/restore_db.py
# Responda "s" para SUBSTITUIR

# Pronto! Catálogo atualizado
```

### Caso 3: Backup Local para Segurança

```bash
# Fazer backup com timestamp (não vai pro Git)
python scripts/backup_db.py

# Arquivos ficam em backups/ com data/hora
# Exemplo: backup_medcal_20250127_153045.json

# Para restaurar:
python scripts/restore_db.py backups/backup_medcal_20250127_153045.json
```

### Caso 4: Sincronizar Apenas Licitações (Sem Catálogo)

O `backup_db.py` exporta tudo, mas você pode editar o JSON manualmente:

```bash
# 1. Faça backup completo
python scripts/backup_db.py

# 2. Edite o JSON e remova seções que não quer sincronizar
#    (produtos, configuracoes, etc.)

# 3. Restaure apenas o que sobrou
python scripts/restore_db.py backups/arquivo_editado.json
```

---

## 🔒 Segurança

### O que VAI para o GitHub
- ✅ `backup_medcal_latest.json` (dados não sensíveis)
- ✅ Scripts Python
- ✅ Código-fonte
- ✅ Documentação

### O que NÃO vai
- ❌ `*.db` (bancos de dados)
- ❌ `.env` (chaves de API, tokens)
- ❌ `.venv/` (ambiente virtual)
- ❌ `backup_medcal_*_*.json` (backups com timestamp)

### Dados Sensíveis

**Nunca coloque no backup JSON:**
- Senhas
- Tokens de API
- Chaves privadas

**Use o `.env` para isso:**
```bash
# .env (não versionado)
GEMINI_API_KEY=sua_chave_aqui
WHATSAPP_APIKEY=sua_chave_aqui
```

---

## 📊 Estrutura dos Arquivos

### Banco de Dados (Local)
```
data/
├── medcal.db          # Banco principal (licitações, produtos)
└── financeiro.db      # Banco financeiro (extratos, faturas)
```

### Backups (Versionáveis)
```
backups/
├── README.md                              # Documentação
├── backup_medcal_latest.json              # ✅ VAI para o Git
└── backup_medcal_20250127_153045.json     # ❌ NÃO vai para o Git
```

### Scripts
```
scripts/
├── backup_db.py           # Exporta banco → JSON
├── restore_db.py          # Importa JSON → banco
├── restore_catalogo.py    # Importa catálogo padrão (45 produtos)
├── migrate_db.py          # Cria estrutura inicial
└── setup_financeiro.py    # Setup módulo financeiro
```

---

## 🎓 Referências

- **Catálogo Padrão:** `CATALOGO_BACKUP.md` (45 produtos)
- **Documentação Financeiro:** `modules/finance/README.md`
- **Documentação Backups:** `backups/README.md`

---

## ❓ FAQ

**Q: O backup inclui senhas/tokens?**
A: Não! Dados sensíveis devem estar no `.env`, que não é versionado.

**Q: Posso ter bancos diferentes em cada máquina?**
A: Sim! Cada máquina tem seu próprio banco. Use backup/restore quando quiser sincronizar.

**Q: O que acontece se eu não fizer backup?**
A: Cada máquina continuará independente. Sem problema, mas não haverá sincronização.

**Q: Posso editar o JSON manualmente?**
A: Sim! É texto puro. Útil para fazer ajustes ou remover dados específicos antes de restaurar.

**Q: Quanto espaço ocupa um backup?**
A: Depende dos dados. Típico:
  - Apenas catálogo (45 produtos): ~50KB
  - Com 100 licitações: ~200KB
  - Com 1000 licitações: ~2MB

---

**Última atualização:** 27 de novembro de 2025
