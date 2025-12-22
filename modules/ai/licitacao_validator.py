"""
Módulo de Validação de Licitações com IA (OpenRouter)

Este módulo usa IA para validar se uma licitação é realmente relevante
para a Medcal Farma, evitando falsos positivos causados por matches genéricos.
"""

import json
from .ai_config import get_model


# Contexto da empresa para o prompt
CONTEXTO_MEDCAL = """
A MEDCAL FARMA é uma empresa que atua no segmento de ANÁLISES CLÍNICAS LABORATORIAIS.

O QUE A MEDCAL VENDE/FORNECE:
1. EQUIPAMENTOS de laboratório em regime de LOCAÇÃO/COMODATO:
   - Analisadores Hematológicos (hemograma, contagem de células)
   - Analisadores Bioquímicos (glicose, colesterol, enzimas)
   - Analisadores de Coagulação (TP, TTPA, fibrinogênio)
   - Analisadores de Imunologia/Hormônios (TSH, T4, PSA)
   - Analisadores de Ionograma/Eletrólitos (sódio, potássio, cálcio)
   - Analisadores de Gasometria/POCT (pH, pCO2, pO2)
   - Analisadores de Urina

2. REAGENTES E INSUMOS para esses equipamentos:
   - Reagentes para hematologia, bioquímica, coagulação, etc.
   - Calibradores e controles de qualidade
   - Diluentes, lisantes, soluções

3. CONSUMÍVEIS LABORATORIAIS:
   - Tubos de coleta de sangue (EDTA, heparina, citrato)
   - Ponteiras, lâminas, lancetas
   - Luvas, máscaras (para uso laboratorial)

4. MANUTENÇÃO PREVENTIVA E CORRETIVA dos equipamentos fornecidos

O QUE A MEDCAL NÃO VENDE:
- Medicamentos, remédios, fármacos
- Equipamentos de imagem (raio-x, ultrassom, tomografia)
- Equipamentos cirúrgicos
- Material odontológico
- Mobiliário hospitalar (camas, macas, cadeiras)
- Equipamentos de fisioterapia
- Enxoval hospitalar (lençóis, cobertores)
- Material de limpeza
- Alimentos, suplementos
- Qualquer coisa fora do escopo de ANÁLISES CLÍNICAS LABORATORIAIS
"""


def validar_licitacao_com_ia(objeto: str, itens: list) -> dict:
    """
    Usa IA (OpenRouter) para validar se uma licitação é relevante para a Medcal.
    
    Args:
        objeto: Texto do objeto da licitação
        itens: Lista de dicts com os itens {'descricao': str, 'quantidade': float, ...}
    
    Returns:
        dict com:
        - relevante: bool (True se é relevante para Medcal)
        - confianca: int (0-100, confiança da avaliação)
        - motivo: str (explicação curta)
        - itens_relevantes: list (descrições dos itens que são do escopo Medcal)
        - itens_irrelevantes: list (descrições dos itens FORA do escopo)
        - erro: str (se houve erro na análise)
    """
    
    resultado_padrao = {
        "relevante": False,
        "confianca": 0,
        "motivo": "Não analisado",
        "itens_relevantes": [],
        "itens_irrelevantes": [],
        "erro": None
    }
    
    try:
        model = get_model(temperature=0.1)  # Baixa temperatura para respostas consistentes
        
        # Monta texto dos itens
        if itens:
            itens_texto = "\n".join([
                f"- {i.get('descricao', 'Sem descrição')}" 
                for i in itens[:30]  # Limita a 30 itens para não estourar contexto
            ])
            if len(itens) > 30:
                itens_texto += f"\n... e mais {len(itens) - 30} itens."
        else:
            itens_texto = "(Nenhum item detalhado disponível)"
        
        prompt = f"""
{CONTEXTO_MEDCAL}

---

TAREFA: Analise a licitação abaixo e determine se é RELEVANTE para a Medcal Farma participar.

OBJETO DA LICITAÇÃO:
{objeto}

ITENS DA LICITAÇÃO:
{itens_texto}

---

INSTRUÇÕES:
1. Analise se o OBJETO e os ITENS são do escopo de atuação da Medcal
2. Uma licitação é RELEVANTE se pelo menos 50% dos itens forem do escopo Medcal
3. Ignore itens genéricos como "Reagente para diagnóstico" sem especificação - considere IRRELEVANTE
4. Licitações que mencionam "gasometria" ou "hematologia" apenas como SETOR/LOCAL (não como equipamento/reagente) são IRRELEVANTES

RESPONDA APENAS COM JSON VÁLIDO no formato:
{{
    "relevante": true ou false,
    "confianca": número de 0 a 100,
    "motivo": "explicação curta de 1-2 frases",
    "itens_relevantes": ["item 1", "item 2"],
    "itens_irrelevantes": ["item x", "item y"]
}}
"""
        
        response = model.generate_content(prompt)
        resposta_texto = response.text.strip()
        
        # Limpa possíveis marcadores de código
        if resposta_texto.startswith("```"):
            resposta_texto = resposta_texto.split("```")[1]
            if resposta_texto.startswith("json"):
                resposta_texto = resposta_texto[4:]
        resposta_texto = resposta_texto.strip()
        
        # Tenta extrair JSON
        try:
            dados = json.loads(resposta_texto)
            return {
                "relevante": dados.get("relevante", False),
                "confianca": dados.get("confianca", 50),
                "motivo": dados.get("motivo", "Análise concluída"),
                "itens_relevantes": dados.get("itens_relevantes", []),
                "itens_irrelevantes": dados.get("itens_irrelevantes", []),
                "erro": None
            }
        except json.JSONDecodeError:
            # Se não conseguiu parsear JSON, tenta extrair informação básica
            texto_lower = resposta_texto.lower()
            relevante = "true" in texto_lower and "relevante" in texto_lower
            return {
                "relevante": relevante,
                "confianca": 30,
                "motivo": "Resposta não estruturada da IA",
                "itens_relevantes": [],
                "itens_irrelevantes": [],
                "erro": "JSON inválido na resposta"
            }
            
    except Exception as e:
        resultado_padrao["erro"] = str(e)
        return resultado_padrao


def validar_licitacao_rapido(objeto: str, itens: list) -> tuple:
    """
    Versão rápida que retorna apenas (relevante: bool, motivo: str).
    Útil para filtros em massa.
    """
    resultado = validar_licitacao_com_ia(objeto, itens)
    return resultado["relevante"], resultado["motivo"]


def calcular_score_ia(objeto: str, itens: list) -> int:
    """
    Calcula um score de 0-100 baseado na análise da IA.
    
    Score alto = Muito relevante para Medcal
    Score baixo = Pouco ou nada relevante
    """
    resultado = validar_licitacao_com_ia(objeto, itens)
    
    if resultado["erro"]:
        return 0
    
    if not resultado["relevante"]:
        return 0
    
    # Base: confiança da IA
    score = resultado["confianca"]
    
    # Bonus por quantidade de itens relevantes
    qtd_relevantes = len(resultado["itens_relevantes"])
    qtd_irrelevantes = len(resultado["itens_irrelevantes"])
    
    if qtd_relevantes > 0:
        proporcao = qtd_relevantes / (qtd_relevantes + qtd_irrelevantes + 0.1)
        score = int(score * (0.5 + proporcao * 0.5))  # Ajusta pela proporção
    
    return min(100, max(0, score))
