import os
import requests

from modules.database.database import get_session, Configuracao

# ============================================================================
# CONFIGURAÇÃO CENTRALIZADA DE IA (OpenRouter-only)
# ============================================================================


def get_openrouter_api_key():
    """Obtém OpenRouter API Key por env ou banco (Configuracao.openrouter_api_key)."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if api_key:
        return api_key

    session = get_session()
    try:
        config = session.query(Configuracao).filter_by(chave="openrouter_api_key").first()
        if config and config.valor:
            return config.valor
        return None
    finally:
        session.close()


# Mantido por compatibilidade com código antigo; agora sempre retorna False.
def configure_genai():
    return False


# Modelos gratuitos do OpenRouter (pode ser ajustado conforme necessidade)
OPENROUTER_FREE_MODELS = [
    "nvidia/nemotron-nano-9b-v2:free",
    "qwen/qwen3-coder:free",
    "openai/gpt-oss-20b:free",
    "cognitivecomputations/dolphin-mistral-24b-venice-edition:free",
    "amazon/nova-2-lite-v1:free",
]


class OpenRouterResponse:
    """Wrapper simples para compatibilidade com interface generate_content().text."""

    def __init__(self, text: str):
        self.text = text


class OpenRouterClient:
    """Cliente OpenRouter (chat.completions)."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or get_openrouter_api_key()
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://medcal.local",
            "X-Title": "Medcal Licitacoes",
        }

    def generate_content(self, prompt: str, temperature: float = 0.2, max_tokens: int = 2000) -> OpenRouterResponse:
        if not self.api_key:
            raise ValueError("OpenRouter API Key não configurada")

        last_error = None
        for model in OPENROUTER_FREE_MODELS:
            try:
                response = requests.post(
                    self.base_url,
                    headers=self.headers,
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                    },
                    timeout=60,
                )
                if response.status_code == 200:
                    data = response.json()
                    return OpenRouterResponse(data["choices"][0]["message"]["content"])
                if response.status_code == 429:
                    continue
                last_error = f"Status {response.status_code}: {response.text[:200]}"
            except Exception as exc:
                last_error = str(exc)

        raise Exception(f"OpenRouter falhou. Último erro: {last_error}")


class UnifiedAIModel:
    """
    Mantido por compatibilidade: agora é OpenRouter-only.
    Interface compatível com o antigo GenerativeModel (generate_content()).
    """

    def __init__(self, temperature: float = 0.2):
        self.temperature = temperature
        self.openrouter_key = get_openrouter_api_key()

    def generate_content(self, prompt: str):
        client = OpenRouterClient(self.openrouter_key)
        return client.generate_content(prompt, temperature=self.temperature)


def get_model(temperature: float = 0.2):
    """Retorna modelo unificado (OpenRouter-only)."""
    return UnifiedAIModel(temperature=temperature)
