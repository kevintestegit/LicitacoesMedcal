# 💰 Módulo de Gestão Financeira

Sistema completo de gestão financeira com auditoria automática de extratos bancários e conciliação inteligente de faturas.

## 🎯 Funcionalidades

### 1. **Gestão de Contas Bancárias**
- Cadastro de múltiplas contas bancárias
- Controle de saldo
- Ativação/desativação de contas
- Organização por banco, agência e conta

### 2. **Upload e Parsing de Extratos**
- **Formatos suportados:**
  - CSV (vários encodings)
  - Excel (.xlsx, .xls)
  - OFX (Open Financial Exchange)
- **Parser inteligente** que detecta automaticamente colunas
- **Prevenção de duplicatas** usando hash único
- **Categorização automática** de lançamentos

### 3. **Gestão de Faturas**
- Cadastro de faturas a pagar e a receber
- Controle de vencimentos
- Alertas de faturas vencidas
- Status: PENDENTE, PAGA, VENCIDA, PARCIAL
- Múltiplas formas de pagamento

### 4. **Conciliação Automática (Auditoria)**
- **Matching inteligente** usando fuzzy matching
- **Score de confiabilidade** (0-100%)
- Critérios de matching:
  - Valor (40% do score)
  - Data (30% do score)
  - Descrição/Fornecedor (30% do score)
- **Conciliação automática** para matches > 85%
- **Sugestões** para matches entre 70-85%
- **Conciliação manual** com interface intuitiva

### 5. **Dashboard Financeiro**
- Visão geral de contas ativas
- Total de faturas pendentes e vencidas
- Próximos vencimentos (15 dias)
- Alertas visuais com código de cores
- Histórico de conciliações

## 📊 Estrutura de Dados

### Tabelas do Banco de Dados

#### `contas_bancarias`
- Cadastro de contas da empresa
- Controle de saldo atual
- Status ativo/inativo

#### `extratos_bancarios`
- Lançamentos importados dos extratos
- Categorização automática
- Flag de conciliação
- Hash único para evitar duplicatas

#### `faturas`
- Faturas a pagar/receber
- Datas de emissão, vencimento e pagamento
- Controle de valor pago vs. valor original
- Status e forma de pagamento

#### `conciliacoes`
- Relacionamento entre extratos e faturas
- Score de matching
- Tipo (AUTO ou MANUAL)
- Auditoria de quem e quando conciliou

## 🚀 Como Usar

### 1. Cadastrar Contas Bancárias
1. Acesse **💰 Gestão Financeira** → **🏦 Contas**
2. Clique em "➕ Adicionar Nova Conta"
3. Preencha banco, agência, conta e saldo inicial

### 2. Importar Extratos
1. Vá para a aba **📤 Extratos**
2. Selecione a conta bancária
3. Faça upload do arquivo (CSV, Excel ou OFX)
4. Revise a pré-visualização
5. Confirme a importação

### 3. Cadastrar Faturas
1. Acesse a aba **📄 Faturas**
2. Clique em "➕ Adicionar Nova Fatura"
3. Preencha:
   - Tipo (PAGAR ou RECEBER)
   - Fornecedor/Cliente
   - Valor e datas
   - Forma de pagamento

### 4. Fazer Auditoria (Conciliação)
1. Vá para **🔍 Conciliação**
2. Clique em **"🤖 Executar Conciliação Automática"**
   - O sistema encontrará matches automáticos
3. Para conciliação manual:
   - Selecione um extrato pendente
   - Veja as sugestões de faturas
   - Clique em "✅ Conciliar"

## 🧠 Algoritmo de Matching

O sistema usa um algoritmo de 3 camadas:

### Camada 1: Análise de Valor (40 pontos)
- Compara valor do extrato vs. valor da fatura
- Tolerância de 2% para pequenas diferenças (taxas, IOF, etc.)

### Camada 2: Análise de Data (30 pontos)
- Compara data do lançamento com data de vencimento/pagamento
- Tolerância de 5 dias

### Camada 3: Análise Textual (30 pontos)
- Fuzzy matching entre:
  - Descrição do extrato ↔ Nome do fornecedor
  - Descrição do extrato ↔ Descrição da fatura
- Usa biblioteca `rapidfuzz` para matching parcial

### Classificação Final
- **Score ≥ 85%**: Conciliação AUTOMÁTICA
- **70% ≤ Score < 85%**: SUGESTÃO (requer confirmação manual)
- **Score < 70%**: Sem match

## 📁 Estrutura de Arquivos

```
modules/finance/
├── __init__.py              # Exportações do módulo
├── bank_models.py           # Modelos SQLAlchemy
├── extrato_parser.py        # Parser de arquivos
├── conciliador.py           # Lógica de conciliação
└── README.md                # Esta documentação
```

## 🎨 Interface

A interface foi projetada com foco em:
- **Simplicidade**: Tudo em 5 abas organizadas
- **Visual**: Cards coloridos por status
- **Indicadores**: Métricas e alertas visuais
- **Automação**: Menos cliques, mais resultados

## 🔐 Segurança

- **Hash único** para cada lançamento (previne duplicatas)
- **Auditoria completa** (quem e quando conciliou)
- **Reversibilidade**: Todas as conciliações podem ser desfeitas
- **Validação**: Campos obrigatórios e regras de negócio

## 📝 Próximas Melhorias Sugeridas

- [ ] Exportação de relatórios para Excel/PDF
- [ ] Gráficos de fluxo de caixa
- [ ] Projeções financeiras
- [ ] Integração com APIs bancárias (Open Banking)
- [ ] Regras personalizadas de matching
- [ ] Machine Learning para melhorar matching automático
- [ ] Categorização avançada com IA

## 🛠️ Dependências

```python
pandas>=2.0.0
rapidfuzz>=3.0.0
sqlalchemy>=2.0.0
streamlit>=1.28.0
openpyxl>=3.1.0  # Para Excel
ofxparse>=0.21   # Para OFX (opcional)
```

## 📞 Suporte

Para dúvidas ou sugestões, entre em contato com a equipe de desenvolvimento.

---

**Desenvolvido com ❤️ para Medcal Gestão**
