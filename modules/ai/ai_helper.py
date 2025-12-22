from .ai_config import get_model

def summarize_bidding(licitacao_obj, itens_list):
    """
    Gera um resumo estratégico da licitação usando IA (OpenRouter).
    """
    try:
        model = get_model(temperature=0.3)
        
        # Prepara o prompt
        itens_text = "\n".join([f"- {i.descricao} ({i.quantidade} {i.unidade})" for i in itens_list[:20]])
        if len(itens_list) > 20:
            itens_text += "\n... (e mais itens)"
            
        prompt = f"""Atue como um consultor especialista em licitações públicas na área da saúde.
Analise os dados abaixo e forneça um resumo estratégico para tomada de decisão.

DADOS DA LICITAÇÃO:
Órgão: {licitacao_obj.orgao}
Objeto: {licitacao_obj.objeto}
Modalidade: {licitacao_obj.modalidade}
Data: {licitacao_obj.data_sessao}

PRINCIPAIS ITENS:
{itens_text}

Gere um resumo com os seguintes tópicos (use Markdown):
1. **Resumo do Objeto**: O que está sendo comprado em linguagem simples?
2. **Atratividade**: Vale a pena participar? (Baseado no volume e tipo de itens)
3. **Riscos Potenciais**: Há algo que chame atenção negativamente? (Ex: itens muito específicos)
4. **Recomendação**: "Participar" ou "Ignorar"?
"""
        
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Erro ao gerar resumo com IA: {str(e)}. Verifique suas API Keys."

from googlesearch import search
import re

def get_google_price_estimate(item_description):
    """
    Busca no Google por preços do item e tenta extrair uma média.
    Retorna uma string com a faixa de preço ou mensagem.
    """
    try:
        query = f"preço {item_description} comprar"
        results = []
        prices = []
        
        # Busca 5 primeiros resultados
        for url in search(query, num_results=5, lang="pt"):
            results.append(url)
            
        # Nota: O googlesearch-python só retorna URLs (sem snippet/preço).
        # Para um preço "real" do Google seria necessário scraping de SERP ou API paga.
        # Aqui usamos IA (OpenRouter) apenas como referência rápida.
        
        return estimate_market_price_ai(item_description)

    except Exception as e:
        return f"Erro na busca: {str(e)}"

def estimate_market_price_ai(item_description):
    """
    Estima preço usando IA via OpenRouter.
    """
    try:
        model = get_model(temperature=0.3)
        prompt = f"""Atue como um especialista em compras hospitalares e governamentais.
Estime o preço médio de mercado (Unitário) para o produto: "{item_description}".
Considere preços praticados em licitações recentes e e-commerces especializados no Brasil.

Responda EXATAMENTE neste formato: "R$ X,XX - R$ Y,YY (Referência: [Fonte/Tipo de Fornecedor])".
Exemplo: "R$ 15,00 - R$ 20,00 (Referência: Distribuidores Hospitalares)".
Se não tiver ideia, responda "Preço desconhecido".
"""
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception:
        return "N/A"

# Mantemos a função antiga como alias para compatibilidade, se necessário
estimate_market_price = estimate_market_price_ai
