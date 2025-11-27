# 📚 Documentação de Regras de Negócio - Financeiro

## 1. Ordem Bancária (Cód. 632)
- **Definição:** Pagamentos recebidos do Estado (Receita/Entrada).
- **Identificação:** O extrato mostra apenas "632 Ordem Bancária" e o número do documento/fatura.
- **Categorização (Tipo):** 
  - O tipo **NÃO** pode ser definido apenas pelo extrato.
  - O usuário verifica o número da Fatura/Ordem no sistema interno **Cronos**.
  - Com base no Cronos, o usuário define se é:
    - `Hematologia`
    - `Coagulação`
    - `Ionograma`
    - `Base`
    - Outros produtos...

## 2. Regras de Importação
- **Prioridade:** Se a coluna "Tipo" da planilha importada estiver preenchida (ex: "Hematologia"), o sistema **DEVE** respeitar e manter esse valor.
- **Inferência:** O sistema só deve tentar adivinhar o tipo se a coluna estiver vazia.

## 3. Regras de Sinal (Entrada vs Saída)
- **Entradas (Valor Positivo):**
  - Ordem Bancária (632)
  - Pix Recebidos (821)
  - Transferências Recebidas
  - Categorias de produtos: Hematologia, Coagulação, Ionograma, Base.
- **Saídas (Valor Negativo):**
  - Pagamentos (Boletos, Títulos, Fornecedores)
  - Pix Enviados
  - Compras com Cartão
  - Impostos/Tributos
  - Tarifas
- **Neutros (Ignorar na Soma):**
  - BB Rende Fácil
  - Aplicação Financeira
  - Resgate Investimento
