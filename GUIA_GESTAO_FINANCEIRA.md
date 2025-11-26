# 💰 Guia de Uso - Gestão Financeira

## 🎯 O que é este módulo?

O módulo de **Gestão Financeira** permite que você:
1. **Importe extratos bancários** de qualquer banco (CSV, Excel, OFX)
2. **Cadastre faturas** a pagar e a receber
3. **Faça auditoria automática** encontrando quais faturas foram pagas
4. **Controle vencimentos** e receba alertas

## 🚀 Início Rápido (5 minutos)

### Passo 1: Cadastrar uma Conta Bancária
1. Abra o sistema: `streamlit run dashboard.py`
2. No menu lateral, clique em **💰 Gestão Financeira**
3. Vá na aba **🏦 Contas**
4. Clique em "➕ Adicionar Nova Conta"
5. Preencha:
   - **Banco**: Ex: "Banco do Brasil"
   - **Agência**: Ex: "1234-5"
   - **Conta**: Ex: "98765-4"
   - **Nome Amigável**: Ex: "Conta Principal"

### Passo 2: Importar um Extrato
1. Vá na aba **📤 Extratos**
2. Selecione a conta que você acabou de criar
3. Clique em "Browse files" e selecione seu extrato
   - **Formatos aceitos**: CSV, Excel (.xlsx), OFX
   - Tem um exemplo em: `data/exemplo_extrato.csv`
4. Revise a pré-visualização
5. Clique em **"✅ Confirmar e Importar"**

### Passo 3: Cadastrar Faturas
1. Vá na aba **📄 Faturas**
2. Clique em "➕ Adicionar Nova Fatura"
3. Preencha:
   - **Tipo**: PAGAR ou RECEBER
   - **Fornecedor**: Nome da empresa
   - **Descrição**: Ex: "Nota Fiscal 1234"
   - **Valor**: Valor total da fatura
   - **Vencimento**: Data de vencimento

**Dica**: Cadastre as faturas que você espera ver no extrato!

### Passo 4: Fazer a Auditoria (Conciliação)
1. Vá na aba **🔍 Conciliação**
2. Clique no botão **"🤖 Executar Conciliação Automática"**
3. O sistema vai:
   - Comparar cada lançamento do extrato com suas faturas
   - Fazer matching por valor, data e descrição
   - Conciliar automaticamente os matches fortes (score > 85%)
   - Sugerir matches fracos para você revisar

4. Veja os resultados:
   - **Conciliados**: Faturas encontradas automaticamente ✅
   - **Sugestões**: Matches que precisam de confirmação
   - **Sem Match**: Lançamentos sem correspondência

## 📊 Exemplo Prático

Imagine que você tem:
- **Extrato bancário** com: "PAGTO FORNECEDOR ABC LTDA - R$ 1.500,50"
- **Fatura cadastrada**: Fornecedor "ABC Materiais Ltda" - R$ 1.500,00

O sistema vai:
1. Comparar valores: 1.500,50 vs 1.500,00 ✅ (diferença < 2%)
2. Comparar datas: 01/01 (extrato) vs 31/12 (vencimento) ✅ (diferença < 5 dias)
3. Comparar textos: "ABC LTDA" vs "ABC Materiais" ✅ (fuzzy match > 70%)
4. **Score final**: 92% → **Conciliação automática!** 🎉

## 🎨 Entendendo o Dashboard

### Aba 📊 Dashboard
- **Visão geral** de tudo
- **Faturas vencidas** em vermelho 🔴
- **Próximos vencimentos** (15 dias)
- **Extratos pendentes** de conciliação

### Aba 🏦 Contas
- Cadastro de todas as suas contas bancárias
- Saldo atual de cada conta
- Ativar/desativar contas

### Aba 📤 Extratos
- Upload de arquivos de extrato
- Visualização dos lançamentos importados
- Filtro por conta

### Aba 📄 Faturas
- Cadastro de faturas a pagar/receber
- Filtros por:
  - Tipo (PAGAR/RECEBER)
  - Status (PENDENTE/PAGA/VENCIDA)
  - Busca por fornecedor

### Aba 🔍 Conciliação
- **Botão mágico** de conciliação automática
- Conciliação manual com sugestões
- Histórico de todas as conciliações
- Opção de desfazer conciliações

