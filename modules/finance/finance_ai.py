import google.generativeai as genai
from sqlalchemy import text
import pandas as pd
from modules.finance.database import get_finance_session
from modules.database.database import get_session as get_main_session, Configuracao
from datetime import date, datetime

class FinanceAI:
    def __init__(self):
        self.api_key = self._get_api_key()
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-2.0-flash')
        else:
            self.model = None

    def _get_api_key(self):
        """Busca a API Key nas configurações do banco principal"""
        session = get_main_session()
        config = session.query(Configuracao).filter_by(chave='gemini_api_key').first()
        session.close()
        return config.valor if config else None

    def analisar_pergunta(self, pergunta: str):
        """
        1. Transforma linguagem natural em SQL.
        2. Executa SQL.
        3. Gera resposta explicativa.
        """
        if not self.model:
            return "⚠️ Erro: API Key do Gemini não configurada. Vá em 'Configurações' e adicione sua chave."

        # 1. Gerar SQL
        try:
            sql_query = self._gerar_sql(pergunta)
            
            # Limpeza básica do SQL gerado pela IA (remover markdown)
            sql_query = sql_query.replace('```sql', '').replace('```', '').strip()
            
            # 2. Executar SQL
            resultado_df = self._executar_sql(sql_query)
            
            if resultado_df is None or resultado_df.empty:
                return f"Não encontrei dados para responder sua pergunta.\n\nQuery tentada: `{sql_query}`"
            
            # 3. Interpretar Resultado
            resposta_final = self._interpretar_resultado(pergunta, resultado_df, sql_query)
            return resposta_final

        except Exception as e:
            return f"Desculpe, não consegui processar essa pergunta.\nErro: {str(e)}"

    def _gerar_sql(self, pergunta: str) -> str:
        """Pede para o Gemini criar a query SQL"""
        
        schema = """
        Tabela: extratos_bb
        Colunas:
        - id (INTEGER): ID único do lançamento
        - status (TEXT): Status do lançamento. Valores: 'Baixado' ou 'Pendente'
        - dt_balancete (DATE): Data da transação (YYYY-MM-DD)
        - valor (FLOAT): Valor da transação. NEGATIVO para saídas/pagamentos, POSITIVO para entradas/recebimentos
        - tipo (TEXT): Categoria da transação. Valores comuns:
          * Entradas: 'Ordem Bancária', 'Recebimento SESAP', 'Hematologia', 'Coagulação', 'Ionograma', 'Recebimento Base Aérea', 'Pix - Recebido', 'Transferência Recebida'
          * Saídas: 'Impostos', 'Pix - Enviado', 'Pagamento Boleto', 'Pagamento Fornecedor', 'Tarifa Bancária', 'Compra com Cartão'
        - historico (TEXT): Descrição original do banco (ex: "632 Ordem Bancária - SESAP")
        - documento (TEXT): Número do documento
        - fatura (TEXT): Fatura ou observação
        - ano_referencia (INTEGER): Ano (ex: 2025)
        - mes_referencia (TEXT): Mês abreviado (ex: 'Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez')
        """

        prompt = f"""
        Você é um especialista em SQL SQLite. Converta a pergunta do usuário em uma query SQL para responder.

        {schema}

        Regras CRÍTICAS:
        1. Retorne APENAS o código SQL puro, sem markdown ou explicações
        2. NÃO use ```sql ou ``` - apenas SQL puro

        3. VALORES MONETÁRIOS:
           - Saídas/Pagamentos/Gastos: valor < 0 (negativo). Use SUM(ABS(valor)) para somar
           - Entradas/Recebimentos: valor > 0 (positivo). Use SUM(valor) direto
           - Para calcular totais gerais: SUM(valor) mostra o líquido

        4. CATEGORIAS ESPECIAIS:
           - SESAP/Estado: agrupe (tipo IN ('Recebimento SESAP', 'Hematologia', 'Coagulação', 'Coagulacao', 'Ionograma', 'Ordem Bancária'))
           - Impostos: tipo LIKE '%Imposto%' OU tipo = 'Impostos'
           - Base Aérea: tipo = 'Recebimento Base Aérea' OU tipo LIKE '%Base%'

        5. STATUS:
           - Para contar baixados: COUNT(*) WHERE status = 'Baixado'
           - Para contar pendentes: COUNT(*) WHERE status = 'Pendente'
           - Para comparar: GROUP BY status

        6. AGRUPAMENTO POR PERÍODO:
           - Por mês: GROUP BY mes_referencia, ano_referencia ORDER BY ano_referencia DESC,
             CASE mes_referencia
               WHEN 'Jan' THEN 1 WHEN 'Fev' THEN 2 WHEN 'Mar' THEN 3 WHEN 'Abr' THEN 4
               WHEN 'Mai' THEN 5 WHEN 'Jun' THEN 6 WHEN 'Jul' THEN 7 WHEN 'Ago' THEN 8
               WHEN 'Set' THEN 9 WHEN 'Out' THEN 10 WHEN 'Nov' THEN 11 WHEN 'Dez' THEN 12
             END DESC
           - Por ano: GROUP BY ano_referencia ORDER BY ano_referencia DESC

        7. EXEMPLOS DE PERGUNTAS COMUNS:
           - "Quanto a SESAP pagou em [mês/ano]?" → WHERE tipo IN (...) AND mes_referencia = 'Mês' AND ano_referencia = Ano
           - "Quantos estão baixados/pendentes?" → SELECT status, COUNT(*) FROM extratos_bb GROUP BY status
           - "Quanto foi pago de imposto em [mês]?" → WHERE tipo LIKE '%Imposto%' AND valor < 0 AND mes_referencia = 'Mês'

        Pergunta do Usuário: "{pergunta}"
        SQL:
        """
        
        response = self.model.generate_content(prompt)
        
        # Limpeza agressiva do SQL
        sql_query = response.text.replace('```sql', '').replace('```', '').strip()
        
        # Garante que começa com SELECT (remove lixo antes)
        if "SELECT" in sql_query.upper():
            start = sql_query.upper().find("SELECT")
            sql_query = sql_query[start:]
            
        return sql_query

    def _executar_sql(self, query: str):
        """Executa a query no banco financeiro"""
        session = get_finance_session()
        try:
            # Segurança básica: impedir comandos de modificação
            if any(cmd in query.upper() for cmd in ['DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER']):
                raise Exception("Comandos de modificação não permitidos.")
                
            result = session.execute(text(query))
            df = pd.DataFrame(result.fetchall(), columns=result.keys())
            session.close()
            return df
        except Exception as e:
            session.close()
            raise e

    def _interpretar_resultado(self, pergunta: str, df: pd.DataFrame, query: str) -> str:
        """Pede para a IA transformar o dataframe em texto amigável"""
        dados_str = df.to_string()
        
        prompt = f"""
        Pergunta do usuário: "{pergunta}"
        Query SQL executada: "{query}"
        Resultado do banco de dados:
        {dados_str}
        
        Com base nesse resultado, responda a pergunta do usuário de forma direta, amigável e em Português (Brasil).
        Se for um valor monetário, formate como R$ X,XX.
        """
        
        response = self.model.generate_content(prompt)
        detalhes = self._format_result_table(df)
        # Acrescenta uma visão detalhada dos registros retornados para perguntas como "quais são"
        if detalhes:
            return f"{response.text.strip()}\n\n**Detalhes (máx 50 linhas):**\n{detalhes}"
        return response.text

    def _format_result_table(self, df: pd.DataFrame, max_rows: int = 50) -> str:
        """Formata o dataframe em lista amigável e segura para exibir diretamente."""
        if df is None or df.empty:
            return ""

        # Seleciona colunas mais úteis se existirem
        colunas_prioridade = ['dt_balancete', 'status', 'tipo', 'historico', 'valor', 'mes_referencia', 'ano_referencia']
        colunas_presentes = [c for c in colunas_prioridade if c in df.columns]
        if not colunas_presentes:
            # Se o schema for diferente, mostra tudo mas limitando linhas
            colunas_presentes = list(df.columns)

        linhas = []
        for _, row in df.head(max_rows).iterrows():
            valores = []
            for col in colunas_presentes:
                valores.append(self._format_cell(col, row.get(col)))
            linhas.append("- " + " | ".join(valores))

        if len(df) > max_rows:
            linhas.append(f"... (+{len(df) - max_rows} linhas ocultas)")
        return "\n".join(linhas)

    def _format_cell(self, coluna: str, valor):
        """Formata células com cuidado para datas e valores monetários."""
        if valor is None or (isinstance(valor, float) and pd.isna(valor)):
            return "-"
        if coluna == 'valor' and isinstance(valor, (int, float)):
            return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        if isinstance(valor, (date, datetime)):
            return valor.strftime("%d/%m/%Y")
        return str(valor)
