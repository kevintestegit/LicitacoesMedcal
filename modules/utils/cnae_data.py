# Dicionário de CNAEs e suas respectivas palavras-chave
# Fonte: Adaptação dos termos observados no pncp_client.py e conhecimento geral

CNAE_KEYWORDS = {
    "4649-4/08": [ # Comércio atacadista de produtos de higiene, limpeza e conservação domiciliar
        "LIMPEZA", "SANEANTE", "SANEANTES", "DOMISSANITARIO", "DOMISSANITÁRIO", 
        "DETERGENTE", "DESINFETANTE", "AGUA SANITARIA", "SABAO"
    ],
    "4789-0/05": [ # Comércio varejista de produtos saneantes domissanitários
        "SANEANTE", "DOMISSANITARIO", "INSETICIDA", "RATICIDA"
    ],
    "4664-8/00": [ # Comércio atacadista de máquinas, aparelhos e equipamentos para uso odonto-médico-hospitalar; partes e peças
        "ACESSORIO", "ACESSÓRIO", 
        "MANUTENCAO", "MANUTENÇÃO", "REPARO", "CALIBRACAO", "CALIBRAÇÃO"
    ],
    "4645-1/01": [ # Comércio atacadista de instrumentos e materiais para uso médico, cirúrgico, hospitalar e de laboratórios
        "MATERIAL HOSPITALAR", "MATERIAIS HOSPITALARES", "MATERIAL MEDICO", "MATERIAIS MEDICOS",
        "MATERIAL CIRURGICO", "INSTRUMENTOS CIRURGICOS", "AGULHA", "SERINGA", "CATETER", "SONDA",
        "LUVA CIRURGICA", "MASCARA CIRURGICA", "GAZE", "ATADURA", "ESPARADRAPO"
    ],
    "4645-1/03": [ # Comércio atacadista de produtos odontológicos
        "ODONTOLOGICO", "ODONTOLÓGICO", "MATERIAL ODONTOLOGICO", "RESINA", "AMALGAMA", 
        "ANESTESICO ODONTOLOGICO", "BROCA ODONTOLOGICA", "CIMENTO ODONTOLOGICO"
    ]
}

def get_keywords_by_cnae(cnae_code):
    """Retorna lista de keywords para um CNAE específico (remove pontuação para busca)."""
    # Normaliza o input (remove ./ -)
    clean_code = cnae_code.replace(".", "").replace("/", "").replace("-", "")
    
    # Busca no dicionário (que também deve ser normalizado na chave se necessário, 
    # mas aqui vamos manter as chaves formatadas para leitura e limpar na comparação)
    
    for key, keywords in CNAE_KEYWORDS.items():
        clean_key = key.replace(".", "").replace("/", "").replace("-", "")
        if clean_key == clean_code:
            return keywords
            
    return []
