import logging
import json
import re
import pypdf
from io import BytesIO
from modules.ai.ai_config import get_model

class PDFExtractor:
    def __init__(self):
        self.model = get_model(temperature=0.0) # Zero temp for precision

    def extract_text(self, pdf_content: bytes) -> str:
        """Extracts raw text from PDF bytes."""
        try:
            reader = pypdf.PdfReader(BytesIO(pdf_content))
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            return text
        except Exception as e:
            logging.error(f"Erro ao ler PDF: {e}")
            return ""

    def extract_financial_data(self, pdf_text: str) -> list:
        """
        Uses AI to extract structured financial data (Item, Qty, Max Price) from text.
        Returns a list of dicts.
        """
        if not pdf_text or len(pdf_text) < 50:
            return []

        # Truncate to avoid token limits (focus on first 50k chars where tables usually are)
        text_sample = pdf_text[:50000]

        prompt = f"""
        Você é um extrator de dados financeiros de licitações.
        Analise o texto abaixo (extraído de um PDF) e encontre a TABELA DE ITENS/LOTE.
        
        Para cada item, extraia:
        - numero_item: O número do item/lote.
        - descricao: Descrição resumida do produto.
        - quantidade: A quantidade total solicitada (apenas números).
        - unidade: A unidade de medida (UN, CX, FR, etc).
        - valor_maximo: O valor unitário máximo/referência (Teto). Se não tiver, procure o valor total e divida pela quantidade.
        
        TEXTO:
        {text_sample}
        
        Retorne APENAS um JSON válido no formato lista:
        [
            {{
                "numero_item": "1",
                "descricao": "Nome do Produto",
                "quantidade": 100,
                "unidade": "CX",
                "valor_maximo": 50.00
            }}
        ]
        Se não encontrar tabela ou valores, retorne [].
        """

        try:
            response = self.model.generate_content(prompt)
            raw_text = response.text.strip()
            
            # Clean Markdown
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]
                
            data = json.loads(raw_text)
            return data if isinstance(data, list) else []

        except Exception as e:
            logging.error(f"Erro na extração financeira via IA: {e}")
            # Fallback (Simples Regex se IA falhar)
            return self._fallback_extraction(text_sample)

    def _fallback_extraction(self, text: str) -> list:
        """Tentativa básica de extrair via Regex se a IA falhar."""
        items = []
        # Regex genérico para tentar pegar linhas de itens (ex: "1  Luva Latex  100  CX  R$ 50,00")
        # Muito difícil fazer regex perfeito para todas as tabelas, mas serve de "melhor que nada"
        return []
