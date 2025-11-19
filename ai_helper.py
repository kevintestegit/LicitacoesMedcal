import google.generativeai as genai
import os

def configure_genai(api_key):
    """Configura a API Key do Gemini"""
    if api_key:
        genai.configure(api_key=api_key)
        return True
    return False

def summarize_bidding(licitacao_obj, itens_list):
    """
    Gera um resumo estratégico da licitação usando o Gemini.
    """
    try:
        model = genai.GenerativeModel('gemini-pro')
        
        # Prepara o prompt
        itens_text = "\n".join([f"- {i.descricao} ({i.quantidade} {i.unidade})" for i in itens_list[:20]]) # Limita a 20 itens para não estourar token
        if len(itens_list) > 20:
            itens_text += "\n... (e mais itens)"
            
        prompt = f"""
        Atue como um consultor especialista em licitações públicas na área da saúde.
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
        return f"Erro ao gerar resumo com IA: {str(e)}. Verifique sua API Key."

def estimate_market_price(item_description):
    """
    Tenta estimar preço de mercado (Simulação - Gemini não busca na web em tempo real sem tools, 
    mas pode dar uma estimativa baseada em conhecimento treinado).
    """
    try:
        model = genai.GenerativeModel('gemini-pro')
        prompt = f"""
        Estime uma faixa de preço médio de mercado (em Reais BRL) para o seguinte produto hospitalar/médico:
        "{item_description}"
        
        Responda APENAS com a faixa de preço. Exemplo: "R$ 10,00 - R$ 15,00".
        Se não souber, responda "Preço desconhecido".
        """
        response = model.generate_content(prompt)
        return response.text.strip()
    except:
        return "N/A"
