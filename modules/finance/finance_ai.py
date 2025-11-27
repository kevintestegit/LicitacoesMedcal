import google.generativeai as genai
from sqlalchemy import text
import pandas as pd
from modules.finance.database import get_finance_session
from modules.database.database import get_session as get_main_session, Configuracao

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
        - dt_balancete (DATE): Data da transação (YYYY-MM-DD).
        - valor (FLOAT): Valor da transação. Negativo para saídas/pagamentos, Positivo para entradas/recebimentos.
        - tipo (TEXT): Categoria da transação. Exemplos: 'Impostos', 'Ordem Bancária', 'Pix - Enviado', 'Pix - Recebido', 'Tarifa Bancária'.
        - historico (TEXT): Descrição original do banco.
        - ano_referencia (INTEGER): Ano (ex: 2025).
        - mes_referencia (TEXT): Mês (ex: 'Jan', 'Fev').
        """
        
        prompt = f"""
        Você é um especialista em SQL SQLite. Converta a pergunta do usuário em uma query SQL para responder.
        
        {schema}
        
        Regras CRITICAS:
        1. Retorne APENAS o código SQL puro.
        2. NÃO use Markdown (```sql). NÃO escreva explicações.
        3. Se a pergunta for sobre "pagamentos", "saídas" ou "gastos", lembre-se que o 'valor' no banco é negativo. Use SUM(ABS(valor)) ou filtre WHERE valor < 0.
        4. Se a pergunta for sobre "entradas", "recebimentos", lembre-se que o 'valor' é positivo.
        5. Considere 'Ordem Bancária' como Entrada/Recebimento.
        6. Use 'LIKE' para strings parciais (ex: tipo LIKE '%Imposto%').
        7. IMPORTANTE: 'SESAP' ou 'Estado' refere-se à soma das categorias: 'Recebimento SESAP', 'Hematologia', 'Coagulação', 'Ionograma'. (NÃO INCLUA 'Base' nem 'Recebimento Base Aérea').
        8. Base Aérea é apenas 'Recebimento Base Aérea'.
        
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
        return response.text
