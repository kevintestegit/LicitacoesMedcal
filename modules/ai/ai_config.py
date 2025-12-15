import os
import requests
import json
import google.generativeai as genai
from modules.database.database import get_session, Configuracao

# ============================================================================
# CONFIGURAÇÃO CENTRALIZADA DE IA
# Prioridade: OpenRouter (gratuito) > Gemini (fallback)
# ============================================================================

def get_openrouter_api_key():
    """Retrieves OpenRouter API Key from Database or Environment Variable."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if api_key:
        return api_key
    
    try:
        session = get_session()
        config = session.query(Configuracao).filter_by(chave='openrouter_api_key').first()
        session.close()
        if config and config.valor:
            return config.valor
    except Exception as e:
        print(f"Erro ao ler OpenRouter API Key: {e}")
    
    return None

def get_gemini_api_key():
    """Retrieves Gemini API Key from Database or Environment Variable."""
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        return api_key
    
    try:
        session = get_session()
        config = session.query(Configuracao).filter_by(chave='gemini_api_key').first()
        session.close()
        if config and config.valor:
            return config.valor
    except Exception as e:
        print(f"Erro ao ler Gemini API Key: {e}")
    
    return None

def configure_genai():
    """Configures the Gemini library with the API Key."""
    api_key = get_gemini_api_key()
    if api_key:
        genai.configure(api_key=api_key)
        return True
    return False

# ============================================================================
# OPENROUTER CLIENT (Modelos Gratuitos)
# ============================================================================

# Modelos gratuitos do OpenRouter (atualizados Dez/2024)
OPENROUTER_FREE_MODELS = [
    "nvidia/nemotron-nano-9b-v2:free",          # Nvidia - rápido e bom
    "qwen/qwen3-coder:free",                     # Qwen - bom para análise
    "openai/gpt-oss-20b:free",                   # OpenAI OSS
    "cognitivecomputations/dolphin-mistral-24b-venice-edition:free",  # Dolphin
    "amazon/nova-2-lite-v1:free",                # Amazon Nova
]

class OpenRouterClient:
    """Cliente para OpenRouter com modelos gratuitos"""
    
    def __init__(self, api_key=None):
        self.api_key = api_key or get_openrouter_api_key()
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://medcal.com.br",
            "X-Title": "Medcal Licitacoes"
        }
    
    def generate_content(self, prompt, temperature=0.2, max_tokens=2000):
        """Gera conteúdo usando modelos gratuitos do OpenRouter"""
        if not self.api_key:
            raise ValueError("OpenRouter API Key não configurada")
        
        # Tenta cada modelo gratuito até um funcionar
        last_error = None
        for modelo in OPENROUTER_FREE_MODELS:
            try:
                response = requests.post(
                    self.base_url,
                    headers=self.headers,
                    json={
                        "model": modelo,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": temperature,
                        "max_tokens": max_tokens
                    },
                    timeout=60
                )
                
                if response.status_code == 200:
                    data = response.json()
                    # Retorna objeto compatível com interface do Gemini
                    return OpenRouterResponse(data['choices'][0]['message']['content'])
                elif response.status_code == 429:
                    continue  # Tenta próximo modelo
                else:
                    last_error = f"Status {response.status_code}: {response.text[:200]}"
                    continue
                    
            except Exception as e:
                last_error = str(e)
                continue
        
        raise Exception(f"Todos os modelos OpenRouter falharam. Último erro: {last_error}")

class OpenRouterResponse:
    """Classe wrapper para compatibilidade com interface do Gemini"""
    def __init__(self, text):
        self.text = text

# ============================================================================
# MODELO UNIFICADO (OpenRouter com fallback Gemini)
# ============================================================================

class UnifiedAIModel:
    """
    Modelo unificado que usa OpenRouter (gratuito) com fallback para Gemini.
    Interface compatível com GenerativeModel do Gemini.
    """
    
    def __init__(self, temperature=0.2):
        self.temperature = temperature
        self.openrouter_key = get_openrouter_api_key()
        self.gemini_key = get_gemini_api_key()
        
        # Configura Gemini se disponível (para fallback)
        if self.gemini_key:
            genai.configure(api_key=self.gemini_key)
    
    def generate_content(self, prompt):
        """Gera conteúdo: tenta OpenRouter primeiro, depois Gemini"""
        
        # Prioridade 1: OpenRouter (gratuito, sem rate limit agressivo)
        if self.openrouter_key:
            try:
                client = OpenRouterClient(self.openrouter_key)
                return client.generate_content(prompt, self.temperature)
            except Exception as e:
                # Silencia erros de rate limit (comum com plano gratuito)
                if "429" not in str(e) and "Rate limit" not in str(e):
                    print(f"[IA] OpenRouter indisponível, usando Gemini...")
        
        # Prioridade 2: Gemini (fallback)
        if self.gemini_key:
            try:
                model = genai.GenerativeModel(
                    'gemini-2.0-flash',
                    generation_config=genai.GenerationConfig(temperature=self.temperature)
                )
                return model.generate_content(prompt)
            except Exception as e:
                raise Exception(f"Gemini também falhou: {e}")
        
        raise ValueError("Nenhuma API de IA configurada (OpenRouter ou Gemini)")

# ============================================================================
# FUNÇÕES DE COMPATIBILIDADE
# ============================================================================

def get_model(temperature=0.2):
    """
    Retorna modelo unificado (OpenRouter + Gemini fallback).
    Mantém compatibilidade com código existente.
    """
    return UnifiedAIModel(temperature=temperature)
