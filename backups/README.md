# 🔄 Sistema de Backup e Sincronização

Esta pasta contém backups do banco de dados em formato JSON para sincronização entre máquinas.

## 📁 Estrutura

```
backups/
├── README.md                        # Este arquivo
├── backup_medcal_latest.json        # Último backup (versionado no Git)
└── backup_medcal_YYYYMMDD_HHMMSS.json  # Backups com timestamp (não versionados)
```

## 🔄 Como Funciona

### 1️⃣ Fazer Backup (Máquina de Origem)

```bash
python scripts/backup_db.py
```

Este comando:
- Exporta todos os dados do banco (produtos, licitações, configurações)
- Cria dois arquivos:
  - `backup_medcal_YYYYMMDD_HHMMSS.json` (com timestamp)
  - `backup_medcal_latest.json` (sempre atualizado)

### 2️⃣ Enviar para GitHub

```bash
git add backups/backup_medcal_latest.json
git commit -m "Atualiza backup do catálogo"
git push
```

**Importante:** Apenas o `backup_medcal_latest.json` é versionado!

### 3️⃣ Baixar em Outra Máquina

```bash
git pull
```

### 4️⃣ Restaurar Backup (Máquina de Destino)

```bash
# Restaurar o último backup
python scripts/restore_db.py

# Ou especificar um backup específico
python scripts/restore_db.py backups/backup_medcal_20250127_153000.json
```

## ⚙️ Opções de Restauração

O script perguntará se quer:
- **Substituir**: Remove todos os dados atuais e importa o backup
- **Adicionar**: Mantém dados existentes e adiciona os novos

## 📊 O Que é Incluído no Backup

- ✅ **Produtos** (Catálogo completo)
- ✅ **Configurações** (API keys, WhatsApp, termos de busca)
- ✅ **Licitações** (Histórico de licitações capturadas)
- ✅ **Itens de Licitação** (Match de produtos)

## 🔒 Segurança

- Os arquivos `.db` **NUNCA** são versionados no Git
- Apenas o backup JSON `backup_medcal_latest.json` vai para o repositório
- Valores sensíveis (senhas, tokens) devem estar no `.env`, não no backup

## 💡 Casos de Uso

### Sincronizar Catálogo entre Máquinas

```bash
# Máquina 1: Exportar
python scripts/backup_db.py
git add backups/backup_medcal_latest.json
git commit -m "Atualiza catálogo"
git push

# Máquina 2: Importar
git pull
python scripts/restore_db.py
```

### Backup Local Completo

```bash
# Faz backup com timestamp
python scripts/backup_db.py

# Arquivos ficam em backups/ com data/hora
# Exemplo: backup_medcal_20250127_153045.json
```

### Restaurar Apenas Catálogo (Sem Licitações)

Use o script específico:
```bash
python scripts/restore_catalogo.py
```

## 🗂️ Versionamento

**O que VAI para o GitHub:**
- ✅ `backup_medcal_latest.json` (sempre o mais recente)

**O que NÃO vai:**
- ❌ `backup_medcal_*_*.json` (backups com timestamp)
- ❌ `*.db` (bancos de dados SQLite)

---

**Última atualização:** 27 de novembro de 2025
