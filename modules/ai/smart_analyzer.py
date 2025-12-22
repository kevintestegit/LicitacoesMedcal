import json
import logging
from .ai_config import get_model

class SmartAnalyzer:
    def __init__(self):
        self.model = get_model(temperature=0.1) # Low temperature for factual extraction

    def analisar_viabilidade(self, texto_edital: str) -> dict:
        """
        Analisa o texto do edital e retorna um dicionário com a análise de viabilidade.
        """
        if not texto_edital or len(texto_edital) < 100:
            return {"erro": "Texto insuficiente para análise."}

        # Truncate text
        texto_processar = texto_edital[:100000] 
        
        # Fetch Company Context (Products)
        from modules.database.database import get_session, Produto
        session = get_session()
        produtos = session.query(Produto).all()
        lista_produtos = ", ".join([p.nome for p in produtos])
        session.close()
        
        if not lista_produtos:
            lista_produtos = "Equipamentos automatizados, Reagentes, Materiais Hospitalares, Insumos hospitalares, Analises Clínicas, Equipamentos de laboratório"

        prompt = f"""
        Você é um especialista em licitações públicas focado na empresa 'Medcal Farma'.
        
        CONTEXTO DA EMPRESA:
        A Medcal é uma distribuidora de insumos e materiais para analises clinicas que vende EXCLUSIVAMENTE os seguintes produtos/categorias:
        [{lista_produtos}]
        
        Se o objeto da licitação NÃO tiver relação direta com esses produtos, o Score de Viabilidade deve ser BAIXO (menor que 30) e você deve alertar que "Não é compatível com o portfólio".
        
        IMPORTANTE: A empresa NÃO vende MEDICAMENTOS (comprimidos, xaropes, injetáveis, antibióticos, etc). Se o edital for para aquisição de remédios, o Score deve ser 0.
        
        Analise o seguinte texto de um edital/aviso de licitação:
        
        TEXTO DO EDITAL:
        {texto_processar}
        
        Sua análise deve ser CRÍTICA.
        Retorne APENAS um JSON válido com a seguinte estrutura:
        {{
            "resumo_objeto": "Resumo conciso do que está sendo licitado em 1 frase",
            "score_viabilidade": 0 a 100 (Se não for compatível com o portfólio, dê nota baixa!),
            "justificativa_score": "Explicação do score (cite se é compatível ou não com os produtos da Medcal)",
            "pontos_atencao": ["Lista de cláusulas perigosas", "Exigências incomuns", "Prazos apertados"],
            "documentos_habilitacao": ["Lista provável de docs exigidos baseada no texto"],
            "red_flags": ["Fatores impeditivos graves"],
            "produtos_principais": ["Lista resumida dos principais itens/grupos"]
        }}
        """

        try:
            response = self.model.generate_content(prompt)
            raw_text = response.text.strip()
            
            # Clean up potential markdown formatting
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]
            
            return json.loads(raw_text)

        except Exception as e:
            logging.error(f"Erro na análise de IA: {e}")
            print(f"⚠️ Falha na IA ({e}). Tentando análise local...")
            return self._analise_local(texto_processar, lista_produtos)

    def _analise_local(self, texto: str, keywords_str: str) -> dict:
        """
        Análise heurística local (sem IA) baseada em palavras-chave.
        Funciona offline e sem custos.
        """
        texto_upper = texto.upper()
        keywords = [k.strip().upper() for k in keywords_str.split(',')]
        
        # 1. Contagem de Matches
        matches = []
        score = 0
        
        for kw in keywords:
            if kw in texto_upper:
                matches.append(kw)
        
        # 2. Cálculo do Score (Simples)
        # Se tiver pelo menos 1 match forte, já dá 50 pontos. Mais matches aumentam.
        if matches:
            score = 50 + (len(matches) * 10)
            score = min(95, score) # Teto de 95
        else:
            score = 0
            
        # 3. Red Flags (Medicamentos)
        red_flags = []
        termos_proibidos = ["COMPRIMIDO", "XAROPE", "INJETAVEL", "MEDICAMENTO", "FARMACIA BASICA", "REMEDIO"]
        for termo in termos_proibidos:
            if termo in texto_upper:
                score = 0
                red_flags.append(f"Possível medicamento detectado: {termo}")
                break
                
        # 4. Resumo
        if score > 0:
            resumo = f"Análise Local (Sem IA): Encontrados {len(matches)} termos compatíveis com seu catálogo ({', '.join(matches[:3])}...)."
            justificativa = "Compatibilidade identificada por palavras-chave do catálogo."
        else:
            resumo = "Análise Local (Sem IA): Nenhum termo do seu catálogo foi encontrado neste edital."
            justificativa = "Não foram encontrados seus produtos no texto."

        return {
            "resumo_objeto": resumo,
            "score_viabilidade": score,
            "justificativa_score": justificativa,
            "pontos_atencao": ["Análise gerada localmente (Keywords) devido a falha na API."],
            "documentos_habilitacao": ["Verificar edital manualmente."],
            "red_flags": red_flags,
            "produtos_principais": matches
        }
