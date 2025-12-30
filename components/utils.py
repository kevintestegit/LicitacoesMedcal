import unicodedata
from datetime import datetime
from rapidfuzz import fuzz
import streamlit as st
from modules.database.database import get_session, Produto, Licitacao

def normalize_text(texto: str) -> str:
    if not texto:
        return ""
    return unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('ASCII').upper()

def safe_parse_date(date_str):
    if not date_str or not isinstance(date_str, str) or date_str.strip() == "":
        return None
    try:
        return datetime.fromisoformat(date_str)
    except (ValueError, TypeError):
        return None

def best_match_against_keywords(texto_item: str, keywords, nome_produto_catalogo=""):
    if not texto_item or not keywords:
        return 0, ""
    
    texto_norm = normalize_text(texto_item)
    best_score = 0
    best_kw = ""
    
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
    
    tem_contexto_lab = any(termo in texto_norm for termo in CONTEXTO_LABORATORIAL)
    if not tem_contexto_lab:
        return 0, ""
    
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

def salvar_produtos(df_editor):
    session = get_session()
    session.query(Produto).delete()
    produtos = []
    for row in df_editor.itertuples(index=False):
        if row[0]:
            produtos.append(Produto(
                nome=row[0],
                palavras_chave=row[1],
                preco_custo=float(row[2]),
                margem_minima=float(row[3]),
                preco_referencia=float(row[4] if len(row) > 4 and row[4] else 0.0),
                fonte_referencia=str(row[5] if len(row) > 5 and row[5] else "")
            ))
    session.bulk_save_objects(produtos)
    session.commit()
    session.close()
    st.success(f"Catálogo atualizado! {len(produtos)} produtos salvos.")

def match_itens(session, licitacao_id, limiar=75):
    licitacao = session.query(Licitacao).filter_by(id=licitacao_id).first()
    produtos = session.query(Produto).all()
    count = 0
    for item in licitacao.itens:
        item_desc = item.descricao or ""
        melhor_match = None
        melhor_score = 0
        for prod in produtos:
            raw_kw = prod.palavras_chave or ""
            keywords = [k.strip() for k in raw_kw.split(',') if k.strip() and len(k.strip()) > 3]
            keywords.append(prod.nome or "")
            score, _ = best_match_against_keywords(item_desc, keywords, nome_produto_catalogo=prod.nome)
            if score > melhor_score:
                melhor_match = prod
                melhor_score = score
        if melhor_match and melhor_score >= limiar:
            item.produto_match_id = melhor_match.id
            item.match_score = melhor_score
            count += 1
        else:
            item.produto_match_id = None
            item.match_score = melhor_score
    session.commit()
    return count
