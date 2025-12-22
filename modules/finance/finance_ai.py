import requests
from sqlalchemy import text
import pandas as pd
from modules.finance.database import get_finance_session, get_finance_historico_session
from modules.database.database import get_session as get_main_session, Configuracao
from datetime import date, datetime

class FinanceAI:
    def __init__(self, session_factory=None, fonte_nome: str = "financeiro"):
        """
        session_factory: callable que retorna uma sessão (padrão: banco financeiro ativo)
        fonte_nome: usado apenas para mensagem contextual (ativo/histórico)
        """
        self.session_factory = session_factory or get_finance_session
        self.fonte_nome = fonte_nome

        self.provider = None

        # OpenRouter-only
        self.api_key_openrouter = self._get_config_value('openrouter_api_key')
        # Modelo default (público/grátis) e sobrescrevível via Configuracao.openrouter_model
        # Use um dos modelos públicos listados em https://openrouter.ai/models (sem prefixo openrouter/)
        # Exemplo gratuito: "mistralai/mistral-7b-instruct:free"
        self.openrouter_model = self._get_config_value('openrouter_model') or "mistralai/mistral-7b-instruct:free"
        if self.api_key_openrouter:
            self.provider = 'openrouter'

    def _get_config_value(self, chave):
        session = get_main_session()
        config = session.query(Configuracao).filter_by(chave=chave).first()
        session.close()
        return config.valor if config else None

    def analisar_pergunta(self, pergunta: str):
        """
        1. Transforma linguagem natural em SQL.
        2. Executa SQL.
        3. Gera resposta explicativa.
        """
        # Heurística: consultas conhecidas (Magnus / Paulo) respondem localmente sem LLM
        pergunta_lower = pergunta.lower()
        if any(k in pergunta_lower for k in ['magnus', '7704587000169', '07704587000169']):
            return self._responder_pagador_local(
                nome="Magnus Soares",
                patterns=[
                    "%magnus%",
                    "%MAGNUS%",
                    "%7704587000169%",
                    "%07704587000169%",
                    "%PAGAMENTO PIX 07704587000169%",
                ]
            )
        if any(k in pergunta_lower for k in ['paulo sergio', 'paulo', '65427238468']):
            return self._responder_pagador_local(
                nome="Paulo Sergio Soares",
                patterns=[
                    "%paulo%",
                    "%sergio%",
                    "%PAULO SERGIO SOARES%",
                    "%PAGAMENTO PIX 654272%",
                    "%65427238468%",
                ]
            )

        if not self.provider:
            return "⚠️ Erro: IA não configurada. Adicione `openrouter_api_key` em Configurações."

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
        """Pede para o LLM criar a query SQL"""
        
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
           - Magnus Soares (pagamentos): historico LIKE '%magnus%' OU documento LIKE '%7704587000169%' OU historico LIKE '%07704587000169%' (saídas: valor < 0, somar ABS)
           - Paulo Sergio Soares (pagamentos): historico LIKE '%paulo sergio%' OU documento LIKE '%65427238468%' OU historico LIKE '%65427238468%' (saídas: valor < 0, somar ABS)

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
        
        try:
            sql_query = self._openrouter_complete(prompt)
        except Exception as e:
            raise Exception(f"Erro ao gerar SQL ({self.provider or 'sem provedor'}): {e}")
        
        # Limpeza agressiva do SQL
        sql_query = sql_query.replace('```sql', '').replace('```', '').strip()
        
        # Garante que começa com SELECT (remove lixo antes)
        if "SELECT" in sql_query.upper():
            start = sql_query.upper().find("SELECT")
            sql_query = sql_query[start:]
            
        return sql_query

    def _executar_sql(self, query: str):
        """Executa a query no banco financeiro selecionado"""
        session = self.session_factory()
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
        try:
            resp_text = self._openrouter_complete(prompt).strip()
        except Exception as e:
            return f"Erro ao gerar resposta ({self.provider or 'sem provedor'}): {e}"
        detalhes = self._format_result_table(df)
        # Acrescenta uma visão detalhada dos registros retornados para perguntas como "quais são"
        if detalhes:
            return f"{resp_text}\n\n**Detalhes (máx 50 linhas):**\n{detalhes}"
        return resp_text

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

    # ==== CONSULTA LOCAL PARA PAGADORES ESPECÍFICOS ====
    def _responder_pagador_local(self, nome: str, patterns) -> str:
        """
        Consulta local (sem LLM) para pagadores específicos (Magnus/Paulo).
        Soma saídas (valor < 0) em ABS e retorna por ano + total geral nas duas bases.
        Observação: ignora lançamentos cuja classificação/tipo pareça não ser pagamento direto (ex.: Impostos, Compra Cartão).
        """
        bases = [
            ("Financeiro Atual", get_finance_session),
            ("Financeiro Histórico", get_finance_historico_session)
        ]
        linhas = []
        total_geral = 0.0
        detalhes = []
        for label, sess_fn in bases:
            sess = sess_fn()
            # monta condição SQL
            conds = []
            params = {}
            for idx, p in enumerate(patterns):
                conds.append(f"(historico LIKE :p{idx} OR documento LIKE :p{idx} OR historico_complementar LIKE :p{idx})")
                params[f"p{idx}"] = p
            where = " OR ".join(conds)

            # Tipos a excluir (não são pagamento direto para a pessoa)
            tipos_excluir = ['Impostos', 'Compra com Cartão', 'Compra Com Cartão', 'Pagamento Boleto', 'Pagamento de Boleto']
            tipo_excluir_clause = " AND (tipo IS NULL OR tipo NOT IN (:t0, :t1, :t2, :t3, :t4))"
            params.update({ 't0': tipos_excluir[0], 't1': tipos_excluir[1], 't2': tipos_excluir[2], 't3': tipos_excluir[3], 't4': tipos_excluir[4] })
            sql = f"""
                SELECT ano_referencia, COUNT(*) as qtd,
                       SUM(CASE WHEN valor < 0 THEN ABS(valor) ELSE 0 END) as pago
                FROM extratos_bb
                WHERE ({where}) AND valor < 0 {tipo_excluir_clause}
                GROUP BY ano_referencia
                ORDER BY ano_referencia
            """
            res = sess.execute(text(sql), params).fetchall()

            # Detalhes (limitados) para exibir ao usuário
            sql_det = f"""
                SELECT dt_balancete, valor, historico, historico_complementar, fatura, observacoes
                FROM extratos_bb
                WHERE ({where}) AND valor < 0 {tipo_excluir_clause}
                ORDER BY dt_balancete DESC
                LIMIT 50
            """
            det = sess.execute(text(sql_det), params).fetchall()
            sess.close()
            if res:
                for ano, qtd, pago in res:
                    linhas.append(f"{label} {ano}: {qtd} lançamentos | Pago R$ {pago:,.2f}")
                    total_geral += pago or 0.0
            else:
                linhas.append(f"{label}: nenhum lançamento encontrado")

            if det:
                detalhes.append(f"Detalhes {label}:")
                for row in det:
                    dt, valor, hist, histc, fat, obs = row
                    comp = f"{hist or ''} {histc or ''}".strip()
                    fat_obs = fat or obs or ""
                    detalhes.append(f"- {dt} | R$ {valor:,.2f} | {comp} | {fat_obs}")

        if not linhas or total_geral == 0:
            return f"Não encontrei pagamentos para {nome} nas duas bases."
        linhas.append(f"Total geral pago para {nome}: R$ {total_geral:,.2f}")
        if detalhes:
            linhas.append("\n".join(detalhes))
        return "\n".join(linhas)

    # ==== OPENROUTER ====
    def _openrouter_complete(self, prompt: str) -> str:
        """
        Faz chamada ao OpenRouter. Requer `openrouter_api_key` configurado em Configuracao.
        """
        if not self.api_key_openrouter:
            raise Exception("API OpenRouter não configurada.")
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key_openrouter}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost",
            "X-Title": "Medcal Financeiro"
        }
        payload = {
            "model": self.openrouter_model,
            "messages": [
                {"role": "system", "content": "Você é um assistente SQL e financeiro, responda apenas o que for pedido."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1,
        }
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        try:
            resp.raise_for_status()
        except Exception:
            raise Exception(f"OpenRouter error {resp.status_code}: {resp.text}")
        data = resp.json()
        return data["choices"][0]["message"]["content"]
