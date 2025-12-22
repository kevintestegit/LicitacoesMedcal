import random
import time
import unicodedata

from rapidfuzz import fuzz

from .ai_config import get_model
from modules.database.database import Produto, get_session

# Termos que indicam contexto LABORATORIAL/HOSPITALAR
CONTEXTO_LABORATORIAL = [
    "HEMATOLOGIA",
    "BIOQUIMICA",
    "COAGULACAO",
    "COAGULAÇÃO",
    "IMUNOLOGIA",
    "IONOGRAMA",
    "GASOMETRIA",
    "POCT",
    "URINALISE",
    "URINA",
    "HEMOGRAMA",
    "LABORATORIO",
    "LABORATÓRIO",
    "LABORATORIAL",
    "ANALISE CLINICA",
    "ANÁLISE CLÍNICA",
    "ANALISES CLINICAS",
    "ANÁLISES CLÍNICAS",
    "ANALISADOR",
    "EQUIPAMENTO",
    "CENTRIFUGA",
    "CENTRÍFUGA",
    "MICROSCOPIO",
    "MICROSCÓPIO",
    "AUTOCLAVE",
    "COAGULOMETRO",
    "COAGULÔMETRO",
    "HOMOGENEIZADOR",
    "AGITADOR",
    "REAGENTE",
    "REAGENTES",
    "INSUMO",
    "INSUMOS",
    "DILUENTE",
    "LISANTE",
    "CALIBRADOR",
    "CONTROLE DE QUALIDADE",
    "PADRAO",
    "PADRÃO",
    "TUBO",
    "TUBOS",
    "COLETA",
    "VACUO",
    "VÁCUO",
    "EDTA",
    "HEPARINA",
    "CITRATO",
    "AGULHA",
    "SERINGA",
    "LANCETA",
    "SCALP",
    "CATETER",
    "LUVA",
    "LUVAS",
    "MASCARA",
    "MÁSCARA",
    "LAMINA",
    "LÂMINA",
    "PONTEIRA",
    "TESTE RAPIDO",
    "TESTE RÁPIDO",
    "HEMOSTASIA",
    "HORMONIO",
    "HORMÔNIO",
    "TSH",
    "T4",
    "T3",
    "GLICOSE",
    "COLESTEROL",
    "TRIGLICERIDES",
    "UREIA",
    "CREATININA",
    "TGO",
    "TGP",
    "HOSPITALAR",
    "HOSPITALARES",
    "AMBULATORIAL",
    "BIOMEDICO",
    "BIOMÉDICO",
    "SONDA",
    "EQUIPO",
    "EQUIPOS",
    "CANULA",
    "CÂNULA",
    "LOCACAO",
    "LOCAÇÃO",
    "COMODATO",
    "ALUGUEL",
    "MANUTENCAO PREVENTIVA",
    "MANUTENÇÃO PREVENTIVA",
]


def normalize_text(texto: str) -> str:
    if not texto:
        return ""
    return unicodedata.normalize("NFKD", texto).encode("ASCII", "ignore").decode("ASCII").upper()


def tem_contexto_laboratorial(texto: str) -> bool:
    texto_norm = normalize_text(texto)
    return any(termo in texto_norm for termo in CONTEXTO_LABORATORIAL)


class SemanticMatcher:
    """
    Matcher de catálogo sem dependência de embeddings (Gemini removido).
    - `find_matches`: fuzzy match (token_set_ratio) entre objeto e (nome+keywords).
    - `verify_match`: validação LLM (OpenRouter) para reduzir falsos positivos.
    """

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if SemanticMatcher._initialized:
            return
        self.products = []
        self._products_loaded = False
        SemanticMatcher._initialized = True

    def _ensure_products_loaded(self):
        if self._products_loaded:
            return
        session = get_session()
        try:
            self.products = session.query(Produto).all()
        finally:
            session.close()
        self._products_loaded = True

    def find_matches(self, text_objeto: str, threshold: float = 0.75):
        self._ensure_products_loaded()
        if not self.products:
            return []
        if not tem_contexto_laboratorial(text_objeto):
            return []

        text_norm = normalize_text(text_objeto)
        matches = []
        for produto in self.products:
            rep = normalize_text(f"{produto.nome} {produto.palavras_chave}")
            score = fuzz.token_set_ratio(text_norm, rep) / 100.0
            if score >= threshold:
                matches.append((produto, float(score)))
        matches.sort(key=lambda x: x[1], reverse=True)
        return matches

    def verify_match(self, item_licitacao: str, produto_catalogo: str) -> bool:
        max_retries = 3
        base_delay = 1

        prompt = f"""Atue como um Especialista em Licitações de Produtos Laboratoriais e Hospitalares.

Verifique se o ITEM DA LICITAÇÃO é tecnicamente compatível ou equivalente ao MEU PRODUTO.

ITEM DA LICITAÇÃO: "{item_licitacao}"
MEU PRODUTO: "{produto_catalogo}"

Regras:
1. Considere sinônimos técnicos (ex: "Hemograma" = "Hematologia").
2. Se o item for genérico (ex: "Material de Limpeza") e meu produto for específico, responda NÃO.
3. Se o item for equipamento e meu produto for reagente (ou vice-versa), responda NÃO.
4. Responda APENAS "SIM" ou "NAO".
"""

        for attempt in range(max_retries):
            try:
                model = get_model(temperature=0.1)
                response = model.generate_content(prompt)
                resposta = response.text.strip().upper()
                return "SIM" in resposta
            except Exception as exc:
                error_str = str(exc)
                if "429" in error_str or "rate limit" in error_str.lower():
                    delay = base_delay * (2**attempt) + random.uniform(0, 1)
                    time.sleep(delay)
                else:
                    return False

        return False

