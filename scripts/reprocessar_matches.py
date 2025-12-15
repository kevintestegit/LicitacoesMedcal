#!/usr/bin/env python3
"""
Script para reprocessar todos os matches de itens com a nova lógica rigorosa.
Limpa matches incorretos e recalcula usando o novo algoritmo.
"""
import sys
import os

# Adiciona o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unicodedata
from rapidfuzz import fuzz
from modules.database.database import get_session, Licitacao, ItemLicitacao, Produto

def normalize_text(texto: str) -> str:
    if not texto:
        return ""
    return unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('ASCII').upper()

# Termos que indicam contexto LABORATORIAL/HOSPITALAR
CONTEXTO_LABORATORIAL = [
    "HEMATOLOGIA", "BIOQUIMICA", "COAGULACAO", "COAGULAÇÃO", "IMUNOLOGIA", "IONOGRAMA",
    "GASOMETRIA", "POCT", "URINALISE", "URINA", "HEMOGRAMA", "LABORATORIO", "LABORATÓRIO",
    "LABORATORIAL", "ANALISE CLINICA", "ANÁLISE CLÍNICA", "ANALISES CLINICAS", "ANÁLISES CLÍNICAS",
    "CURVA GLICEMICA", "GTT", "GTC", "TOLERANCIA GLICOSE", "DOSAGEM",
    "AMILASE", "ALBUMINA", "BILIRRUBINA", "CALCIO", "FERRO", "URICO", "ÁCIDO ÚRICO", "ACIDO URICO",
    "CLORETO", "COLESTEROL", "HDL", "LDL",
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

def best_match_against_keywords(texto_item: str, keywords, nome_produto_catalogo=""):
    """
    Nova lógica RIGOROSA de matching.
    """
    if not texto_item or not keywords:
        return 0, ""
    
    texto_norm = normalize_text(texto_item)
    best_score = 0
    best_kw = ""
    
    # ETAPA 1: Verificar contexto laboratorial
    tem_contexto_lab = any(termo in texto_norm for termo in CONTEXTO_LABORATORIAL)
    if not tem_contexto_lab:
        return 0, ""
    
    # ETAPA 2: Matching com keywords
    termos_insumo = ["REAGENTE", "SOLUCAO", "LISANTE", "DILUENTE", "TUBO", "LAMINA", "CLORETO", "ACIDO", "KIT", "TIRA", "FRASCO"]
    termos_equip = ["ANALISADOR", "EQUIPAMENTO", "APARELHO", "HOMOGENEIZADOR", "AGITADOR", "CENTRIFUGA", "MICROSCOPIO", "AUTOCLAVE", "COAGULOMETRO"]
    
    nome_prod_norm = normalize_text(nome_produto_catalogo)
    eh_equipamento_catalogo = any(t in nome_prod_norm for t in termos_equip)
    tem_cara_de_insumo_item = any(t in texto_norm for t in termos_insumo) and not any(t in texto_norm for t in termos_equip)
    
    for kw in keywords:
        if not kw: continue
        kw_norm = normalize_text(kw)
        
        if len(kw_norm) < 4: continue
        
        score = 0
        
        if kw_norm in texto_norm:
            score = 95
        else:
            palavras_kw = set(kw_norm.split())
            palavras_texto = set(texto_norm.split())
            palavras_em_comum = palavras_kw.intersection(palavras_texto)
            
            if len(palavras_kw) > 0:
                percentual_match = len(palavras_em_comum) / len(palavras_kw)
                
                if percentual_match >= 1.0:
                    score = 90
                elif percentual_match >= 0.8:
                    score = 80
                elif percentual_match >= 0.6:
                    token_score = fuzz.token_set_ratio(kw_norm, texto_norm)
                    if token_score >= 90:
                        score = 75
                    elif token_score >= 85:
                        score = 70
        
        if eh_equipamento_catalogo and tem_cara_de_insumo_item:
            if not any(ti in kw_norm for ti in termos_insumo):
                score -= 50 
        
        if score > best_score:
            best_score = score
            best_kw = kw
            
    return max(0, best_score), best_kw


def main():
    print("=" * 60)
    print("🔄 REPROCESSANDO MATCHES COM NOVA LÓGICA RIGOROSA")
    print("=" * 60)
    
    session = get_session()
    
    # Carrega produtos
    produtos = session.query(Produto).all()
    print(f"\n📦 Produtos no catálogo: {len(produtos)}")
    
    # Carrega todos os itens
    itens = session.query(ItemLicitacao).all()
    print(f"📋 Itens de licitações: {len(itens)}")
    
    # Estatísticas
    total_itens = len(itens)
    matches_anteriores = sum(1 for i in itens if i.produto_match_id is not None)
    matches_removidos = 0
    matches_mantidos = 0
    matches_novos = 0
    
    print(f"\n🔍 Matches anteriores: {matches_anteriores}")
    print("\nProcessando...")
    
    limiar = 75  # Threshold mínimo
    
    for idx, item in enumerate(itens, 1):
        if idx % 100 == 0:
            print(f"  Processando item {idx}/{total_itens}...")
        
        item_desc = item.descricao or ""
        tinha_match = item.produto_match_id is not None
        
        melhor_match = None
        melhor_score = 0
        
        for prod in produtos:
            keywords = [k.strip() for k in prod.palavras_chave.split(',') if k.strip() and len(k.strip()) > 3]
            keywords.append(prod.nome)
            score, _ = best_match_against_keywords(item_desc, keywords, nome_produto_catalogo=prod.nome)
            if score > melhor_score:
                melhor_match = prod
                melhor_score = score
        
        if melhor_match and melhor_score >= limiar:
            item.produto_match_id = melhor_match.id
            item.match_score = melhor_score
            if tinha_match:
                matches_mantidos += 1
            else:
                matches_novos += 1
        else:
            if tinha_match:
                matches_removidos += 1
            item.produto_match_id = None
            item.match_score = melhor_score
    
    session.commit()
    session.close()
    
    print("\n" + "=" * 60)
    print("✅ REPROCESSAMENTO CONCLUÍDO")
    print("=" * 60)
    print(f"\n📊 ESTATÍSTICAS:")
    print(f"  - Matches anteriores: {matches_anteriores}")
    print(f"  - Matches REMOVIDOS (falsos positivos): {matches_removidos}")
    print(f"  - Matches mantidos: {matches_mantidos}")
    print(f"  - Matches novos: {matches_novos}")
    print(f"  - Total de matches agora: {matches_mantidos + matches_novos}")
    print(f"\n  🎯 Threshold utilizado: {limiar}")
    print()


if __name__ == "__main__":
    main()
