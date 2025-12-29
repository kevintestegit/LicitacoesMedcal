"""
Classificador de Categorias para Licitações
Categoriza automaticamente licitações baseado no objeto e itens.
"""

import unicodedata
from typing import Optional, List


def _normalize(text: str) -> str:
    """Remove acentos e converte para maiúsculas."""
    if not text:
        return ""
    # Remove acentos
    text = unicodedata.normalize('NFD', text)
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    return text.upper()


# Dicionário de palavras-chave por categoria (ordem de prioridade)
CATEGORIAS = {
    "Equipamentos": [
        # Locação/Comodato (prioridade máxima para Medcal)
        "LOCACAO DE EQUIPAMENTO", "LOCAÇÃO DE EQUIPAMENTO", "COMODATO",
        "ALUGUEL DE EQUIPAMENTO", "CESSAO DE EQUIPAMENTO", "CESSÃO DE EQUIPAMENTO",
        # Analisadores
        "ANALISADOR", "ANALIZADOR", "EQUIPAMENTO AUTOMATIZADO",
        "EQUIPAMENTO DE HEMATOLOGIA", "EQUIPAMENTO DE BIOQUIMICA",
        "EQUIPAMENTO DE COAGULACAO", "EQUIPAMENTO DE IONOGRAMA",
        "EQUIPAMENTO DE GASOMETRIA", "EQUIPAMENTO LABORATORIAL",
        "EQUIPAMENTO HOSPITALAR", "EQUIPAMENTO BIOMEDICO", "EQUIPAMENTO BIOMÉDICO",
        # Equipamentos específicos
        "CENTRIFUGA", "CENTRÍFUGA", "AUTOCLAVE", "HOMOGENEIZADOR",
        "MICROSCÓPIO", "MICROSCOPIO", "ESPECTROFOTOMETRO", "ESPECTROFOTÔMETRO",
        "COAGULOMETRO", "COAGULÔMETRO", "HEMOGASOMETRO", "HEMOGASÔMETRO",
        "GASOMETRO", "GASÔMETRO",
    ],
    
    "Reagentes": [
        "REAGENTE", "REAGENTES", "CALIBRADOR", "CALIBRADORES",
        "CONTROLE DE QUALIDADE", "DILUENTE", "LISANTE", "HEMOLISANTE",
        "REAGENTE HEMATOLOGICO", "REAGENTE BIOQUIMICO", "REAGENTE IMUNOLOGICO",
        "REAGENTES PARA HEMATOLOGIA", "REAGENTES PARA BIOQUIMICA",
        "REAGENTES PARA COAGULACAO", "REAGENTES PARA IONOGRAMA",
        "REAGENTES LABORATORIAIS", "INSUMOS LABORATORIAIS",
        "COLORACAO", "COLORAÇÃO", "CORANTE",
    ],
    
    "Consumíveis": [
        # Tubos e coleta
        "TUBO DE COLETA", "TUBOS DE COLETA", "TUBO VACUO", "TUBO VÁCUO",
        "TUBO EDTA", "TUBO HEPARINA", "TUBO CITRATO",
        # Descartáveis hospitalares
        "LUVA", "LUVAS", "MASCARA", "MÁSCARA", "MASCARAS", "MÁSCARAS",
        "SERINGA", "SERINGAS", "AGULHA", "AGULHAS", "SCALP",
        "CATETER", "CATETERES", "CANULA", "CÂNULA", "CANULAS", "CÂNULAS",
        "SONDA", "SONDAS", "EQUIPO", "EQUIPOS",
        "LANCETA", "LANCETAS", "PONTEIRA", "PONTEIRAS",
        "LAMINA", "LÂMINA", "LAMINAS", "LÂMINAS", "LAMINULA", "LAMÍNULA",
        # Outros descartáveis
        "MATERIAL DESCARTAVEL", "MATERIAL DESCARTÁVEL",
        "MATERIAIS DESCARTAVEIS", "MATERIAIS DESCARTÁVEIS",
        "DESCARTAVEL", "DESCARTÁVEL",
    ],
    
    "Serviços": [
        "MANUTENCAO PREVENTIVA", "MANUTENÇÃO PREVENTIVA",
        "MANUTENCAO CORRETIVA", "MANUTENÇÃO CORRETIVA",
        "MANUTENCAO E REPARO", "MANUTENÇÃO E REPARO",
        "ASSISTENCIA TECNICA", "ASSISTÊNCIA TÉCNICA",
        "CALIBRACAO", "CALIBRAÇÃO", "AFERICAO", "AFERIÇÃO",
        "SERVICO DE", "SERVIÇO DE", "PRESTACAO DE SERVICO", "PRESTAÇÃO DE SERVIÇO",
        "CONTRATACAO DE SERVICO", "CONTRATAÇÃO DE SERVIÇO",
    ],
    
    "Kits/Testes": [
        "TESTE RAPIDO", "TESTE RÁPIDO", "TESTES RAPIDOS", "TESTES RÁPIDOS",
        "KIT DIAGNOSTICO", "KIT DIAGNÓSTICO", "KITS DIAGNOSTICOS",
        "KIT DE TESTE", "KIT PARA", "ELISA", "PCR",
        "IMUNOCROMATOGRAFIA", "IMUNOCROMATOGRÁFICO",
        "TESTE DE GRAVIDEZ", "TESTE DE GLICEMIA",
    ],
}


