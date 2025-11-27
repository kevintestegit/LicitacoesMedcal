import json
import os
import unicodedata
import numpy as np
import google.generativeai as genai
from .ai_config import configure_genai
from sqlalchemy.orm import Session
from modules.database.database import Produto, get_session # Reusing existing models

# Caminho absoluto para o cache em data/
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CACHE_FILE = os.path.join(BASE_DIR, 'data', 'embeddings_cache.json')

# Termos que indicam contexto LABORATORIAL/HOSPITALAR
CONTEXTO_LABORATORIAL = [
    "HEMATOLOGIA", "BIOQUIMICA", "COAGULACAO", "COAGULAÇÃO", "IMUNOLOGIA", "IONOGRAMA",
    "GASOMETRIA", "POCT", "URINALISE", "URINA", "HEMOGRAMA", "LABORATORIO", "LABORATÓRIO",
    "LABORATORIAL", "ANALISE CLINICA", "ANÁLISE CLÍNICA", "ANALISES CLINICAS", "ANÁLISES CLÍNICAS",
    "ANALISADOR", "EQUIPAMENTO", "CENTRIFUGA", "CENTRÍFUGA", "MICROSCOPIO", "MICROSCÓPIO",
    "AUTOCLAVE", "COAGULOMETRO", "COAGULÔMETRO", "HOMOGENEIZADOR", "AGITADOR",
    "REAGENTE", "REAGENTES", "INSUMO", "INSUMOS", "DILUENTE", "LISANTE", "CALIBRADOR",
    "CONTROLE DE QUALIDADE", "PADRAO", "PADRÃO",
    "TUBO", "TUBOS", "COLETA", "VACUO", "VÁCUO", "EDTA", "HEPARINA", "CITRATO",
    "AGULHA", "SERINGA", "LANCETA", "SCALP", "CATETER",
    "LUVA", "LUVAS", "MASCARA", "MÁSCARA", "LAMINA", "LÂMINA", "PONTEIRA",
    "TESTE RAPIDO", "TESTE RÁPIDO", "HEMOSTASIA", "HORMONIO", "HORMÔNIO", "TSH", "T4", "T3",
    "GLICOSE", "COLESTEROL", "TRIGLICERIDES", "UREIA", "CREATININA", "TGO", "TGP",
    "HOSPITALAR", "HOSPITALARES", "AMBULATORIAL", "BIOMEDICO", "BIOMÉDICO",
    "SONDA", "EQUIPO", "EQUIPOS", "CANULA", "CÂNULA",
    "LOCACAO", "LOCAÇÃO", "COMODATO", "ALUGUEL", "MANUTENCAO PREVENTIVA", "MANUTENÇÃO PREVENTIVA"
]

def normalize_text(texto: str) -> str:
    """Normaliza texto removendo acentos e convertendo para maiúsculas."""
    if not texto:
        return ""
    return unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('ASCII').upper()

def tem_contexto_laboratorial(texto: str) -> bool:
    """Verifica se o texto tem contexto laboratorial/hospitalar."""
    texto_norm = normalize_text(texto)
    return any(termo in texto_norm for termo in CONTEXTO_LABORATORIAL)

class SemanticMatcher:
    def __init__(self):
        configure_genai()
        self.cache = self._load_cache()
        self.products = []
        self.product_embeddings = []
        self._refresh_product_embeddings()

    def _load_cache(self):
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "r") as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def _save_cache(self):
        with open(CACHE_FILE, "w") as f:
            json.dump(self.cache, f)

    def generate_embedding(self, text: str):
        """Generates embedding for a text using Gemini."""
        if text in self.cache:
            return self.cache[text]
        
        try:
            # Using the text-embedding-004 model (or latest available)
            result = genai.embed_content(
                model="models/text-embedding-004",
                content=text,
                task_type="retrieval_query"
            )
            embedding = result['embedding']
            self.cache[text] = embedding
            self._save_cache() # Save incrementally
            return embedding
        except Exception as e:
            print(f"Erro ao gerar embedding: {e}")
            return None

    def _refresh_product_embeddings(self):
        """Loads products from DB and ensures they have embeddings."""
        session = get_session()
        self.products = session.query(Produto).all()
        
        self.product_embeddings = []
        for p in self.products:
            # Combine name and keywords for a rich representation
            text_rep = f"{p.nome} {p.palavras_chave}"
            emb = self.generate_embedding(text_rep)
            if emb:
                self.product_embeddings.append({
                    "product": p,
                    "embedding": emb
                })
        
        session.close()

    def find_matches(self, text_objeto: str, threshold=0.75):
        """
        Finds products that match the object description semantically.
        Returns list of (Produto, score).
        
        IMPORTANTE: Só retorna matches se o texto tiver contexto laboratorial.
        Threshold aumentado de 0.6 para 0.75 para maior precisão.
        """
        if not self.product_embeddings:
            return []
        
        # VALIDAÇÃO DE CONTEXTO: Se não tem contexto laboratorial, retorna vazio
        if not tem_contexto_laboratorial(text_objeto):
            return []

        target_emb = self.generate_embedding(text_objeto)
        if not target_emb:
            return []

        matches = []
        target_vec = np.array(target_emb)

        for item in self.product_embeddings:
            prod_vec = np.array(item["embedding"])
            
            # Cosine Similarity
            score = np.dot(target_vec, prod_vec) / (np.linalg.norm(target_vec) * np.linalg.norm(prod_vec))
            
            if score >= threshold:
                matches.append((item["product"], float(score)))

        # Sort by score desc
        matches.sort(key=lambda x: x[1], reverse=True)
        return matches