## 📁 Formatos de Arquivo Aceitos

### CSV (Recomendado para começar)
Colunas necessárias:
- `Data` ou `Data_Lancamento`
- `Descricao` ou `Historico`
- `Valor` OU (`Credito` + `Debito`)

Opcional:
- `Tipo`, `Documento`

**Exemplo de CSV:**
```csv
Data,Descricao,Valor,Tipo
01/01/2025,PAGTO FORNECEDOR ABC,-1500.50,DEBITO
02/01/2025,RECEBIMENTO CLIENTE XYZ,3200.00,CREDITO
```

### Excel (.xlsx)
Mesma estrutura do CSV, mas em formato Excel.

### OFX (Banco)
Formato padrão dos bancos brasileiros.
- Baixe direto do internet banking
- Upload direto no sistema

## 🧠 Como Funciona o Matching Automático?

O sistema analisa 3 coisas:

### 1️⃣ Valor (40% do score)
- Valores exatamente iguais = 100 pontos
- Diferença até 2% = 100 pontos (aceita pequenas taxas)
- Diferença até 10% = 70 pontos
- Diferença > 30% = 0 pontos

### 2️⃣ Data (30% do score)
- Mesma data = 100 pontos
- Diferença de 1 dia = 90 pontos
- Diferença até 5 dias = 80 pontos
- Diferença > 30 dias = 0 pontos

### 3️⃣ Descrição (30% do score)
- Usa **fuzzy matching** (texto similar)
- Compara:
  - Descrição do extrato ↔ Nome do fornecedor
  - Descrição do extrato ↔ Descrição da fatura
- Ignora acentos, maiúsculas e pontuação

**Score Final:**
- ≥ 85% = Conciliação AUTOMÁTICA ✅
- 70-84% = SUGESTÃO (você confirma) ⚠️
- < 70% = SEM MATCH ❌

## 💡 Dicas e Boas Práticas

### ✅ FAÇA
- **Cadastre faturas antes** de importar extratos
- Use **nomes consistentes** para fornecedores
- Importe extratos **mensalmente**
- Revise **sugestões de match** manualmente
- Use a **conciliação automática** primeiro

### ❌ EVITE
- Cadastrar faturas com valores zerados
- Usar nomes muito diferentes (Ex: "ABC" vs "Fornecedor XYZ")
- Importar o mesmo extrato duas vezes (há proteção, mas evite)
- Ignorar alertas de faturas vencidas

## 🔧 Conciliação Manual

Se o sistema não encontrou um match automático:

1. Na aba **🔍 Conciliação**
2. Selecione o **extrato pendente** na lista
3. Veja as **sugestões** (se houver)
4. Clique em **"✅ Conciliar"** na fatura correta
5. Pronto! A conciliação é salva

## 📈 Relatórios e Indicadores

### Dashboard Principal
- **Faturas Pendentes**: Quanto você ainda deve pagar
- **Faturas Vencidas**: Atenção! Atraso no pagamento
- **Extratos Pendentes**: Lançamentos não conciliados

### Próximos Vencimentos
- Código de cores:
  - 🟢 Verde: Vence em mais de 7 dias
  - 🟡 Amarelo: Vence em 3-7 dias
  - 🔴 Vermelho: Vence em 0-3 dias

## 🆘 Resolução de Problemas

### "Nenhuma sugestão encontrada"
**Possíveis causas:**
- Fatura não cadastrada
- Diferença de valor muito grande
- Nomes muito diferentes
- Diferença de data muito grande

**Solução:**
- Verifique se a fatura está cadastrada
- Faça conciliação manual

### "Arquivo não suportado"
**Solução:**
- Certifique-se que o arquivo é CSV, Excel ou OFX
- Tente exportar novamente do banco

### "Erro ao processar arquivo"
**Possíveis causas:**
- Arquivo corrompido
- Colunas com nomes não reconhecidos

**Solução:**
- Abra o arquivo e verifique se há dados
- Renomeie as colunas para: Data, Descricao, Valor

## 📞 Suporte

Dúvidas? Entre em contato com a equipe de TI.

---

**Desenvolvido para Medcal Gestão** 🏥
**Versão 1.0** - Janeiro 2025
