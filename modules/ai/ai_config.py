import os
import google.generativeai as genai
import os
import google.generativeai as genai
from modules.database.database import get_session, Configuracao

def get_gemini_api_key():
    """Retrieves Gemini API Key from Database or Environment Variable."""
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        return api_key
    
    try:
        session = get_session()
        config = session.query(Configuracao).filter_by(chave='gemini_api_key').first()
        session.close()
        if config:
            return config.valor
    except Exception as e:
        print(f"Erro ao ler configuração de API Key: {e}")
    
    return None

def configure_genai():
    """Configures the Gemini library with the API Key."""
    api_key = get_gemini_api_key()
    if not api_key:
        raise ValueError("Gemini API Key não encontrada! Configure no Dashboard ou variável de ambiente GEMINI_API_KEY.")
    
    genai.configure(api_key=api_key)

# --- Model Configurations ---
# Lista de modelos para tentar (do mais rápido/barato para o mais robusto)
AVAILABLE_MODELS = [
    'gemini-2.0-flash',
    'gemini-2.0-flash-lite',
    'gemini-2.5-flash',
    'gemini-flash-latest',
]

def get_model(temperature=0.2):
    configure_genai()
    
    # Tenta configurar o modelo padrão, mas a biblioteca do Google geralmente não valida o nome na instanciação,
    # apenas na geração. Então vamos retornar o configurado com o primeiro da lista ou um fixo.
    # O erro 404 acontece na chamada, então aqui apenas definimos o nome preferencial.
    
    model_name = 'gemini-2.0-flash' # Modelo gratuito atualizado (Nov 2025)
    
    return genai.GenerativeModel(
        model_name,
        generation_config=genai.GenerationConfig(
            temperature=temperature,
        )
    )
