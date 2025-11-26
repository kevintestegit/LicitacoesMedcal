import logging
import json
from .ai_config import get_model

class SemanticFilter:
    def __init__(self):
        self.model = get_model(temperature=0.0) # Zero temp for strict classification

    def is_relevant(self, objeto: str) -> bool:
        """
        Uses AI to decide if the bidding object is relevant to Clinical Analysis/Laboratory.
        Returns True if relevant, False otherwise.
        """
        if not objeto or len(objeto) < 10:
            return False

        prompt = f"""
        Você é um filtro semântico estrito para uma empresa de DISTRIBUIÇÃO DE PRODUTOS PARA LABORATÓRIO DE ANÁLISES CLÍNICAS.
        
        Sua missão é dizer SIM ou NÃO se o objeto da licitação é pertinente ao ramo de atuação.
        
        O QUE A EMPRESA VENDE (RELEVANTE):
        - Reagentes químicos/biológicos para laboratório.
        - Equipamentos de laboratório (Centrífugas, Microscópios, Analisadores de Bioquímica/Hematologia).
        - Materiais de consumo laboratorial (Tubos de coleta, ponteiras, lâminas, agulhas, seringas).
        - Testes rápidos, gasometria, uroanálise.
        
        O QUE A EMPRESA NÃO VENDE (IRRELEVANTE - FALSE):
        - MEDICAMENTOS (Remédios, comprimidos, xaropes, injetáveis, antibióticos).
        - ENXOVAL HOSPITALAR (Lençóis, roupas, tecidos, cama e mesa).
        - LIVROS, Revistas, Material Didático.
        - Material de Limpeza (Vassouras, desinfetantes comuns).
        - Material de Escritório/Informática genérica.
        - Serviços médicos (Consultas, plantões).
        - Obras, Engenharia, Veículos, Combustíveis.
        
        OBJETO DA LICITAÇÃO:
        "{objeto}"
        
        Responda APENAS com um JSON:
        {{
            "relevante": true/false,
            "motivo": "Breve explicação"
        }}
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
            return data.get("relevante", False)

        except Exception as e:
            logging.error(f"Erro no filtro semântico IA: {e}")
            # Se der erro na IA, aprovamos para não perder oportunidade (fallback seguro)
            # Ou reprovamos se quisermos ser estritos. Dado o pedido do usuário, melhor ser estrito?
            # Não, melhor aprovar e deixar o humano filtrar do que perder negócio por erro de API.
            return True