def classificar_licitacao(objeto: str, itens: List[str] = None) -> Optional[str]:
    """
    Classifica uma licitação em uma categoria baseado no objeto e itens.
    
    Args:
        objeto: Texto do objeto da licitação
        itens: Lista de descrições dos itens (opcional)
    
    Returns:
        Nome da categoria ou None se não classificável
    """
    if not objeto:
        return None
    
    # Normaliza o objeto
    objeto_norm = _normalize(objeto)
    
    # Também normaliza os itens se fornecidos
    itens_norm = []
    if itens:
        itens_norm = [_normalize(item) for item in itens if item]
    
    # Texto combinado para análise
    texto_completo = objeto_norm + " " + " ".join(itens_norm)
    
    # Verifica cada categoria em ordem de prioridade
    for categoria, palavras in CATEGORIAS.items():
        for palavra in palavras:
            palavra_norm = _normalize(palavra)
            if palavra_norm in texto_completo:
                return categoria
    
    # Se tem "HOSPITALAR" ou "LABORATORIAL" mas não classificou, assume Consumíveis
    if any(termo in texto_completo for termo in ["HOSPITALAR", "LABORATORIAL", "MATERIAL MEDICO", "MATERIAL MÉDICO"]):
        return "Consumíveis"
    
    return None


def classificar_por_itens(itens_descricoes: List[str]) -> dict:
    """
    Analisa uma lista de itens e retorna contagem por categoria.
    Útil para licitações com muitos itens de diferentes tipos.
    
    Args:
        itens_descricoes: Lista de descrições de itens
    
    Returns:
        dict com contagem por categoria
    """
    contagem = {}
    
    for desc in itens_descricoes:
        if not desc:
            continue
        
        categoria = classificar_licitacao(desc)
        if categoria:
            contagem[categoria] = contagem.get(categoria, 0) + 1
    
    return contagem


def categoria_dominante(itens_descricoes: List[str]) -> Optional[str]:
    """
    Retorna a categoria mais frequente entre os itens.
    
    Args:
        itens_descricoes: Lista de descrições de itens
    
    Returns:
        Nome da categoria dominante ou None
    """
    contagem = classificar_por_itens(itens_descricoes)
    
    if not contagem:
        return None
    
    # Retorna a categoria com maior contagem
    return max(contagem, key=contagem.get)


# Lista de categorias disponíveis (para uso no dashboard)
CATEGORIAS_DISPONIVEIS = ["Todas", "Equipamentos", "Reagentes", "Consumíveis", "Serviços", "Kits/Testes"]
