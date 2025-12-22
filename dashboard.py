import concurrent.futures
import streamlit as st
import pandas as pd
from datetime import datetime, date
import time
import os
import unicodedata
from pathlib import Path
from rapidfuzz import fuzz
from sqlalchemy import func, or_, not_, and_
from io import BytesIO

# --- IMPORTS DOS MÓDULOS ---
from modules.database.database import init_db, get_session, Licitacao, ItemLicitacao, Produto, Configuracao
from modules.finance.bank_models import ExtratoBB, ResumoMensal
from modules.finance.extrato_parser import importar_extrato_bb, processar_texto_extrato
from modules.finance import (
    init_finance_db,
    init_finance_historico_db,
    get_finance_session,
    get_finance_historico_session,
    importar_extrato_historico,
)
from modules.scrapers.pncp_client import PNCPClient
from modules.scrapers.external_scrapers import FemurnScraper, FamupScraper, AmupeScraper, AmaScraper, MaceioScraper, MaceioInvesteScraper, MaceioSaudeScraper
from modules.utils.notifications import WhatsAppNotifier
from modules.ai.smart_analyzer import SmartAnalyzer
from modules.ai.eligibility_checker import EligibilityChecker
from modules.ai.improved_matcher import SemanticMatcher
from modules.ai.licitacao_validator import validar_licitacao_com_ia  # Validador IA
from modules.utils import importer # Import module instead of non-existent class
from modules.utils.cnae_data import get_keywords_by_cnae

from modules.distance_calculator import get_road_distance # Importa calculador de distância
from modules.core.search_engine import SearchEngine
from modules.core.opportunity_collector import prepare_results_for_pipeline
from modules.core.background_search import background_manager  # Busca em background
from modules.core.deep_analyzer import deep_analyzer  # Análise profunda de licitações

# Inicializa Banco
init_db()
init_finance_db()
init_finance_historico_db()

# IA: OpenRouter-only (configurado via Configurações)

st.set_page_config(page_title="Medcal Licitações", layout="wide", page_icon="🏥", initial_sidebar_state="expanded")

# --- CSS INJECTION ---
def local_css(file_name):
    with open(file_name) as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

try:
    local_css("assets/style.css")
except Exception as e:
    st.warning(f"Erro ao carregar estilo: {e}")

# --- UTILITÁRIOS DE TEXTO ---

# --- UTILITÁRIOS DE TEXTO ---
def normalize_text(texto: str) -> str:
    if not texto:
        return ""
    return unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('ASCII').upper()

def safe_parse_date(date_str):
    """Converte string ISO para datetime de forma segura. Retorna None se inválido."""
    if not date_str or not isinstance(date_str, str) or date_str.strip() == "":
        return None
    try:
        return datetime.fromisoformat(date_str)
    except (ValueError, TypeError):
        return None

def best_match_against_keywords(texto_item: str, keywords, nome_produto_catalogo=""):
    """
    Retorna (melhor_score, melhor_keyword) com lógica RIGOROSA para matching.
    REGRA PRINCIPAL: Só dá match se o item for do contexto laboratorial/hospitalar.
    """
    if not texto_item or not keywords:
        return 0, ""
    
    texto_norm = normalize_text(texto_item)
    best_score = 0
    best_kw = ""
    
    # ============================================================
    # ETAPA 1: VERIFICAR SE O ITEM É DO CONTEXTO LABORATORIAL
    # Se não tiver NENHUM termo do universo médico/laboratorial, retorna 0
    # ============================================================
    
    # Termos que indicam contexto LABORATORIAL/HOSPITALAR (baseados nos termos positivos do PNCP)
    CONTEXTO_LABORATORIAL = [
        # Equipamentos e análises
        "HEMATOLOGIA", "BIOQUIMICA", "COAGULACAO", "COAGULAÇÃO", "IMUNOLOGIA", "IONOGRAMA",
        "GASOMETRIA", "POCT", "URINALISE", "URINA", "HEMOGRAMA", "LABORATORIO", "LABORATÓRIO",
        "LABORATORIAL", "ANALISE CLINICA", "ANÁLISE CLÍNICA", "ANALISES CLINICAS", "ANÁLISES CLÍNICAS",
        "CURVA GLICEMICA", "GTT", "GTC", "TOLERANCIA GLICOSE", "DOSAGEM",
        "AMILASE", "ALBUMINA", "BILIRRUBINA", "CALCIO", "FERRO", "URICO", "ÁCIDO ÚRICO", "ACIDO URICO",
        "CLORETO", "COLESTEROL", "HDL", "LDL",
        # Equipamentos
        "ANALISADOR", "EQUIPAMENTO", "CENTRIFUGA", "CENTRÍFUGA", "MICROSCOPIO", "MICROSCÓPIO",
        "AUTOCLAVE", "COAGULOMETRO", "COAGULÔMETRO", "HOMOGENEIZADOR", "AGITADOR",
        # Reagentes e insumos
        "REAGENTE", "REAGENTES", "INSUMO", "INSUMOS", "DILUENTE", "LISANTE", "CALIBRADOR",
        "CONTROLE DE QUALIDADE", "PADRAO", "PADRÃO",
        # Materiais de coleta
        "TUBO", "TUBOS", "COLETA", "VACUO", "VÁCUO", "EDTA", "HEPARINA", "CITRATO",
        "AGULHA", "SERINGA", "LANCETA", "SCALP", "CATETER",
        # Consumíveis hospitalares
        "LUVA", "LUVAS", "MASCARA", "MÁSCARA", "LAMINA", "LÂMINA", "PONTEIRA",
        # Testes e exames
        "TESTE RAPIDO", "TESTE RÁPIDO", "HEMOSTASIA", "HORMONIO", "HORMÔNIO", "TSH", "T4", "T3",
        "GLICOSE", "COLESTEROL", "TRIGLICERIDES", "UREIA", "CREATININA", "TGO", "TGP",
        # Termos gerais médicos
        "HOSPITALAR", "HOSPITALARES", "AMBULATORIAL", "BIOMEDICO", "BIOMÉDICO",
        "SONDA", "EQUIPO", "EQUIPOS", "CANULA", "CÂNULA",
        # Locação/Comodato (termos de modalidade importantes)
        "LOCACAO", "LOCAÇÃO", "COMODATO", "ALUGUEL", "MANUTENCAO PREVENTIVA", "MANUTENÇÃO PREVENTIVA"
    ]
    
    # Verifica se o item tem contexto laboratorial
    tem_contexto_lab = any(termo in texto_norm for termo in CONTEXTO_LABORATORIAL)
    
    # Se NÃO tem nenhum termo de contexto laboratorial, retorna 0 imediatamente
    if not tem_contexto_lab:
        return 0, ""
    
    # ============================================================
    # ETAPA 2: MATCHING COM KEYWORDS DO CATÁLOGO
    # Só chega aqui se o item passou pela validação de contexto
    # ============================================================
    
    # Palavras que indicam Insumo/Consumível
    termos_insumo = ["REAGENTE", "SOLUCAO", "LISANTE", "DILUENTE", "TUBO", "LAMINA", "CLORETO", "ACIDO", "KIT", "TIRA", "FRASCO"]
    
    # Palavras que indicam Equipamento
    termos_equip = ["ANALISADOR", "EQUIPAMENTO", "APARELHO", "HOMOGENEIZADOR", "AGITADOR", "CENTRIFUGA", "MICROSCOPIO", "AUTOCLAVE", "COAGULOMETRO"]
    
    nome_prod_norm = normalize_text(nome_produto_catalogo)
    eh_equipamento_catalogo = any(t in nome_prod_norm for t in termos_equip)
    tem_cara_de_insumo_item = any(t in texto_norm for t in termos_insumo) and not any(t in texto_norm for t in termos_equip)
    
    for kw in keywords:
        if not kw: continue
        kw_norm = normalize_text(kw)
        
        # Ignora palavras muito curtas (menos de 4 caracteres)
        if len(kw_norm) < 4: continue
        
        score = 0
        
        # ============================================================
        # ESTRATÉGIA DE MATCHING RIGOROSA:
        # 1. Match EXATO da keyword no texto = 95 pontos
        # 2. Todas as palavras da keyword presentes = 85 pontos
        # 3. Usa token_set_ratio (compara palavras, não substrings) >= 85 = 75 pontos
        # 4. partial_ratio foi REMOVIDO pois gerava falsos positivos
        # ============================================================
        
        # 1. MATCH EXATO: keyword completa está no texto
        if kw_norm in texto_norm:
            score = 95
        else:
            # 2. MATCH POR PALAVRAS: todas as palavras da keyword estão no texto
            palavras_kw = set(kw_norm.split())
            palavras_texto = set(texto_norm.split())
            palavras_em_comum = palavras_kw.intersection(palavras_texto)
            
            if len(palavras_kw) > 0:
                percentual_match = len(palavras_em_comum) / len(palavras_kw)
                
                if percentual_match >= 1.0:  # 100% das palavras
                    score = 90
                elif percentual_match >= 0.8:  # 80% das palavras
                    score = 80
                elif percentual_match >= 0.6:  # 60% das palavras
                    # 3. Usa token_set_ratio como fallback (mais rigoroso que partial_ratio)
                    token_score = fuzz.token_set_ratio(kw_norm, texto_norm)
                    if token_score >= 90:
                        score = 75
                    elif token_score >= 85:
                        score = 70
                    # Se token_score < 85, score permanece 0 (sem match)
        
        # ============================================================
        # PENALIZAÇÃO CRUZADA (EQUIPAMENTO x INSUMO)
        # Evita que equipamento faça match com reagentes e vice-versa
        # ============================================================
        if eh_equipamento_catalogo and tem_cara_de_insumo_item:
            if not any(ti in kw_norm for ti in termos_insumo):
                score -= 50 
        
        if score > best_score:
            best_score = score
            best_kw = kw
            
    return max(0, best_score), best_kw

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("""
        <div style="padding: 12px 0 16px 0; text-align: center; border-bottom: 1px solid rgba(255,255,255,0.1); margin-bottom: 12px;">
            <div style="font-size: 24px; margin-bottom: 4px;">🏥</div>
            <div style="font-size: 14px; font-weight: 600; color: #ffffff; letter-spacing: -0.02em;">Medcal</div>
            <div style="font-size: 9px; color: rgba(255,255,255,0.5); text-transform: uppercase; letter-spacing: 0.1em;">Gestão de Licitações</div>
        </div>
    """, unsafe_allow_html=True)
    
    # === STATUS DE BUSCA EM BACKGROUND ===
    search_status = background_manager.get_current_status()
    if search_status['status'] == 'running':
        elapsed = search_status.get('elapsed_seconds', 0)
        mins = elapsed // 60
        secs = elapsed % 60
        st.markdown(f"""
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                        padding: 10px; border-radius: 8px; margin-bottom: 12px; text-align: center;">
                <div style="font-size: 20px; margin-bottom: 4px;">🔄</div>
                <div style="font-size: 11px; color: white; font-weight: 500;">Buscando...</div>
                <div style="font-size: 9px; color: rgba(255,255,255,0.7);">{mins}m {secs}s</div>
            </div>
        """, unsafe_allow_html=True)
        
        # Botão de refresh manual (evita loop infinito de st.rerun)
        if st.button("🔄", key="sidebar_refresh", help="Atualizar status"):
            st.rerun()
        
    elif search_status['status'] == 'completed' and search_status.get('finished_at'):
        # Mostra notificação de conclusão por 60 segundos
        finished = search_status['finished_at']
        if isinstance(finished, datetime) and (datetime.now() - finished).seconds < 60:
            st.markdown("""
                <div style="background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); 
                            padding: 10px; border-radius: 8px; margin-bottom: 12px; text-align: center;">
                    <div style="font-size: 20px; margin-bottom: 4px;">✅</div>
                    <div style="font-size: 11px; color: white; font-weight: 500;">Busca Concluída!</div>
                    <div style="font-size: 9px; color: rgba(255,255,255,0.7);">{} novas</div>
                </div>
            """.format(search_status.get('total_novos', 0)), unsafe_allow_html=True)
    
    page = st.radio(
        "Navegação Principal",
        ["📊 Dashboard", "🔍 Buscar", "🎯 Preparar", "🧠 Análise IA", "📦 Catálogo", "💰 Financeiro", "⚙️ Config"],
        label_visibility="collapsed"
    )
    
    # Espaçador para empurrar a versão para o final
    st.markdown("<div style='flex-grow: 1; min-height: 50px;'></div>", unsafe_allow_html=True)
    
    st.markdown("""
        <div style="text-align: center; padding: 16px 0; margin-top: auto;">
            <div style="font-size: 10px; color: rgba(255,255,255,0.3);">v2.2 • 2025</div>
        </div>
    """, unsafe_allow_html=True)

# Mapeamento para manter compatibilidade com os IFs abaixo
page_map = {
    "📊 Dashboard": "Dashboard",
    "🔍 Buscar": "Buscar Licitações",
    "🎯 Preparar": "Preparar Competição",
    "🧠 Análise IA": "🧠 Análise de IA",
    "📦 Catálogo": "Catálogo",
    "💰 Financeiro": "💰 Gestão Financeira",
    "⚙️ Config": "Configurações"
}
page = page_map.get(page, page)

# --- FUNÇÕES AUXILIARES ---
def salvar_produtos(df_editor):
    session = get_session()
    session.query(Produto).delete()

    # Otimização: bulk insert com list comprehension é 10-30x mais rápido
    produtos = []
    for row in df_editor.itertuples(index=False):
        # Acessa por índice: 0=Nome, 1=Palavras-Chave, 2=Preço Custo, 3=Margem, 4=Preço Ref, 5=Fonte
        if row[0]:  # Nome do Produto
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
    """Tenta cruzar itens da licitação com produtos do catálogo com matching RIGOROSO"""
    licitacao = session.query(Licitacao).filter_by(id=licitacao_id).first()
    produtos = session.query(Produto).all()
    
    count = 0
    for item in licitacao.itens:
        item_desc = item.descricao or ""
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
            count += 1
        else:
            item.produto_match_id = None
            item.match_score = melhor_score
            
    session.commit()
    return count


def gerar_relatorio_whatsapp(licitacoes_relevantes, session):
    """
    Gera relatórios compactos para WhatsApp, divididos em múltiplas mensagens.
    Retorna LISTA de mensagens (cada uma com até 10 licitações).
    """
    if not licitacoes_relevantes:
        return []
    
    mensagens = []
    lics_por_msg = 10  # Máximo de licitações por mensagem
    
    # Divide em lotes
    for i in range(0, len(licitacoes_relevantes), lics_por_msg):
        lote = licitacoes_relevantes[i:i + lics_por_msg]
        parte_atual = (i // lics_por_msg) + 1
        total_partes = (len(licitacoes_relevantes) + lics_por_msg - 1) // lics_por_msg
        
        # Cabeçalho
        data_hora = datetime.now().strftime("%d/%m/%Y %H:%M")
        if total_partes > 1:
            linhas = [f"📋 *MEDCAL* ({parte_atual}/{total_partes})", f"🕐 {data_hora}", ""]
        else:
            linhas = [f"📋 *MEDCAL* - {len(licitacoes_relevantes)} oportunidades", f"🕐 {data_hora}", ""]
        
        for idx, lic in enumerate(lote, 1):
            # Extrai dados
            orgao = lic.get('orgao', 'N/A')
            # Limita tamanho do órgão mas mantém informação útil
            if len(orgao) > 35:
                orgao = orgao[:32] + "..."
            uf = lic.get('uf', 'BR')
            modalidade = lic.get('modalidade', 'N/A')
            # Simplifica modalidade
            if 'Pregão' in modalidade or 'Pregao' in modalidade:
                mod_curto = 'PE'
            elif 'Dispensa' in modalidade:
                mod_curto = 'Disp'
            elif 'Emergencial' in modalidade:
                mod_curto = 'Emerg'
            else:
                mod_curto = modalidade[:6]
            
            link = lic.get('link', '')
            
            # Data limite de proposta
            data_enc = lic.get('data_encerramento_proposta')
            if data_enc:
                try:
                    if isinstance(data_enc, str):
                        dt = datetime.fromisoformat(data_enc[:10])
                    else:
                        dt = data_enc
                    prazo = dt.strftime("%d/%m")
                except:
                    prazo = "N/I"
            else:
                prazo = "N/I"
            
            # Itens matched (se houver)
            matched = lic.get('matched_products', [])
            if matched:
                # Pega apenas o primeiro produto e abrevia
                item_str = matched[0][:20]
                if len(matched) > 1:
                    item_str += f" +{len(matched)-1}"
                itens_linha = f"\n   🎯 {item_str}"
            else:
                itens_linha = ""
            
            # Formato compacto:
            # 1. HOSPITAL X (RN) 📅30/11 PE
            #    🎯 Reagente Hematologia
            #    🔗 link
            num_global = i + idx
            linha = f"{num_global}. *{orgao}* ({uf})"
            linha += f"\n   📅 {prazo} | {mod_curto}"
            linha += itens_linha
            linha += f"\n   🔗 {link}"
            
            linhas.append(linha)
            linhas.append("")  # Linha em branco entre licitações
        
        mensagens.append("\n".join(linhas))
    
    return mensagens


def enviar_relatorio_completo(licitacoes, session):
    """
    Envia relatório para todos os contatos configurados.
    Divide em múltiplas mensagens se necessário.
    """
    import json
    import time
    
    if not licitacoes:
        return False
    
    # Busca contatos
    config_contacts = session.query(Configuracao).filter_by(chave='whatsapp_contacts').first()
    
    if not config_contacts or not config_contacts.valor:
        # Tenta formato antigo
        conf_phone = session.query(Configuracao).filter_by(chave='whatsapp_phone').first()
        conf_key = session.query(Configuracao).filter_by(chave='whatsapp_apikey').first()
        
        if conf_phone and conf_key and conf_phone.valor and conf_key.valor:
            contacts_list = [{"nome": "Principal", "phone": conf_phone.valor, "apikey": conf_key.valor}]
        else:
            return False
    else:
        try:
            contacts_list = json.loads(config_contacts.valor)
        except:
            return False
    
    if not contacts_list:
        return False
    
    # Gera relatórios (lista de mensagens)
    mensagens = gerar_relatorio_whatsapp(licitacoes, session)
    if not mensagens:
        return False
    
    # Envia para todos os contatos
    enviados = 0
    for contact in contacts_list:
        try:
            notifier = WhatsAppNotifier(contact.get('phone'), contact.get('apikey'))
            for idx, msg in enumerate(mensagens):
                if notifier.enviar_mensagem(msg):
                    enviados += 1
                # Pausa entre mensagens para evitar bloqueio (2 segundos)
                if idx < len(mensagens) - 1:
                    time.sleep(2)
        except Exception as e:
            print(f"Erro ao enviar para {contact.get('nome')}: {e}")
    
    return enviados > 0


def filtrar_itens_negativos(itens_api, termos_negativos):
    """
    Filtra itens que contenham termos negativos (enxoval, berço, etc).
    Retorna apenas itens válidos.
    """
    if not itens_api:
        return []
    
    itens_validos = []
    termos_neg_norm = [normalize_text(t) for t in termos_negativos]
    
    for item in itens_api:
        desc = item.get('descricao', '')
        desc_norm = normalize_text(desc)
        
        # Verifica se contém termo negativo
        tem_negativo = any(t in desc_norm for t in termos_neg_norm)
        
        if not tem_negativo:
            itens_validos.append(item)
    
    return itens_validos


def enviar_notificacao_scraper(resultados, fonte_nome):
    """Envia notificação WhatsApp para licitações encontradas em scrapers individuais"""
    if not resultados:
        return
    
    try:
        session = get_session()
        config_contacts = session.query(Configuracao).filter_by(chave='whatsapp_contacts').first()
        
        if not config_contacts or not config_contacts.valor:
            session.close()
            return
        
        import json
        import re
        try:
            contacts_list = json.loads(config_contacts.valor)
        except:
            session.close()
            return
        
        if not contacts_list:
            session.close()
            return
        
        # Monta mensagem para cada licitação (limita a 5 para evitar spam e erro 503)
        data_hoje = datetime.now().strftime('%d/%m/%Y')
        
        for lic in resultados[:5]:
            orgao = lic.get('orgao', 'Órgão não informado')
            modalidade = lic.get('modalidade', '')
            objeto_raw = lic.get('objeto', '')
            link = lic.get('link', '')
            
            # Remove prefixos de IA se existirem
            objeto = objeto_raw
            if '[IA]' in objeto:
                objeto = re.sub(r'\[IA\][^\n]*\n?', '', objeto)
            
            # Extrai tipo e número do pregão/edital
            tipo_licitacao = ""
            num_edital = ""
            
            # Busca padrões como "PREGÃO ELETRÔNICO" ou "PE-040/2025" ou "PE nº 040/2025"
            texto_busca = (objeto + " " + modalidade).upper()
            # Normaliza acentos para facilitar busca
            texto_busca_norm = texto_busca.replace('Ã', 'A').replace('Ô', 'O').replace('Ê', 'E').replace('Í', 'I').replace('Ó', 'O')
            
            # Tipo de licitação - ordem de prioridade
            if "PREGAO ELETRONICO" in texto_busca_norm or "PE-" in texto_busca_norm or "PE " in texto_busca_norm:
                tipo_licitacao = "Pregão Eletrônico"
            elif "PREGAO PRESENCIAL" in texto_busca_norm or "PP-" in texto_busca_norm or "PP " in texto_busca_norm:
                tipo_licitacao = "Pregão Presencial"
            elif "DISPENSA ELETRONICA" in texto_busca_norm:
                tipo_licitacao = "Dispensa Eletrônica"
            elif "DISPENSA" in texto_busca_norm:
                tipo_licitacao = "Dispensa"
            elif "CHAMADA PUBLICA" in texto_busca_norm or "CHAMAMENTO" in texto_busca_norm or "CREDENCIAMENTO" in texto_busca_norm:
                tipo_licitacao = "Chamada Pública"
            elif "CONCORRENCIA" in texto_busca_norm:
                tipo_licitacao = "Concorrência"
            elif "TOMADA DE PRECO" in texto_busca_norm:
                tipo_licitacao = "Tomada de Preços"
            elif "PREGAO" in texto_busca_norm:
                tipo_licitacao = "Pregão Eletrônico"  # Default para pregão
            
            # Número do edital - vários padrões (melhorado)
            patterns_edital = [
                r'PE[- ]?N?[ºo°]?\s*0*(\d+)[\/\-](\d+)',  # PE-040/2025, PE nº 040/2025
                r'PP[- ]?N?[ºo°]?\s*0*(\d+)[\/\-](\d+)',  # PP-040/2025
                r'PREGAO[^\d]{0,20}N?[ºo°]?\s*0*(\d+)[\/\-](\d+)',  # PREGÃO nº 040/2025
                r'REGISTRO DE PRECO[^\d]{0,10}N?[ºo°]?\s*0*(\d+)[\/\-](\d+)',
                r'EDITAL[^\d]{0,10}N?[ºo°]?\s*0*(\d+)[\/\-](\d+)',
            ]
            
            for pattern in patterns_edital:
                match = re.search(pattern, texto_busca_norm)
                if match:
                    num_edital = f"{match.group(1)}/{match.group(2)}"
                    break
            
            # Extrai o objeto limpo (primeira parte relevante)
            objeto_limpo = objeto
            # Remove quebras de linha múltiplas e limpa
            objeto_limpo = re.sub(r'\n+', ' ', objeto_limpo)
            objeto_limpo = re.sub(r'\s+', ' ', objeto_limpo).strip()
            
            # Tenta extrair apenas a parte do objeto
            match_objeto = re.search(r'(?:para eventual|para\s+)?(?:CONTRATACAO|AQUISICAO|REGISTRO DE PRECOS?)[^\w]*(?:DE\s+)?(.+?)(?:O PROCEDIMENTO|O EDITAL|EM ATENDIMENTO|DATA|LOCAL|,\s*EM|$)', objeto_limpo, re.IGNORECASE)
            if match_objeto:
                objeto_limpo = match_objeto.group(1).strip()
                # Remove pontuação final
                objeto_limpo = re.sub(r'[,;.]+$', '', objeto_limpo).strip()
            
            # Se ainda muito longo, pega só início
            if len(objeto_limpo) > 150:
                objeto_limpo = objeto_limpo[:150] + "..."
            
            # Monta linha do tipo/número
            linha_tipo = ""
            if tipo_licitacao and num_edital:
                linha_tipo = f"📋 *{tipo_licitacao} nº {num_edital}*"
            elif tipo_licitacao:
                linha_tipo = f"📋 *{tipo_licitacao}*"
            elif num_edital:
                linha_tipo = f"📋 *Edital nº {num_edital}*"
            
            msg = f"""📢 *Atualizações*

🏛️ *{orgao}*
{linha_tipo}
📝 {objeto_limpo}

📰 {fonte_nome} {data_hoje}
🔗 {link}"""
            
            # Envia para todos os contatos (com delay para evitar 503)
            for contact in contacts_list:
                try:
                    notifier = WhatsAppNotifier(contact.get('phone'), contact.get('apikey'))
                    notifier.enviar_mensagem(msg)
                    import time
                    time.sleep(2)  # Delay de 2 segundos entre mensagens
                except Exception as e:
                    print(f"Erro ao notificar {contact.get('nome')}: {e}")
            
            # Delay entre licitações diferentes
            import time
            time.sleep(1)
        
        session.close()
        
    except Exception as e:
        print(f"Erro ao enviar notificação: {e}")


def processar_resultados(resultados_raw, notificar=False, fonte_nome=""):
    """Processa e salva uma lista de resultados brutos (pipeline consolidado)."""
    if not resultados_raw:
        st.warning("Nenhum resultado encontrado para processar.")
        return
    
    # Envia notificação se solicitado
    if notificar and resultados_raw:
        enviar_notificacao_scraper(resultados_raw, fonte_nome)

    resultados_preparados = prepare_results_for_pipeline(resultados_raw)
    engine = SearchEngine()
    details = engine.run_search_pipeline(resultados_preparados, return_details=True, send_immediate_alerts=False)
    novos = int((details or {}).get("novos") or 0)
    alerts = (details or {}).get("alerts") or []

    st.success(f"Busca finalizada! {novos} novas licitações importadas.")

    if alerts:
        st.info(f"📱 Enviando relatório com {len(alerts)} licitações relevantes...")
        session = get_session()
        try:
            if enviar_relatorio_completo(alerts, session):
                st.success("✅ Relatório enviado via WhatsApp!")
            else:
                st.warning("⚠️ Não foi possível enviar relatório. Verifique as configurações de WhatsApp.")
        finally:
            session.close()

# --- PÁGINAS ---

if page == "Catálogo":
    st.header("📦 Catálogo de Produtos")
    st.info("Cadastro dos produtos. O sistema usará as 'Palavras-Chave' para encontrar as Licitações.")
    
    session = get_session()
    produtos = session.query(Produto).all()
    session.close()
    
    data = []
    for p in produtos:
        data.append({
            "nome": p.nome or "",
            "palavras_chave": p.palavras_chave or "",
            "preco_custo": float(p.preco_custo or 0.0),
            "margem_minima": float(p.margem_minima or 30.0),
            "preco_referencia": float(p.preco_referencia or 0.0),
            "fonte_referencia": p.fonte_referencia or ""
        })
    
    if not data:
        data = [{
            "nome": "", 
            "palavras_chave": "", 
            "preco_custo": 0.0, 
            "margem_minima": 30.0,
            "preco_referencia": 0.0,
            "fonte_referencia": ""
        }]
        
    df = pd.DataFrame(data)
    
    # Configuração explícita das colunas para evitar erros de renderização
    edited_df = st.data_editor(
        df,
        column_config={
            "nome": st.column_config.TextColumn("Nome do Produto", required=True, width="medium"),
            "palavras_chave": st.column_config.TextColumn("Palavras-Chave", help="Separadas por vírgula", width="medium"),
            "preco_custo": st.column_config.NumberColumn("Preço de Custo", min_value=0.0, format="R$ %.2f", required=True, width="small"),
            "margem_minima": st.column_config.NumberColumn("Margem (%)", min_value=0.0, format="%.1f%%", width="small"),
            "preco_referencia": st.column_config.NumberColumn("Preço Referência", min_value=0.0, format="R$ %.2f", width="small"),
            "fonte_referencia": st.column_config.TextColumn("Fonte Referência", width="small")
        },
        num_rows="dynamic",
        width='stretch',
        key="editor_catalogo"
    )
    
    if st.button("💾 Salvar Alterações", key="btn_salvar_catalogo"):
        # Renomeia colunas para compatibilidade com a função de salvar existente
        df_to_save = edited_df.rename(columns={
            "nome": "Nome do Produto",
            "palavras_chave": "Palavras-Chave",
            "preco_custo": "Preço de Custo",
            "margem_minima": "Margem (%)",
            "preco_referencia": "Preço Referência",
            "fonte_referencia": "Fonte Referência"
        })
        salvar_produtos(df_to_save)

elif page == "Buscar Licitações":
    st.header("🔍 Buscar Novas Oportunidades")
    
    # Período fixo de busca (60 dias é suficiente para capturar todos os pregões abertos)
    dias = 60

    estados = st.multiselect("Estados:", ['RN', 'PB', 'PE', 'AL', 'CE', 'BA'], default=['RN', 'PB', 'PE', 'AL'])
    
    # --- PNCP (Fonte Principal) ---
    st.markdown("""
    <div style="background: linear-gradient(135deg, #1e3a5f 0%, #0f172a 100%); border-radius: 12px; padding: 16px; margin: 16px 0;">
        <div style="display: flex; align-items: center; gap: 12px;">
            <div style="font-size: 24px;">🏛️</div>
            <div>
                <div style="font-weight: 600; color: white; font-size: 14px;">PNCP - Portal Nacional</div>
                <div style="font-size: 12px; color: rgba(255,255,255,0.7);">Fonte oficial do Governo Federal</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    use_pncp = st.checkbox("Incluir PNCP na busca completa", value=True, label_visibility="collapsed")
    
    st.markdown("---")
    st.markdown("#### 📰 Diários Oficiais Municipais")
    st.caption("Clique no botão ▶️ para buscar apenas naquela fonte")
    
    # --- Grid de Scrapers com visual moderno ---
    col_ext1, col_ext2, col_ext3 = st.columns(3)
    
    # --- FEMURN (RN) ---
    with col_ext1:
        st.markdown("""
        <div style="background: white; border: 1px solid #e5e7eb; border-radius: 12px; padding: 16px; margin: 4px 0; transition: all 0.2s;">
            <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 12px;">
                <div style="width: 40px; height: 40px; background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%); border-radius: 10px; display: flex; align-items: center; justify-content: center;">
                    <span style="font-size: 18px;">📰</span>
                </div>
                <div>
                    <div style="font-weight: 600; font-size: 14px; color: #111827;">FEMURN</div>
                    <div style="font-size: 12px; color: #6b7280;">Rio Grande do Norte</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        col_chk, col_btn = st.columns([0.6, 0.4])
        with col_chk:
            use_femurn = st.checkbox("Incluir", value=True, key="chk_femurn", label_visibility="collapsed")
        with col_btn:
            if st.button("▶️ Buscar", key="btn_femurn", use_container_width=True):
                with st.status("🔄 Buscando no FEMURN...", expanded=True) as status:
                    st.write("📥 Baixando PDF do Diário Oficial...")
                    client = PNCPClient()
                    scraper = FemurnScraper()
                    res = scraper.buscar_oportunidades(client.TERMOS_PRIORITARIOS, termos_negativos=client.TERMOS_NEGATIVOS_PADRAO)
                    if res:
                        st.write(f"✅ Encontradas **{len(res)}** licitações!")
                        for r in res[:3]:
                            st.success(f"🏛️ {r.get('orgao', '')[:50]}")
                    else:
                        st.write("😕 Nenhuma licitação encontrada hoje")
                    processar_resultados(res, notificar=True, fonte_nome="FEMURN")
                    status.update(label=f"✅ FEMURN: {len(res)} encontradas", state="complete")

    # --- FAMUP (PB) ---
    with col_ext2:
        st.markdown("""
        <div style="background: white; border: 1px solid #e5e7eb; border-radius: 12px; padding: 16px; margin: 4px 0;">
            <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 12px;">
                <div style="width: 40px; height: 40px; background: linear-gradient(135deg, #8b5cf6 0%, #6d28d9 100%); border-radius: 10px; display: flex; align-items: center; justify-content: center;">
                    <span style="font-size: 18px;">📰</span>
                </div>
                <div>
                    <div style="font-weight: 600; font-size: 14px; color: #111827;">FAMUP</div>
                    <div style="font-size: 12px; color: #6b7280;">Paraíba</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        col_chk, col_btn = st.columns([0.6, 0.4])
        with col_chk:
            use_famup = st.checkbox("Incluir", value=True, key="chk_famup", label_visibility="collapsed")
        with col_btn:
            if st.button("▶️ Buscar", key="btn_famup", use_container_width=True):
                with st.status("🔄 Buscando no FAMUP...", expanded=True) as status:
                    st.write("📥 Baixando PDF do Diário Oficial...")
                    client = PNCPClient()
                    scraper = FamupScraper()
                    res = scraper.buscar_oportunidades(client.TERMOS_PRIORITARIOS, termos_negativos=client.TERMOS_NEGATIVOS_PADRAO)
                    if res:
                        st.write(f"✅ Encontradas **{len(res)}** licitações!")
                        for r in res[:3]:
                            st.success(f"🏛️ {r.get('orgao', '')[:50]}")
                    else:
                        st.write("😕 Nenhuma licitação encontrada hoje")
                    processar_resultados(res, notificar=True, fonte_nome="FAMUP")
                    status.update(label=f"✅ FAMUP: {len(res)} encontradas", state="complete")

    # --- AMUPE (PE) ---
    with col_ext3:
        st.markdown("""
        <div style="background: white; border: 1px solid #e5e7eb; border-radius: 12px; padding: 16px; margin: 4px 0;">
            <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 12px;">
                <div style="width: 40px; height: 40px; background: linear-gradient(135deg, #ec4899 0%, #be185d 100%); border-radius: 10px; display: flex; align-items: center; justify-content: center;">
                    <span style="font-size: 18px;">📰</span>
                </div>
                <div>
                    <div style="font-weight: 600; font-size: 14px; color: #111827;">AMUPE</div>
                    <div style="font-size: 12px; color: #6b7280;">Pernambuco</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        col_chk, col_btn = st.columns([0.6, 0.4])
        with col_chk:
            use_amupe = st.checkbox("Incluir", value=True, key="chk_amupe", label_visibility="collapsed")
        with col_btn:
            if st.button("▶️ Buscar", key="btn_amupe", use_container_width=True):
                with st.status("🔄 Buscando no AMUPE...", expanded=True) as status:
                    st.write("📥 Baixando PDF do Diário Oficial...")
                    client = PNCPClient()
                    scraper = AmupeScraper()
                    res = scraper.buscar_oportunidades(client.TERMOS_PRIORITARIOS, termos_negativos=client.TERMOS_NEGATIVOS_PADRAO)
                    if res:
                        st.write(f"✅ Encontradas **{len(res)}** licitações!")
                        for r in res[:3]:
                            st.success(f"🏛️ {r.get('orgao', '')[:50]}")
                    else:
                        st.write("😕 Nenhuma licitação encontrada hoje")
                    processar_resultados(res, notificar=True, fonte_nome="AMUPE")
                    status.update(label=f"✅ AMUPE: {len(res)} encontradas", state="complete")

    # --- ALAGOAS ---
    st.markdown("##### 🟠 Alagoas")
    col_al1, col_al2, col_al3, col_al4 = st.columns(4)
    
    with col_al1:
        st.markdown("""<div style="background: white; border: 1px solid #e5e7eb; border-radius: 10px; padding: 12px; text-align: center;">
            <div style="font-weight: 600; font-size: 13px; color: #111827;">AMA</div>
            <div style="font-size: 11px; color: #6b7280;">Municípios AL</div>
        </div>""", unsafe_allow_html=True)
        use_ama = st.checkbox("Incluir", value=True, key="chk_ama", label_visibility="collapsed")
        if st.button("▶️", key="btn_ama", use_container_width=True):
            with st.status("🔄 Buscando no AMA...", expanded=True) as status:
                client = PNCPClient()
                scraper = AmaScraper()
                res = scraper.buscar_oportunidades(client.TERMOS_PRIORITARIOS, termos_negativos=client.TERMOS_NEGATIVOS_PADRAO)
                if res:
                    for r in res[:3]:
                        st.success(f"🏛️ {r.get('orgao', '')[:40]}")
                processar_resultados(res, notificar=True, fonte_nome="AMA")
                status.update(label=f"✅ AMA: {len(res)}", state="complete")

    with col_al2:
        st.markdown("""<div style="background: white; border: 1px solid #e5e7eb; border-radius: 10px; padding: 12px; text-align: center;">
            <div style="font-weight: 600; font-size: 13px; color: #111827;">Maceió</div>
            <div style="font-size: 11px; color: #6b7280;">Capital AL</div>
        </div>""", unsafe_allow_html=True)
        use_maceio = st.checkbox("Incluir", value=True, key="chk_maceio", label_visibility="collapsed")
        if st.button("▶️", key="btn_maceio", use_container_width=True):
            with st.status("🔄 Buscando em Maceió...", expanded=True) as status:
                client = PNCPClient()
                scraper = MaceioScraper()
                res = scraper.buscar_oportunidades(client.TERMOS_PRIORITARIOS, termos_negativos=client.TERMOS_NEGATIVOS_PADRAO)
                if res:
                    for r in res[:3]:
                        st.success(f"🏛️ {r.get('orgao', '')[:40]}")
                processar_resultados(res, notificar=True, fonte_nome="Maceió")
                status.update(label=f"✅ Maceió: {len(res)}", state="complete")

    with col_al3:
        st.markdown("""<div style="background: white; border: 1px solid #e5e7eb; border-radius: 10px; padding: 12px; text-align: center;">
            <div style="font-weight: 600; font-size: 13px; color: #111827;">Investe</div>
            <div style="font-size: 11px; color: #6b7280;">Maceió</div>
        </div>""", unsafe_allow_html=True)
        use_maceio_investe = st.checkbox("Incluir", value=True, key="chk_maceio_inv", label_visibility="collapsed")
        if st.button("▶️", key="btn_maceio_inv", use_container_width=True):
            with st.status("🔄 Buscando em Maceió Investe...", expanded=True) as status:
                client = PNCPClient()
                scraper = MaceioInvesteScraper()
                res = scraper.buscar_oportunidades(client.TERMOS_PRIORITARIOS, termos_negativos=client.TERMOS_NEGATIVOS_PADRAO)
                if res:
                    for r in res[:3]:
                        st.success(f"🏛️ {r.get('orgao', '')[:40]}")
                processar_resultados(res, notificar=True, fonte_nome="Maceió Investe")
                status.update(label=f"✅ Investe: {len(res)}", state="complete")

    with col_al4:
        st.markdown("""<div style="background: white; border: 1px solid #e5e7eb; border-radius: 10px; padding: 12px; text-align: center;">
            <div style="font-weight: 600; font-size: 13px; color: #111827;">Saúde</div>
            <div style="font-size: 11px; color: #6b7280;">Maceió</div>
        </div>""", unsafe_allow_html=True)
        use_maceio_saude = st.checkbox("Incluir", value=True, key="chk_maceio_saude", label_visibility="collapsed")
        if st.button("▶️", key="btn_maceio_saude", use_container_width=True):
            with st.status("🔄 Buscando em Maceió Saúde...", expanded=True) as status:
                client = PNCPClient()
                scraper = MaceioSaudeScraper()
                res = scraper.buscar_oportunidades(client.TERMOS_PRIORITARIOS, termos_negativos=client.TERMOS_NEGATIVOS_PADRAO)
                if res:
                    for r in res[:3]:
                        st.success(f"🏛️ {r.get('orgao', '')[:40]}")
                processar_resultados(res, notificar=True, fonte_nome="Maceió Saúde")
                status.update(label=f"✅ Saúde: {len(res)}", state="complete")

    st.markdown("---")
    
    # Filtro de futuro agora é MANDATÓRIO
    filtro_futuro = True

    # === STATUS DA BUSCA EM BACKGROUND ===
    search_status = background_manager.get_current_status()
    
    if search_status['status'] == 'running':
        st.info(f"""
        🔄 **Busca em andamento...**  
        {search_status.get('message', '')}
        
        Você pode navegar pelo sistema normalmente. A busca continua em segundo plano.
        """)
        
        col_cancel, col_refresh = st.columns([1, 1])
        with col_cancel:
            if st.button("❌ Cancelar Busca", type="secondary"):
                result = background_manager.cancel_search()
                st.warning(result['message'])
                time.sleep(1)
                st.rerun()
        with col_refresh:
            if st.button("🔄 Atualizar Status"):
                st.rerun()
                
    elif search_status['status'] == 'completed' and search_status.get('finished_at'):
        finished = search_status['finished_at']
        if isinstance(finished, datetime):
            tempo_desde = (datetime.now() - finished).seconds
            if tempo_desde < 300:  # Últimos 5 minutos
                st.success(f"""
                ✅ **Busca concluída!**  
                {search_status.get('total_novos', 0)} novas licitações importadas.  
                Finalizado há {tempo_desde // 60} min {tempo_desde % 60}s.
                """)
    
    elif search_status['status'] == 'error':
        st.error(f"❌ Última busca falhou: {search_status.get('resumo', 'Erro desconhecido')}")
    
    st.divider()
    
    # Monta lista de fontes selecionadas
    fontes_selecionadas = []
    if use_pncp:
        fontes_selecionadas.append('pncp')
    if use_femurn:
        fontes_selecionadas.append('femurn')
    if use_famup:
        fontes_selecionadas.append('famup')
    if use_amupe:
        fontes_selecionadas.append('amupe')
    if use_ama:
        fontes_selecionadas.append('ama')
    if use_maceio:
        fontes_selecionadas.append('maceio')
    if use_maceio_investe:
        fontes_selecionadas.append('maceio_investe')
    if use_maceio_saude:
        fontes_selecionadas.append('maceio_saude')
    
    # Botão principal de busca
    col_btn1, col_btn2 = st.columns([2, 1])
    
    with col_btn1:
        btn_disabled = search_status['status'] == 'running'
        btn_label = f"🚀 Iniciar Busca ({len(fontes_selecionadas)} fonte{'s' if len(fontes_selecionadas) != 1 else ''})"
        
        if not fontes_selecionadas:
            st.warning("⚠️ Selecione pelo menos uma fonte de busca")
        elif st.button(btn_label, type="primary", disabled=btn_disabled, use_container_width=True):
            result = background_manager.start_search(dias=60, estados=estados, fontes=fontes_selecionadas)
            
            if result['success']:
                st.success(f"""
                ✅ **{result['message']}**  
                
                A busca está rodando em **segundo plano**. Você pode:
                - Navegar para outras páginas
                - Ver o status no indicador do menu lateral
                - Voltar aqui para acompanhar o progresso
                """)
                time.sleep(1)
                st.rerun()
            else:
                st.warning(result['message'])
    
    with col_btn2:
        st.caption("A busca roda em background. Você pode navegar pelo sistema.")

    st.divider()
    
    # === BOTÃO MANUAL PARA ENVIAR RELATÓRIO ===
    st.markdown("#### 📱 Relatório WhatsApp")
    col_rel1, col_rel2 = st.columns([3, 1])
    with col_rel1:
        st.caption("Envia um relatório compacto com todas as licitações relevantes do banco.")
    with col_rel2:
        if st.button("📤 Enviar Relatório", key="btn_enviar_relatorio"):
            session = get_session()
            # Busca licitações com prazo aberto e que tenham matches
            licitacoes_db = session.query(Licitacao).filter(
                Licitacao.data_encerramento_proposta >= datetime.now()
            ).order_by(Licitacao.data_encerramento_proposta.asc()).all()
            
            # Monta lista no formato esperado pela função de relatório
            lics_para_relatorio = []
            for lic in licitacoes_db:
                # Verifica se tem itens com match
                itens_match = [i for i in lic.itens if i.produto_match_id is not None]
                matched_products = list(set([i.produto_match.nome for i in itens_match])) if itens_match else []
                
                lics_para_relatorio.append({
                    "orgao": lic.orgao,
                    "uf": lic.uf,
                    "modalidade": lic.modalidade,
                    "data_encerramento_proposta": lic.data_encerramento_proposta.isoformat() if lic.data_encerramento_proposta else None,
                    "matched_products": matched_products,
                    "link": lic.link
                })
            
            if lics_para_relatorio:
                if enviar_relatorio_completo(lics_para_relatorio, session):
                    st.success(f"✅ Relatório com {len(lics_para_relatorio)} licitações enviado!")
                else:
                    st.error("❌ Erro ao enviar. Verifique as configurações de WhatsApp ou veja os logs para mais detalhes.")
            else:
                st.warning("Nenhuma licitação com prazo aberto encontrada.")
            
            session.close()
    
    st.divider()
    with st.expander("Limpeza do banco de dados"):
        st.warning("Isso apagará todas as licitações NÃO SALVAS (que não foram fixadas com '⭐ Fixar').")
        if st.button("Limpar Histórico de Licitações"):
            session = get_session()
            
            # Seleciona IDs para exclusão (preserva 'Salva')
            to_delete = session.query(Licitacao.id).filter(Licitacao.status != 'Salva').all()
            ids_to_delete = [row[0] for row in to_delete]
            
            if ids_to_delete:
                # Apaga itens filhos primeiro (segurança contra falha de cascade)
                session.query(ItemLicitacao).filter(ItemLicitacao.licitacao_id.in_(ids_to_delete)).delete(synchronize_session=False)
                # Apaga licitações
                session.query(Licitacao).filter(Licitacao.id.in_(ids_to_delete)).delete(synchronize_session=False)
                
                session.commit()
                st.success(f"Limpeza concluída! {len(ids_to_delete)} registros removidos. Itens 'Salvas' foram mantidos.")
            else:
                st.info("Nada para limpar (banco vazio ou todos os itens estão Salvos).")
            
            session.close()
            time.sleep(1)
            st.rerun()

elif page == "Preparar Competição":
    st.header("🎯 Preparar para Competir")
    st.info("Selecione licitações **fixadas** (⭐) para análise profunda. A IA lerá todos os anexos e preparará um relatório completo.")
    
    session = get_session()
    
    # Busca apenas licitações SALVAS (fixadas)
    licitacoes_salvas = session.query(Licitacao).filter_by(status='Salva').order_by(Licitacao.data_encerramento_proposta.asc()).all()
    
    if not licitacoes_salvas:
        st.warning("Nenhuma licitação fixada. Vá ao Dashboard e clique em ⭐ Fixar nas licitações de interesse.")
    else:
        st.success(f"📌 {len(licitacoes_salvas)} licitações fixadas para análise")
        
        # Lista de licitações para selecionar
        for lic in licitacoes_salvas:
            # Verifica se já tem análise
            cached_analysis = deep_analyzer.get_cached_analysis(lic.id)
            
            # Card da licitação
            with st.expander(f"{'✅' if cached_analysis else '⏳'} {lic.orgao} ({lic.uf}) - {lic.modalidade}", expanded=False):
                col_info, col_action = st.columns([3, 1])
                
                with col_info:
                    st.markdown(f"**Objeto:** {lic.objeto[:200]}...")
                    if lic.data_encerramento_proposta:
                        dias = (lic.data_encerramento_proposta - datetime.now()).days
                        st.markdown(f"⏰ **Prazo:** {lic.data_encerramento_proposta.strftime('%d/%m/%Y')} ({dias} dias)")
                    st.markdown(f"🔗 [Abrir no Portal]({lic.link})")
                
                with col_action:
                    if cached_analysis:
                        st.markdown(f"**Score:** {cached_analysis.score_viabilidade}/100")
                        st.markdown(f"**Recomendação:** {cached_analysis.recomendacao_final}")
                
                # Botão de análise
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button("🔍 Analisar Profundamente", key=f"analyze_{lic.id}", type="primary"):
                        with st.spinner("🤖 Baixando anexos e analisando com IA... Isso pode levar alguns minutos."):
                            result = deep_analyzer.analyze(lic.id, force_refresh=True)
                            if result:
                                st.success("✅ Análise concluída!")
                                st.rerun()
                            else:
                                st.error("❌ Erro na análise. Verifique se a IA (OpenRouter) está configurada.")
                
                with col_btn2:
                    if cached_analysis:
                        if st.button("🔄 Refazer Análise", key=f"refresh_{lic.id}"):
                            with st.spinner("Refazendo análise..."):
                                result = deep_analyzer.analyze(lic.id, force_refresh=True)
                                st.rerun()
                
                # Mostra resultado da análise se existir
                if cached_analysis:
                    st.divider()
                    
                    # Score visual
                    score = cached_analysis.score_viabilidade
                    if score >= 70:
                        score_color = "🟢"
                    elif score >= 40:
                        score_color = "🟡"
                    else:
                        score_color = "🔴"
                    
                    st.markdown(f"""
                    ### {score_color} Viabilidade: {score}/100
                    **Recomendação:** `{cached_analysis.recomendacao_final}`
                    
                    **Justificativa:** {cached_analysis.justificativa}
                    """)
                    
                    # Tabs para detalhes
                    tab1, tab2, tab3, tab4 = st.tabs(["📋 Resumo", "🚫 Impedimentos", "📄 Documentos", "✅ Próximos Passos"])
                    
                    with tab1:
                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown(f"""
                            **Resumo do Objeto:**  
                            {cached_analysis.resumo_objeto}
                            
                            **Valor Total Estimado:** R$ {cached_analysis.valor_total_estimado:,.2f}  
                            **Prazo de Entrega:** {cached_analysis.prazo_entrega}  
                            **Local:** {cached_analysis.local_entrega}
                            """)
                        with col2:
                            st.markdown(f"""
                            **Total de Itens:** {cached_analysis.total_itens}  
                            **Itens Compatíveis:** {cached_analysis.itens_compativeis}  
                            **PDFs Analisados:** {len(cached_analysis.pdf_analisados)}
                            """)
                            if cached_analysis.pdf_analisados:
                                for pdf in cached_analysis.pdf_analisados:
                                    st.caption(f"📄 {pdf}")
                        
                        # Pontos Fortes e Fracos
                        col_f, col_fr = st.columns(2)
                        with col_f:
                            st.markdown("**💪 Pontos Fortes:**")
                            for p in cached_analysis.pontos_fortes:
                                st.markdown(f"- {p}")
                        with col_fr:
                            st.markdown("**⚠️ Pontos Fracos:**")
                            for p in cached_analysis.pontos_fracos:
                                st.markdown(f"- {p}")
                    
                    with tab2:
                        if cached_analysis.impedimentos:
                            st.error("**🚫 Impedimentos Identificados:**")
                            for imp in cached_analysis.impedimentos:
                                st.markdown(f"- ❌ {imp}")
                        else:
                            st.success("✅ Nenhum impedimento grave identificado")
                        
                        st.divider()
                        
                        if cached_analysis.riscos:
                            st.warning("**⚠️ Riscos:**")
                            for r in cached_analysis.riscos:
                                st.markdown(f"- {r}")
                    
                    with tab3:
                        st.markdown("**📋 Requisitos de Habilitação:**")
                        for req in cached_analysis.requisitos_habilitacao:
                            st.markdown(f"- {req}")
                        
                        st.divider()
                        
                        st.markdown("**📄 Documentos Necessários:**")
                        for doc in cached_analysis.documentos_necessarios:
                            st.checkbox(doc, key=f"doc_{lic.id}_{hash(doc)}")
                    
                    with tab4:
                        st.markdown("**✅ Próximos Passos:**")
                        for i, passo in enumerate(cached_analysis.proximos_passos, 1):
                            st.markdown(f"{i}. {passo}")
                        
                        st.divider()
                        
                        # Botões de ação final
                        col_a1, col_a2, col_a3 = st.columns(3)
                        with col_a1:
                            if st.button("📝 Preparar Proposta", key=f"proposta_{lic.id}", type="primary"):
                                st.info("Funcionalidade em desenvolvimento: Geração automática de proposta")
                        with col_a2:
                            if st.button("📧 Exportar Análise", key=f"export_{lic.id}"):
                                # Gera texto para copiar
                                export_text = f"""
ANÁLISE DE LICITAÇÃO - MEDCAL FARMA

Órgão: {lic.orgao} ({lic.uf})
Modalidade: {lic.modalidade}
Objeto: {cached_analysis.resumo_objeto}
Score: {cached_analysis.score_viabilidade}/100
Recomendação: {cached_analysis.recomendacao_final}

IMPEDIMENTOS:
{chr(10).join(['- ' + i for i in cached_analysis.impedimentos]) or 'Nenhum'}

PRÓXIMOS PASSOS:
{chr(10).join([f'{i+1}. {p}' for i, p in enumerate(cached_analysis.proximos_passos)])}
"""
                                st.text_area("Copie o texto:", export_text, height=300)
                        with col_a3:
                            if st.button("❌ Descartar", key=f"descartar_{lic.id}"):
                                lic.status = 'Ignorada'
                                session.commit()
                                st.warning("Licitação marcada como ignorada")
                                time.sleep(1)
                                st.rerun()
    
    session.close()

elif page == "🧠 Análise de IA":
    st.header("🧠 Análise Inteligente de Licitações")
    st.info("Use a Inteligência Artificial para analisar a viabilidade, riscos e elegibilidade dos editais.")

    session = get_session()
    # Lista licitações para análise (apenas as que não foram ignoradas/perdidas)
    licitacoes = session.query(Licitacao).filter(Licitacao.status.in_(['Nova', 'Em Análise', 'Participar'])).order_by(Licitacao.data_publicacao.desc()).all()
    
    if not licitacoes:
        st.warning("Nenhuma licitação disponível para análise.")
    else:
        lic_dict = {f"{l.id} - {l.orgao} ({l.modalidade})": l for l in licitacoes}
        selected_lic_key = st.selectbox("Selecione uma Licitação para Analisar:", list(lic_dict.keys()))
        
        if selected_lic_key:
            lic = lic_dict[selected_lic_key]
            
            # Exibe detalhes básicos
            with st.expander("Detalhes da Licitação", expanded=False):
                st.write(f"**Objeto:** {lic.objeto}")
                st.write(f"**Link:** {lic.link}")
                st.write(f"**Data:** {lic.data_publicacao}")
            
            if st.button("🤖 Gerar Análise Completa (IA)"):
                with st.spinner("A IA está lendo o edital e analisando viabilidade..."):
                    analyzer = SmartAnalyzer()
                    eligibility = EligibilityChecker()
                    matcher = SemanticMatcher()
                    client = PNCPClient()
                    
                    # 1. Análise do Texto (Smart Analyzer)
                    texto_analise = f"OBJETO: {lic.objeto}\n\nITENS:\n"
                    for item in lic.itens:
                        texto_analise += f"- {item.quantidade} {item.unidade} de {item.descricao}\n"
                    
                    # --- LEITURA PROFUNDA (DEEP READING) ---
                    # Tenta baixar anexos se for PNCP
                    if lic.pncp_id and len(lic.pncp_id.split('-')) == 3:
                        try:
                            cnpj, ano, seq = lic.pncp_id.split('-')
                            lic_dict = {"cnpj": cnpj, "ano": ano, "seq": seq}
                            arquivos = client.buscar_arquivos(lic_dict)
                            
                            # Prioriza Termo de Referência ou Edital
                            pdf_url = None
                            nome_arquivo = ""
                            for arq in arquivos:
                                nome_lower = (arq['titulo'] or "").lower() + (arq['nome'] or "").lower()
                                if "termo de referencia" in nome_lower or "termo de referência" in nome_lower or "edital" in nome_lower:
                                    if arq['url'] and (arq['url'].endswith('.pdf') or arq['url'].endswith('.PDF')):
                                        pdf_url = arq['url']
                                        nome_arquivo = arq['titulo'] or arq['nome']
                                        break
                            
                            if pdf_url:
                                st.toast(f"Baixando anexo: {nome_arquivo}...", icon="📥")
                                pdf_content = client.download_arquivo(pdf_url)
                                if pdf_content:
                                    import io
                                    from pypdf import PdfReader
                                    
                                    f = io.BytesIO(pdf_content)
                                    reader = PdfReader(f)
                                    texto_pdf = ""
                                    for page in reader.pages:
                                        texto_pdf += page.extract_text() + "\n"
                                    
                                    if texto_pdf:
                                        texto_analise += f"\n\n--- CONTEÚDO EXTRAÍDO DO ANEXO ({nome_arquivo}) ---\n{texto_pdf[:50000]}" # Limite de 50k chars do PDF
                                        st.toast("Texto do anexo extraído com sucesso!", icon="✅")
                        except Exception as e:
                            print(f"Erro no Deep Reading: {e}")
                            st.error(f"Erro ao ler anexo: {e}")

                    if len(texto_analise) < 200:
                        texto_analise += "\n(Texto curto, análise pode ser limitada. Recomenda-se baixar o PDF completo para análise profunda.)"

                    analise = analyzer.analisar_viabilidade(texto_analise)
                    
                    # 2. Verificação de Elegibilidade
                    elegibilidade = eligibility.check_eligibility({
                        "uf": lic.uf,
                        "modalidade": lic.modalidade
                    }, ai_analysis=analise)
                    
                    # 3. Matching Semântico (apenas se tiver itens)
                    # (Opcional para esta visualização, foca na viabilidade)
                    
                    # --- EXIBIÇÃO DOS RESULTADOS (CARD STYLE) ---
                    st.divider()
                    
                    if analise.get('erro'):
                        st.error(f"❌ {analise.get('erro')}")
                    else:
                        st.markdown(f"""
                        <div class="css-card">
                            <div class="card-header">Resultado da Análise</div>
                            <div class="card-title">Score de Viabilidade: <span style="color: #0071e3;">{analise.get('score_viabilidade', 0)}/100</span></div>
                            <div style="margin-top: 10px; font-size: 16px;">{analise.get('resumo_objeto', 'N/A')}</div>
                            <div style="margin-top: 10px; color: #86868b; font-size: 14px;"><em>"{analise.get('justificativa_score', 'N/A')}"</em></div>
                        </div>
                        """, unsafe_allow_html=True)

                    # Elegibilidade
                    if elegibilidade['eligible']:
                        st.success("✅ Empresa Elegível para participar")
                    else:
                        st.error("🚫 Empresa INELEGÍVEL")
                        for reason in elegibilidade['reasons']:
                            st.write(f"- {reason}")
                    
                    if elegibilidade['warnings']:
                        with st.expander("⚠️ Alertas de Elegibilidade"):
                            for warn in elegibilidade['warnings']:
                                st.write(f"- {warn}")

                    # Red Flags e Pontos de Atenção
                    col_red, col_att = st.columns(2)
                    with col_red:
                        st.markdown("""<div class="css-card" style="border-left: 4px solid #ff3b30;">
                        <div class="card-title" style="font-size: 16px;">🚩 Riscos (Red Flags)</div>
                        """, unsafe_allow_html=True)
                        red_flags = analise.get('red_flags', [])
                        if red_flags:
                            for flag in red_flags:
                                st.markdown(f"- {flag}")
                        else:
                            st.write("Nenhum risco grave identificado.")
                        st.markdown("</div>", unsafe_allow_html=True)

                    with col_att:
                        st.markdown("""<div class="css-card" style="border-left: 4px solid #ffcc00;">
                        <div class="card-title" style="font-size: 16px;">⚠️ Pontos de Atenção</div>
                        """, unsafe_allow_html=True)
                        att_points = analise.get('pontos_atencao', [])
                        if att_points:
                            for point in att_points:
                                st.markdown(f"- {point}")
                        else:
                            st.write("Nenhum ponto de atenção específico.")
                        st.markdown("</div>", unsafe_allow_html=True)

                    # Documentos
                    with st.expander("📄 Documentos Prováveis para Habilitação"):
                        docs = analise.get('documentos_habilitacao', [])
                        if docs:
                            for doc in docs:
                                st.write(f"- {doc}")
                        else:
                            st.write("Não foi possível extrair a lista de documentos.")
    session.close()

elif page == "Dashboard":
    st.header("Painel de Controle")
    
    session = get_session()

    # Opção para filtrar licitações salvas
    apenas_salvas = st.checkbox("⭐ Mostrar apenas licitações Salvas", value=False)
    
    query = session.query(Licitacao)
    if apenas_salvas:
        query = query.filter(Licitacao.status == 'Salva')
    
    licitacoes_db = query.all()
    
    # Ordenação Inteligente: Primeiro por número de itens com match, depois por data (mais recente)
    licitacoes = sorted(
        licitacoes_db, 
        key=lambda x: (sum(1 for i in x.itens if i.produto_match_id is not None), x.data_sessao or datetime.min), 
        reverse=True
    )
    
    if not licitacoes:
        st.info("Nenhuma licitação no banco. Vá em 'Buscar Licitações' para começar.")
    else:
        st.write(f"Mostrando {len(licitacoes)} licitações ordenadas por relevância.")
        
        for lic in licitacoes:
            # Contar itens com match
            total_itens = len(lic.itens)
            itens_com_match = [i for i in lic.itens if i.produto_match_id is not None]
            matches = len(itens_com_match)
            
            # Extrair nomes dos produtos (únicos)
            matched_names = sorted(list(set([i.produto_match.nome for i in itens_com_match])))
            
            # Ícone e cor baseados no match
            if matches > 0:
                icon = "🔥" # Fogo para alta prioridade
                names_str = ", ".join(matched_names[:3])
                if len(matched_names) > 3:
                    names_str += "..."
                match_info = f"✅ {names_str} ({matches} itens)"
            elif lic.modalidade == "Diário Oficial" or lic.modalidade == "Portal Externo":
                icon = "📢"
                match_info = "Aviso de Edital"
            else:
                icon = "⚠️"
                match_info = "Sem match direto"
            
            # Data formatada
            data_sessao_fmt = lic.data_sessao.strftime('%d/%m/%Y') if lic.data_sessao else "N/A"
            
            # Título do Expander (Unificado)
            expander_title = f"{icon} [{lic.uf}] {lic.orgao} ({lic.modalidade}) — {match_info}"
            
            with st.expander(expander_title):
                # --- CÁLCULO DE DISTÂNCIA ---
                # Tenta limpar o nome do órgão para achar a cidade
                clean_name = lic.orgao.upper()
                for p in ["PREFEITURA MUNICIPAL DE ", "PREFEITURA DE ", "MUNICIPIO DE ", "FUNDO MUNICIPAL DE SAUDE DE ", "CAMARA MUNICIPAL DE ", "SECRETARIA MUNICIPAL DE SAUDE DE "]:
                     clean_name = clean_name.replace(p, "")
                # Remove possíveis sufixos após traço (ex: NATAL - RN -> NATAL)
                if " - " in clean_name:
                    clean_name = clean_name.split(" - ")[0]
                
                cidade_destino = f"{clean_name} - {lic.uf}"

                # Endereço exato da base
                origem_base = "Avenida Miguel Castro, 998-A, Nossa Senhora de Nazaré, Natal - RN"
                distancia = get_road_distance(origem_base, cidade_destino)
                
                if distancia:
                    custo_frete = distancia * 1.0 # R$ 1,00 por km
                    st.info(f"🚚 **Logística:** Distância de **{distancia} km** | Custo Estimado (Ida): **R$ {custo_frete:.2f}**")
                # ---------------------------

                # Cabeçalho interno com informações principais
                col_header, col_dates = st.columns([3, 1])
                with col_header:
                    st.markdown(f"**Objeto:** {lic.objeto}")
                    st.caption(f"ID PNCP: {lic.pncp_id or 'N/A'}")
                with col_dates:
                    st.markdown(f"**📅 Sessão:** {data_sessao_fmt}")
                    st.link_button("🔗 Abrir Link", lic.link)

                st.divider()
                
                # Tabela de Itens
                if lic.itens:
                    st.markdown("###### 📦 Itens da Licitação")
                    data_itens = []
                    valor_total_proposta = 0
                    
                    for item in lic.itens:
                        match_nome = "❌ Sem Match"
                        custo = 0
                        preco_ref = 0
                        fonte_ref = "-"
                        v_unit_edital = item.valor_unitario if item.valor_unitario else 0
                        diff_percent = 0
                        
                        if item.produto_match:
                            match_nome = f"✅ {item.produto_match.nome}"
                            custo = item.produto_match.preco_custo
                            margem = item.produto_match.margem_minima / 100
                            preco_venda = custo * (1 + margem)
                            valor_total_proposta += preco_venda * item.quantidade
                            
                            preco_ref = item.produto_match.preco_referencia
                            fonte_ref = item.produto_match.fonte_referencia
                            
                            if v_unit_edital > 0 and custo > 0:
                                diff_percent = ((v_unit_edital - custo) / custo) * 100
                        
                        data_itens.append({
                            "Item": item.numero_item,
                            "Descrição": item.descricao,
                            "Qtd": item.quantidade,
                            "Unidade": item.unidade,
                            "Valor Unit. (Edital)": f"R$ {v_unit_edital:,.2f}",
                            "Match": match_nome
                        })
                        
                    st.dataframe(
                        pd.DataFrame(data_itens), 
                        width='stretch',
                        column_config={
                            "Item": st.column_config.NumberColumn(width="small"),
                            "Descrição": st.column_config.TextColumn(width="large"),
                        },
                        hide_index=True
                    )
                    
                    if matches > 0:
                        st.success(f"💰 Potencial de Proposta: R$ {valor_total_proposta:,.2f} (Baseado no seu custo + margem)")
                else:
                    st.info("Nenhum item detalhado encontrado.")
                
                # Ações Extras
                st.markdown("---")
                col_act1, col_act2, col_act3, col_act4, col_act5, col_act6 = st.columns(6)
                
                with col_act1:
                    if st.button("📂 Ver Arquivos", key=f"btn_arq_{lic.id}"):
                        with st.spinner("Buscando arquivos..."):
                            client = PNCPClient()
                            # Reconstrói dict mínimo
                            parts = lic.pncp_id.split('-') if lic.pncp_id else []
                            if len(parts) >= 3:
                                lic_dict = {"cnpj": parts[0], "ano": parts[1], "seq": parts[2]}
                                arquivos = client.buscar_arquivos(lic_dict)
                                if arquivos:
                                    st.write("**Arquivos:**")
                                    for arq in arquivos:
                                        st.markdown(f"- [{arq['titulo']}]({arq['url']})")
                                else:
                                    st.warning("Nenhum arquivo anexado encontrado no PNCP.")
                            else:
                                st.error("ID PNCP inválido para busca de arquivos.")

                with col_act2:
                    if st.button("🧠 Análise IA", key=f"btn_ai_{lic.id}"):
                        # Redireciona ou executa análise inline
                        st.info("Para análise detalhada, use a aba '🧠 Análise de IA' no menu lateral.")

                with col_act3:
                    if st.button("📱 WhatsApp", key=f"btn_wpp_{lic.id}"):
                        import json
                        session = get_session()

                        # Tenta puxar o edital/anexos direto do PNCP para compartilhar no WhatsApp
                        edital_link = None
                        if lic.pncp_id:
                            try:
                                parts = lic.pncp_id.split('-')
                                if len(parts) >= 3:
                                    pncp_client = PNCPClient()
                                    lic_dict = {"cnpj": parts[0], "ano": parts[1], "seq": parts[2]}
                                    arquivos = pncp_client.buscar_arquivos(lic_dict) or []

                                    # Prioriza PDF que contenha "edital" no título
                                    pdfs = [a for a in arquivos if (a.get("url") or "").lower().endswith(".pdf") or (a.get("nome") or "").lower().endswith(".pdf")]
                                    edital_pdf = next((a for a in pdfs if "edital" in (a.get("titulo") or "").lower()), None)
                                    alvo = edital_pdf or (pdfs[0] if pdfs else None)
                                    if alvo:
                                        edital_link = alvo.get("url")
                            except Exception as e:
                                print(f"[WhatsApp] Falha ao buscar edital PNCP: {e}")

                        # Tenta buscar configuração nova (múltiplos contatos)
                        config_contacts = session.query(Configuracao).filter_by(chave='whatsapp_contacts').first()

                        contacts_list = []
                        if config_contacts and config_contacts.valor:
                            try:
                                contacts_list = json.loads(config_contacts.valor)
                            except:
                                pass

                        # Fallback: tenta configuração antiga (1 telefone)
                        if not contacts_list:
                            conf_phone = session.query(Configuracao).filter_by(chave='whatsapp_phone').first()
                            conf_key = session.query(Configuracao).filter_by(chave='whatsapp_apikey').first()
                            if conf_phone and conf_key and conf_phone.valor and conf_key.valor:
                                contacts_list = [{"nome": "Principal", "phone": conf_phone.valor, "apikey": conf_key.valor}]

                        session.close()

                        if not contacts_list:
                            st.error("Configure o WhatsApp na aba Configurações!")
                        else:
                            # Monta mensagem
                            itens_str = ""
                            # Prioriza itens com match para destacar o motivo do interesse
                            target_list = [i for i in lic.itens if i.produto_match_id]
                            if not target_list: target_list = lic.itens

                            for i in target_list[:5]:
                                itens_str += f"- {i.descricao[:60]}...\n"
                            if len(target_list) > 5:
                                itens_str += f"... (+{len(target_list)-5} itens)"

                            msg = f"🚀 *Oportunidade Selecionada*\n\n"
                            msg += f"🏛 *{lic.orgao}* ({lic.uf})\n"
                            msg += f"📋 {lic.modalidade}\n\n"
                            msg += f"📦 *Destaques:*\n{itens_str}\n"
                            msg += f"🔗 {lic.link}"
                            if edital_link:
                                msg += f"\n📑 Edital (PDF): {edital_link}"

                            # Envia para todos os contatos configurados
                            enviados = 0
                            erros = []
                            for contact in contacts_list:
                                notifier = WhatsAppNotifier(contact.get('phone'), contact.get('apikey'))
                                if notifier.enviar_mensagem(msg):
                                    enviados += 1
                                else:
                                    erro_msg = notifier.ultimo_erro or "Erro desconhecido"
                                    erros.append(f"{contact.get('nome', 'Sem nome')}: {erro_msg}")

                            if enviados > 0:
                                st.toast(f"✅ Enviado para {enviados} contato(s)!", icon="✅")

                            if erros:
                                st.error("❌ Erros ao enviar:\n" + "\n".join(erros))

                with col_act4:
                    # Botão de Salvar/Fixar
                    label_salvar = "⭐ Fixar" if lic.status != 'Salva' else "❌ Desafixar"
                    if st.button(label_salvar, key=f"btn_save_{lic.id}", help="Salva no banco permanente (não será apagado na limpeza)"):
                        if lic.status == 'Salva':
                            lic.status = 'Nova'
                            st.toast("Licitação desafixada.", icon="ℹ️")
                        else:
                            lic.status = 'Salva'
                            st.toast("Licitação salva com sucesso!", icon="✅")
                        session.commit()
                        time.sleep(0.5)
                        st.rerun()

                with col_act5:
                    if st.button("✅ Participar", key=f"btn_part_{lic.id}", help="Marcar para participar desta licitação"):
                        lic.status = "Participar"
                        session.commit()
                        st.toast("Marcada como Participar.", icon="✅")
                        time.sleep(0.3)
                        st.rerun()

                with col_act6:
                    if st.button("🚫 Ignorar", key=f"btn_ignore_{lic.id}", help="Ignorar esta licitação"):
                        lic.status = "Ignorada"
                        session.commit()
                        st.toast("Marcada como Ignorada.", icon="⚠️")
                        time.sleep(0.3)
                        st.rerun()

elif page == "💰 Gestão Financeira":
    st.header("💰 Gestão Financeira - Extratos Banco do Brasil")
    st.info("Importe e visualize seus extratos bancários (Formato Excel BB).")

    col_base, _ = st.columns([1, 4])
    with col_base:
        base_escolhida = st.radio(
            "Base de dados",
            ["Financeiro Atual", "Financeiro Histórico"],
            horizontal=True,
            help="Escolha onde salvar/consultar: ativo (2025 em diante) ou histórico (anos anteriores)."
        )
    is_historico = base_escolhida == "Financeiro Histórico"
    session_factory = get_finance_historico_session if is_historico else get_finance_session
    session = session_factory()
    base_label = "Histórico" if is_historico else "Atual"

    # === BUSCA GLOBAL POR FATURA/OBS (ambas as bases) ===
    with st.expander("🔎 Busca Global por Fatura/Obs (todas as bases e meses)", expanded=False):
        termo_fatura_global = st.text_input("Informe parte da fatura/obs/histórico (ex: 3194)", key="busca_fatura_global")
        if termo_fatura_global:
            # Consulta na base atual selecionada
            query_base = session.query(ExtratoBB).filter(
                or_(
                    ExtratoBB.fatura.ilike(f"%{termo_fatura_global}%"),
                    ExtratoBB.observacoes.ilike(f"%{termo_fatura_global}%"),
                    ExtratoBB.historico.ilike(f"%{termo_fatura_global}%")
                )
            ).order_by(ExtratoBB.dt_balancete.desc()).limit(200).all()

            # Consulta na outra base
            if is_historico:
                outra_session = get_finance_session()
                outra_label = "Financeiro Atual"
            else:
                outra_session = get_finance_historico_session()
                outra_label = "Financeiro Histórico"

            query_outra = outra_session.query(ExtratoBB).filter(
                or_(
                    ExtratoBB.fatura.ilike(f"%{termo_fatura_global}%"),
                    ExtratoBB.observacoes.ilike(f"%{termo_fatura_global}%"),
                    ExtratoBB.historico.ilike(f"%{termo_fatura_global}%")
                )
            ).order_by(ExtratoBB.dt_balancete.desc()).limit(200).all()

            def montar_df(lst, label):
                data = []
                for l in lst:
                    data.append({
                        "Base": label,
                        "Data": l.dt_balancete,
                        "Mês": l.mes_referencia,
                        "Ano": l.ano_referencia,
                        "Status": l.status,
                        "Histórico": l.historico,
                        "Documento": l.documento,
                        "Valor": l.valor,
                        "Fatura/Obs": l.fatura or l.observacoes
                    })
                return pd.DataFrame(data)

            df_base = montar_df(query_base, base_label)
            df_outra = montar_df(query_outra, outra_label)
            df_result = pd.concat([df_base, df_outra], ignore_index=True)

            if df_result.empty:
                st.info("Nada encontrado nas duas bases.")
            else:
                st.caption("Mostrando até 200 resultados por base, ordenados pela data mais recente.")
                st.dataframe(df_result, use_container_width=True, hide_index=True)
                csv_data = df_result.to_csv(index=False).encode('utf-8')
                st.download_button(
                    "📥 Baixar resultados (CSV)",
                    data=csv_data,
                    file_name=f"busca_fatura_global_{termo_fatura_global}.csv",
                    mime="text/csv"
                )

    # === SEÇÃO DE UPLOAD ===
    col_up1, col_up2 = st.columns(2)
    
    with col_up1:
        with st.expander("📤 Importar Arquivo Excel", expanded=False):
            uploaded_file = st.file_uploader("Selecione o arquivo Excel (.xlsx)", type=['xlsx'])

            if uploaded_file:
                if st.button("Processar Arquivo"):
                    with st.spinner("Lendo arquivo..."):
                        # Salva arquivo temporário
                        temp_path = f"temp_extrato_{int(time.time())}.xlsx"
                        with open(temp_path, "wb") as f:
                            f.write(uploaded_file.getbuffer())

                        try:
                            stats = importar_extrato_bb(temp_path, session)
                            st.success(f"✅ Importação concluída! {stats['importados']} lançamentos processados.")
                            if stats['duplicados'] > 0:
                                st.warning(f"{stats['duplicados']} lançamentos duplicados mantidos/ignorados.")
                            if stats['erros']:
                                st.error(f"Erros: {stats['erros']}")
                        except Exception as e:
                            st.error(f"Erro ao processar: {str(e)}")
                        finally:
                            if os.path.exists(temp_path):
                                os.remove(temp_path)
                                
                    st.rerun()

        with st.expander("📤 Importar Arquivo Excel (Histórico flexível)", expanded=False):
            st.caption("Use para Sicredi ou planilhas fora do padrão BB (colunas mínimas: Data, Descrição, Valor).")
            banco_origem = st.selectbox("Banco/Origem", ["Sicredi", "BB", "Outro"], key="hist_banco_origem")
            uploaded_hist = st.file_uploader("Selecione o arquivo Excel (.xlsx)", type=['xlsx'], key="hist_uploader")

            if uploaded_hist:
                if st.button("Processar Histórico", key="btn_process_hist"):
                    with st.spinner("Lendo arquivo histórico..."):
                        temp_path = f"temp_extrato_{int(time.time())}.xlsx"
                        with open(temp_path, "wb") as f:
                            f.write(uploaded_hist.getbuffer())
                        try:
                            stats = importar_extrato_historico(temp_path, session, banco_origem)
                            st.success(f"✅ Histórico importado em {base_label}! {stats['importados']} lançamentos.")
                            if stats.get('duplicados', 0) > 0:
                                st.warning(f"{stats['duplicados']} lançamentos duplicados ignorados.")
                            if stats.get('erros'):
                                st.error(f"Erros: {stats['erros']}")
                        except Exception as e:
                            st.error(f"Erro ao processar histórico: {str(e)}")
                        finally:
                            if os.path.exists(temp_path):
                                os.remove(temp_path)
                    st.rerun()

    with col_up2:
        # Lógica Inteligente: Sugerir próximo mês
        ultimo_lanc = session.query(ExtratoBB).order_by(ExtratoBB.dt_balancete.desc()).first()
        lbl_expander = "📋 Importar Texto (Copiar/Colar)"
        msg_ajuda = "Copie as linhas do Excel ou do Internet Banking e cole abaixo."
        
        if ultimo_lanc:
            ud = ultimo_lanc.dt_balancete
            if ud.month == 12:
                prox_mes = 1
                prox_ano = ud.year + 1
            else:
                prox_mes = ud.month + 1
                prox_ano = ud.year
                
            meses_pt = {
                1:'Janeiro', 2:'Fevereiro', 3:'Março', 4:'Abril', 5:'Maio', 6:'Junho', 
                7:'Julho', 8:'Agosto', 9:'Setembro', 10:'Outubro', 11:'Novembro', 12:'Dezembro'
            }
            lbl_expander = f"📋 Importar: {meses_pt[prox_mes]}/{prox_ano} (Copiar/Colar)"
            msg_ajuda = f"O sistema parou em **{ud.strftime('%d/%m/%Y')}**. Cole abaixo os lançamentos de **{meses_pt[prox_mes]}/{prox_ano}**."

        with st.expander(lbl_expander, expanded=False):
            st.info(msg_ajuda)
            texto_paste = st.text_area("Cole os dados aqui:", height=150, placeholder="25/11/2025\tPIX RECEBIDO\t2.000,00 C")

            if st.button("Processar Texto"):
                if texto_paste:
                    with st.spinner("Processando texto..."):
                        try:
                            stats = processar_texto_extrato(texto_paste, session)
                            st.success(f"✅ Importação concluída! {stats['importados']} lançamentos processados.")
                            if stats['duplicados'] > 0:
                                st.warning(f"{stats['duplicados']} lançamentos duplicados mantidos/ignorados.")
                            if stats['erros']:
                                st.error(f"Erros: {stats['erros']}")
                        except Exception as e:
                            st.error(f"Erro ao processar: {str(e)}")
                    st.rerun()
                else:
                    st.warning("Cole algum texto primeiro.")

    st.divider()

    # === IMPORTAR PLANILHA SESAP ===
    with st.expander("📥 Importar Planilha SESAP (listagem a receber/pagos)", expanded=False):
        st.caption("Usa o XLSX que vem da SESAP (ex.: HEMATO 165_2022 ATT.xlsx). Detecta colunas: Filial, Competência, Unidade, Contrato, Cliente, Dt.Emissão, Nº Doc (fatura), Vr.Líquido, Dt.Vencimento, Nº DO PROCESSO, Status, Pagamento (manual).")
        uploaded_sesap = st.file_uploader("Selecione a planilha SESAP (.xlsx)", type=['xlsx'], key="sesap_uploader")
        if uploaded_sesap and st.button("Processar Planilha SESAP", key="btn_process_sesap"):
            with st.spinner("Importando planilha SESAP..."):
                temp_path = f"temp_sesap_{int(time.time())}.xlsx"
                with open(temp_path, "wb") as f:
                    f.write(uploaded_sesap.getbuffer())
                try:
                    from modules.finance import importar_planilha_sesap
                    stats = importar_planilha_sesap(temp_path, session, arquivo_origem=uploaded_sesap.name)
                    st.success(f"✅ SESAP importada ({base_label}): {stats['importados']} linhas, {stats['duplicados']} duplicadas.")
                    if stats.get('erros'):
                        st.error(f"Erros: {stats['erros']}")
                except Exception as e:
                    st.error(f"Erro ao importar SESAP: {e}")
                finally:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
            st.rerun()

    st.divider()

    # === ASSISTENTE IA ===
    with st.expander("🤖 Assistente Financeiro (IA)", expanded=True):
        col_ai1, col_ai2 = st.columns([4, 1])
        with col_ai1:
            pergunta_usuario = st.text_input("Pergunte sobre suas finanças:", placeholder="Ex: Quanto paguei de impostos em 2025? ou Qual o total de entradas em Março?")
        with col_ai2:
            st.write("")
            st.write("")
            btn_perguntar = st.button("Perguntar 🧠")
            
        if btn_perguntar and pergunta_usuario:
            from modules.finance.finance_ai import FinanceAI
            finance_ai = FinanceAI(session_factory=session_factory, fonte_nome=base_label)
            
            with st.spinner("Analisando dados..."):
                resposta = finance_ai.analisar_pergunta(pergunta_usuario)
                st.markdown(f"### 🤖 Resposta:\n{resposta}")

    st.divider()

    # === DASHBOARD E VISUALIZAÇÃO ===

    # Busca meses disponíveis
    meses_disponiveis = session.query(ResumoMensal).order_by(ResumoMensal.ano.desc(), ResumoMensal.id.desc()).all()

    if meses_disponiveis:
        opcoes_meses = [f"{m.mes}/{m.ano}" for m in meses_disponiveis]

        # Seletor de mês (colocado aqui para controlar todas as visualizações)
        st.subheader("📝 Gerenciar Lançamentos")
        col_sel_mes, col_info = st.columns([1, 3])
        with col_sel_mes:
            mes_selecionado_str = st.selectbox("📅 Mês", opcoes_meses, key="selector_mes_lancamentos")
            resumo_selecionado = next(m for m in meses_disponiveis if f"{m.mes}/{m.ano}" == mes_selecionado_str)
        with col_info:
            st.caption("Selecione o mês para visualizar métricas, gráficos e gerenciar lançamentos.")

        st.divider()

        # === METRICAS DO MÊS ===
        col_titulo, col_recalc = st.columns([4, 1])
        with col_titulo:
            st.subheader(f"📊 Resumo: {resumo_selecionado.mes}/{resumo_selecionado.ano}")
        with col_recalc:
            st.write("")  # Alinhamento vertical
            if st.button("🔄 Recalcular", help="Recalcula os totais de entradas e saídas baseado nos lançamentos atuais"):
                # Recalcula o resumo
                tipos_ignorados = ['Aplicação Financeira', 'Aplicação', 'BB Rende Fácil', 'Movimentacao do Dia']
                lancamentos_mes = session.query(ExtratoBB).filter_by(
                    mes_referencia=resumo_selecionado.mes,
                    ano_referencia=resumo_selecionado.ano
                ).all()

                total_entradas = sum(l.valor for l in lancamentos_mes if l.valor > 0 and l.tipo not in tipos_ignorados)
                total_saidas = sum(abs(l.valor) for l in lancamentos_mes if l.valor < 0 and l.tipo not in tipos_ignorados)
                total_valor_liquido = sum(l.valor for l in lancamentos_mes)

                # Separa aportes de entradas operacionais
                total_aportes = sum(l.valor for l in lancamentos_mes if l.valor > 0 and l.tipo == 'Aporte Capital')
                total_entradas_sem_aportes = total_entradas - total_aportes

                resumo_selecionado.total_entradas = total_entradas
                resumo_selecionado.total_aportes = total_aportes
                resumo_selecionado.total_entradas_sem_aportes = total_entradas_sem_aportes
                resumo_selecionado.total_saidas = total_saidas
                resumo_selecionado.total_valor = total_valor_liquido
                session.add(resumo_selecionado)
                session.commit()
                st.success("✅ Resumo recalculado!")
                time.sleep(1)
                st.rerun()

        # Cálculo dos indicadores financeiros
        entradas_operacionais = getattr(resumo_selecionado, 'total_entradas_sem_aportes', 0.0)
        aportes = getattr(resumo_selecionado, 'total_aportes', 0.0)
        saidas = getattr(resumo_selecionado, 'total_saidas', 0.0)

        # Resultado Operacional (O que a empresa gerou de caixa real, SEM contar aportes)
        resultado_operacional = entradas_operacionais - saidas
        resultado_com_aportes = (entradas_operacionais + aportes) - saidas

        # CSS para compactar as métricas e garantir que caibam na linha
        st.markdown("""
            <style>
            [data-testid="stMetricLabel"] {
                font-size: 13px !important;
                min-height: 30px;
                white-space: normal;
            }
            [data-testid="stMetricValue"] {
                font-size: 18px !important;
            }
            </style>
        """, unsafe_allow_html=True)

        m1, m2, m3, m4, m5 = st.columns(5)

        with m1:
            st.metric("Entradas Operacionais", f"R$ {entradas_operacionais:,.2f}",
                     help="Receitas da operação: SESAP, Base Aérea, Vendas (SEM aportes de capital)")
        with m2:
            st.metric("Aportes de Capital", f"R$ {aportes:,.2f}",
                     help="Dinheiro dos sócios (Magnus, Paulo, Medcal)")
        with m3:
            st.metric("Saídas (-)", f"R$ {saidas:,.2f}",
                     help="Pagamentos, Impostos, Despesas")
        with m4:
            st.metric("Res. Operacional", f"R$ {resultado_operacional:,.2f}",
                     help="Entradas Operacionais - Saídas. (Lucro/Prejuízo da operação pura)")
        with m5:
            st.metric("Res. Total c/ Aportes", f"R$ {resultado_com_aportes:,.2f}",
                     help="Resultado Final: (Operacional + Aportes) - Saídas")
            
        # === ANÁLISE SESAP & PÚBLICO ===
        st.write("")

        # Total SESAP = Apenas lançamentos com histórico "632 Ordem Bancária" (Excluindo Base Aérea)
        # (valor total que a SESAP efetivamente pagou)
        sesap_condition = or_(
            ExtratoBB.tipo == 'Recebimento SESAP',
            ExtratoBB.historico.ilike('%632 Ordem Bancária%'),
            ExtratoBB.historico.ilike('%140319%'),  # TED 140319... (Sicredi)
            ExtratoBB.historico.ilike('%082417%'),  # TED 082417... (Sicredi)
            ExtratoBB.historico.ilike('%FUSERN%'),
            ExtratoBB.historico.ilike('%CUSTEIO SUS%')
        )

        # Filtro de banco (001/748) se disponível; se banco vier vazio, não filtra
        if session.query(ExtratoBB).filter(
            ExtratoBB.mes_referencia == resumo_selecionado.mes,
            ExtratoBB.ano_referencia == resumo_selecionado.ano,
            ExtratoBB.banco.isnot(None)
        ).count() > 0:
            banco_filter = ExtratoBB.banco.in_(['001','748'])
        else:
            banco_filter = True

        total_sesap = session.query(func.sum(ExtratoBB.valor)).filter(
            ExtratoBB.mes_referencia == resumo_selecionado.mes,
            ExtratoBB.ano_referencia == resumo_selecionado.ano,
            sesap_condition,
            banco_filter,
            not_(or_(ExtratoBB.historico.ilike('%12 SEC TES NAC%'), ExtratoBB.historico.ilike('%AEREA%')))
        ).scalar() or 0.0

        # Detalhe Base Aérea (Identificado por Tipo OU por palavras-chave no histórico)
        total_base_aerea = session.query(func.sum(ExtratoBB.valor)).filter(
            ExtratoBB.mes_referencia == resumo_selecionado.mes,
            ExtratoBB.ano_referencia == resumo_selecionado.ano,
            or_(
                ExtratoBB.tipo == 'Recebimento Base Aérea',
                ExtratoBB.historico.ilike('%12 SEC TES NAC%'),
                ExtratoBB.historico.ilike('%AEREA%')
            )
        ).scalar() or 0.0

        with st.expander("🏥 Análise de Recebimentos Públicos (SESAP / Base Aérea)", expanded=True):
            c_sesap, c_base = st.columns(2)
            with c_sesap:
                st.metric("Total Pago pela SESAP", f"R$ {total_sesap:,.2f}", help="Valor total baseado no histórico '632 Ordem Bancária'.")

                # Detalhamento por Categoria (para relatório)
                if total_sesap > 0:
                    st.markdown("**Detalhamento por Categoria:**")
                    st.caption("(Classificações para nível de relatório)")

                    categorias_detalhamento = ['Hematologia', 'Coagulação', 'Coagulacao', 'Ionograma']
                    # Filtra apenas lançamentos SESAP (histórico "632 Ordem Bancária") que foram classificados
                    breakdown = session.query(ExtratoBB.tipo, func.sum(ExtratoBB.valor)).filter(
                        ExtratoBB.mes_referencia == resumo_selecionado.mes,
                        ExtratoBB.ano_referencia == resumo_selecionado.ano,
                        ExtratoBB.historico.ilike('%632 Ordem Bancária%'),
                        ExtratoBB.tipo.in_(categorias_detalhamento)
                    ).group_by(ExtratoBB.tipo).order_by(func.sum(ExtratoBB.valor).desc()).all()

                    total_classificado = 0
                    for t, v in breakdown:
                        total_classificado += v
                        st.caption(f"• {t}: R$ {v:,.2f}")

                    # Mostra quanto ainda falta classificar
                    nao_classificado = total_sesap - total_classificado
                    if nao_classificado > 0:
                        st.caption(f"• Não Classificado: R$ {nao_classificado:,.2f}")

            with c_base:
                st.metric("Total Base Aérea", f"R$ {total_base_aerea:,.2f}", help="Identificado por '12 SEC TES NAC' ou 'AEREA'.")
            
        # === GRÁFICOS DE COMPOSIÇÃO ===
        st.write("") # Espaçamento
        col_comp1, col_comp2 = st.columns(2)

        # Tipos neutros para ignorar
        tipos_neutros = ['Aplicação', 'Aplicação Financeira', 'BB Rende Fácil']

        # --- Entradas ---
        with col_comp1:
            with st.expander("🍰 Composição das Entradas (Receita)", expanded=False):
                # Categorias de detalhamento SESAP que devem ser agrupadas
                categorias_sesap_detalhamento = ['Hematologia', 'Coagulação', 'Coagulacao', 'Ionograma', 'Recebimento SESAP']

                # Total SESAP agregado (inclui tipo Recebimento SESAP e TEDs identificadas)
                total_sesap_receita = session.query(func.sum(ExtratoBB.valor)).filter(
                    ExtratoBB.mes_referencia == resumo_selecionado.mes,
                    ExtratoBB.ano_referencia == resumo_selecionado.ano,
                    sesap_condition,
                    ExtratoBB.banco.in_(['001','748']),
                    ExtratoBB.valor > 0
                ).scalar() or 0.0

                # Outras categorias (excluindo SESAP e neutros)
                composicao_ent = session.query(
                    ExtratoBB.tipo,
                    func.sum(ExtratoBB.valor)
                ).filter(
                    ExtratoBB.mes_referencia == resumo_selecionado.mes,
                    ExtratoBB.ano_referencia == resumo_selecionado.ano,
                    ExtratoBB.valor > 0,
                    ExtratoBB.tipo.notin_(tipos_neutros + categorias_sesap_detalhamento)
                ).group_by(ExtratoBB.tipo).order_by(func.sum(ExtratoBB.valor).desc()).all()

                total_receita_base = getattr(resumo_selecionado, 'total_entradas', 0.0)

                if total_receita_base > 0:
                                       # Primeiro mostra Recebimento SESAP agregado
                    if total_sesap_receita > 0:
                        pct = (total_sesap_receita / total_receita_base) * 100
                        st.write(f"**Recebimento SESAP**")
                        st.write(f"R$ {total_sesap_receita:,.2f} ({pct:.1f}%)")
                        st.progress(min(int(pct), 100))

                    # Depois mostra outras categorias
                    for cat, valor in composicao_ent:
                        if not cat: cat = "Outros / Não Identificado"
                        pct = (valor / total_receita_base) * 100
                        st.write(f"**{cat}**")
                        st.write(f"R$ {valor:,.2f} ({pct:.1f}%)")
                        st.progress(min(int(pct), 100))
                else:
                    st.info("Sem dados de entrada.")

        # --- Saídas ---
            with col_comp2:
                with st.expander("💸 Composição das Saídas (Despesas)", expanded=False):
                    # Nota: valor é negativo no banco, usamos abs para somar
                    composicao_sai = session.query(
                        ExtratoBB.tipo, 
                        func.sum(func.abs(ExtratoBB.valor))
                ).filter(
                    ExtratoBB.mes_referencia == resumo_selecionado.mes,
                    ExtratoBB.ano_referencia == resumo_selecionado.ano,
                    ExtratoBB.valor < 0, 
                    ExtratoBB.tipo.notin_(tipos_neutros)
                ).group_by(ExtratoBB.tipo).order_by(func.sum(func.abs(ExtratoBB.valor)).desc()).all()
                
                total_despesa_base = getattr(resumo_selecionado, 'total_saidas', 0.0)
                
                if composicao_sai and total_despesa_base > 0:
                    for cat, valor in composicao_sai:
                        if not cat: cat = "Outros / Não Identificado"
                        pct = (valor / total_despesa_base) * 100
                        st.write(f"**{cat}**")
                        st.write(f"R$ {valor:,.2f} ({pct:.1f}%)")
                        st.progress(min(int(pct), 100))
                else:
                    st.info("Sem dados de saída.")
        
        st.divider()

        # === TABELA DE LANÇAMENTOS ===
        st.markdown("#### 📋 Lançamentos do Mês")
        st.caption("Você pode alterar o **Tipo** e a **Fatura** diretamente na tabela abaixo. Útil para classificar 'Ordem Bancária' como 'Hematologia', Ionograma, etc.")

        # Filtros da tabela
        tf1, tf2, tf3, tf4 = st.columns([1, 1, 2, 1])
        with tf1:
            filtro_status = st.selectbox("Status", ["Todos", "Baixado", "Pendente"])
        with tf2:
            st.write("") # Alinhamento vertical
            apenas_pendentes = st.checkbox("⏳ Classificar O.B.", help="Mostra apenas 'Ordem Bancária' para você definir se é Hematologia, Ionograma, etc.")
        with tf3:
            filtro_texto = st.text_input("Buscar no histórico", placeholder="Ex: Pagamento...")
        with st.columns(2)[1]:
            filtro_fatura = st.text_input("Buscar por Fatura/Obs", placeholder="Ex: 3194")
        with tf4:
            filtro_sesap = st.checkbox("Somente SESAP", help="Filtra histórico/tipo que contenha SESAP (632, TED 140319/082417, FUSERN, Recebimento SESAP).")
        
        # Query
        query = session.query(ExtratoBB).filter_by(
            mes_referencia=resumo_selecionado.mes,
            ano_referencia=resumo_selecionado.ano
        )
        
        if apenas_pendentes:
            # Lógica melhorada: Mostra tudo que é 632 (SESAP/Base) e que AINDA NÃO foi classificado nas categorias finais
            categorias_classificadas = ['Hematologia', 'Coagulação', 'Coagulacao', 'Ionograma', 'Base', 'Recebimento Base Aérea']
            query = query.filter(
                ExtratoBB.historico.ilike('%632 Ordem Bancária%'),
                not_(ExtratoBB.tipo.in_(categorias_classificadas))
            )
        
        if filtro_status != "Todos":
            query = query.filter(ExtratoBB.status.ilike(filtro_status))
            
        if filtro_texto:
            query = query.filter(ExtratoBB.historico.ilike(f"%{filtro_texto}%"))
        if filtro_fatura:
            query = query.filter(ExtratoBB.fatura.ilike(f"%{filtro_fatura}%"))
        if filtro_sesap:
            sesap_condition = or_(
                ExtratoBB.tipo == 'Recebimento SESAP',
                ExtratoBB.historico.ilike('%632 Ordem Bancária%'),
                ExtratoBB.historico.ilike('%140319%'),
                ExtratoBB.historico.ilike('%082417%'),
                ExtratoBB.historico.ilike('%FUSERN%'),
                ExtratoBB.historico.ilike('%CUSTEIO SUS%')
            )
            query = query.filter(sesap_condition)
            
        lancamentos = query.order_by(ExtratoBB.dt_balancete.desc()).all()
        
        if lancamentos:
            # Prepara DF para edição (Mantém ID para update)
            data_edit = []
            for l in lancamentos:
                # Formatação visual do Status
                st_fmt = l.status
                if str(l.status).lower() == 'baixado': st_fmt = "🟢 Baixado"
                elif str(l.status).lower() == 'pendente': st_fmt = "🟡 Pendente"
                elif not l.status: st_fmt = "⚪ (Vazio)"

                data_edit.append({
                    "id": l.id,
                    "Data": l.dt_balancete,
                    "Status": st_fmt,
                    "Histórico": l.historico,
                    "Documento": l.documento,
                    "Valor": l.valor,
                    "Tipo": l.tipo,
                    "Fatura": l.fatura
                })
            
            df_edit = pd.DataFrame(data_edit)
            df_edit.set_index("id", inplace=True) # Define ID como índice para ocultar

            # Botões de download da planilha
            col_down1, col_down2, col_down3 = st.columns([1, 1, 4])

            with col_down1:
                # Prepara dados do mês atual para download
                df_download_mes = df_edit.copy()
                df_download_mes['Status'] = df_download_mes['Status'].str.replace("🟢 ", "").str.replace("🟡 ", "").str.replace("⚪ ", "")

                # Converte para Excel em memória
                buffer_mes = BytesIO()
                with pd.ExcelWriter(buffer_mes, engine='openpyxl') as writer:
                    df_download_mes.to_excel(writer, sheet_name=f'{resumo_selecionado.mes}_{resumo_selecionado.ano}', index=False)
                buffer_mes.seek(0)

                st.download_button(
                    label="📥 Baixar Mês",
                    data=buffer_mes,
                    file_name=f"lancamentos_{resumo_selecionado.mes}_{resumo_selecionado.ano}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    help="Baixa os lançamentos do mês atual filtrados"
                )

            with col_down2:
                # Prepara dados de TODOS os meses para download
                todos_lancamentos = session.query(ExtratoBB).order_by(
                    ExtratoBB.ano_referencia.desc(),
                    ExtratoBB.mes_referencia.desc(),
                    ExtratoBB.dt_balancete.desc()
                ).all()

                data_todos = []
                for l in todos_lancamentos:
                    st_fmt = "Baixado" if str(l.status).lower() == 'baixado' else "Pendente" if str(l.status).lower() == 'pendente' else ""
                    data_todos.append({
                        "Mês": l.mes_referencia,
                        "Ano": l.ano_referencia,
                        "Data": l.dt_balancete,
                        "Status": st_fmt,
                        "Histórico": l.historico,
                        "Documento": l.documento,
                        "Valor": l.valor,
                        "Tipo": l.tipo,
                        "Fatura": l.fatura
                    })

                df_todos = pd.DataFrame(data_todos)

                # Converte para Excel em memória
                buffer_todos = BytesIO()
                with pd.ExcelWriter(buffer_todos, engine='openpyxl') as writer:
                    df_todos.to_excel(writer, sheet_name='Todos_Lançamentos', index=False)
                buffer_todos.seek(0)

                st.download_button(
                    label="📥 Baixar Todos",
                    data=buffer_todos,
                    file_name="lancamentos_todos_meses.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    help="Baixa TODOS os lançamentos de todos os meses"
                )

            # Configura editor
            edited_df = st.data_editor(
                df_edit,
                column_config={
                    "Data": st.column_config.DateColumn(format="DD/MM/YYYY", disabled=True),
                    "Status": st.column_config.SelectboxColumn(
                        "Status", 
                        options=["🟢 Baixado", "🟡 Pendente"], 
                        width="small", 
                        required=True
                    ),
                    "Histórico": st.column_config.TextColumn(disabled=True, width="large"),
                    "Valor": st.column_config.NumberColumn(format="R$ %.2f", disabled=True),
                    "Tipo": st.column_config.SelectboxColumn(
                        "Classificação",
                        options=[
                            "Ordem Bancária", "Hematologia", "Coagulação", "Ionograma", "Base",
                            "Pix - Recebido", "Pix - Enviado", "Pagamento Boleto",
                            "Pagamento Fornecedor", "Impostos", "Tarifa Bancária",
                            "Transferência Recebida", "Transferência Enviada",
                            "Aplicação", "Pagamento Ourocap", "Depósito Corban", "Outros"
                        ],
                        required=True
                    ),
                    "Fatura": st.column_config.TextColumn("Fatura / Obs")
                },
                hide_index=True, # Oculta o ID (que agora é o índice)
                width='stretch',
                key="editor_lancamentos"
            )
            
            # Botão para Salvar (Verifica diferenças)
            if st.button("💾 Salvar Classificações"):
                with st.spinner("Atualizando dados..."):
                    # Otimização: bulk update ao invés de N queries individuais
                    updates = []

                    for row in edited_df.itertuples():
                        lanc_id = row.Index
                        # Busca original no banco usando o ID do índice
                        lanc_db = session.query(ExtratoBB).get(lanc_id)

                        if not lanc_db:
                            continue

                        # Reconstrói formato visual para comparar
                        st_visual_db = "🟢 Baixado" if str(lanc_db.status).lower() == 'baixado' else "🟡 Pendente"
                        if not lanc_db.status: st_visual_db = "⚪ (Vazio)"

                        mudou = False
                        update_dict = {'id': lanc_id}

                        # Status Check
                        if row.Status != st_visual_db:
                            # Remove emoji para salvar limpo
                            update_dict['status'] = row.Status.replace("🟢 ", "").replace("🟡 ", "").strip()
                            mudou = True

                        if lanc_db.tipo != row.Tipo:
                            update_dict['tipo'] = row.Tipo
                            mudou = True

                        if lanc_db.fatura != row.Fatura:
                            update_dict['fatura'] = row.Fatura
                            mudou = True

                        if mudou:
                            updates.append(update_dict)

                    alterados = len(updates)
                    if alterados > 0:
                        # Bulk update - MUITO mais rápido
                        session.bulk_update_mappings(ExtratoBB, updates)
                        session.commit()

                        # RECALCULA o ResumoMensal para atualizar os totais de entradas/saídas
                        tipos_ignorados = ['Aplicação Financeira', 'Aplicação', 'BB Rende Fácil']

                        # Busca todos os lançamentos do mês
                        lancamentos_mes = session.query(ExtratoBB).filter_by(
                            mes_referencia=resumo_selecionado.mes,
                            ano_referencia=resumo_selecionado.ano
                        ).all()

                        # Recalcula entradas e saídas
                        total_entradas = 0.0
                        total_saidas = 0.0
                        total_aportes = 0.0
                        total_valor_liquido = 0.0

                        for lanc in lancamentos_mes:
                            total_valor_liquido += lanc.valor

                            # Ignora aplicações
                            if lanc.tipo in tipos_ignorados:
                                continue

                            if lanc.valor > 0:
                                total_entradas += lanc.valor
                                # Separa aportes
                                if lanc.tipo == 'Aporte Capital':
                                    total_aportes += lanc.valor
                            elif lanc.valor < 0:
                                total_saidas += abs(lanc.valor)

                        total_entradas_sem_aportes = total_entradas - total_aportes

                        # Atualiza o resumo mensal
                        resumo_selecionado.total_entradas = total_entradas
                        resumo_selecionado.total_aportes = total_aportes
                        resumo_selecionado.total_entradas_sem_aportes = total_entradas_sem_aportes
                        resumo_selecionado.total_saidas = total_saidas
                        resumo_selecionado.total_valor = total_valor_liquido
                        session.add(resumo_selecionado)
                        session.commit()

                        st.success(f"✅ {alterados} lançamentos atualizados e resumo recalculado!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.info("Nenhuma alteração detectada.")
                        
        else:
            st.info("Nenhum lançamento encontrado com os filtros atuais.")
            
    else:
        st.info("Nenhum extrato importado ainda. Use a opção acima para importar um arquivo Excel do BB.")

    st.divider()

    # === BACKUP AUTOMÁTICO ===
    with st.expander("💾 Gerenciamento de Backups", expanded=False):
        from modules.finance.backup_manager import BackupManager

        backup_manager = BackupManager()
        backup_manager_hist = BackupManager(db_path=str(Path('data') / 'financeiro_historico.db'))

        # Abas
        tab_manual, tab_automatico, tab_restaurar = st.tabs(["📥 Backup Manual", "⚙️ Automático", "♻️ Restaurar"])

        with tab_manual:
            st.markdown("### Criar Backup Manual")
            col_bk1, col_bk2, col_bk3 = st.columns([3, 1, 1])

            with col_bk1:
                descricao_backup = st.text_input("Descrição do backup", placeholder="Ex: Antes de importar novos dados")

            with col_bk2:
                st.write("")  # Alinhamento
                if st.button("💾 Criar Backup", type="primary"):
                    with st.spinner("Criando backup..."):
                        resultado = backup_manager.criar_backup(descricao=descricao_backup or "Backup manual")

                        if resultado["sucesso"]:
                            st.success(f"✅ Backup criado com sucesso!")
                            st.info(f"📁 Arquivo: {resultado['metadata']['arquivo']}")
                            st.caption(f"📊 Tamanho: {resultado['metadata']['tamanho_mb']} MB")
                        else:
                            st.error(f"❌ Erro ao criar backup: {resultado['erro']}")

            with col_bk3:
                st.write("")  # Alinhamento
                if st.button("💾 Backup Histórico", type="secondary"):
                    with st.spinner("Criando backup do financeiro histórico..."):
                        resultado = backup_manager_hist.criar_backup(descricao=descricao_backup or "Backup historico manual")
                        if resultado["sucesso"]:
                            st.success("✅ Backup histórico criado.")
                            st.info(f"📁 Arquivo: {resultado['metadata']['arquivo']}")
                        else:
                            st.error(f"❌ Erro ao criar backup histórico: {resultado['erro']}")

            # Estatísticas
            st.markdown("### 📊 Estatísticas")
            stats = backup_manager.get_estatisticas()
            stats_hist = backup_manager_hist.get_estatisticas()

            col_st1, col_st2, col_st3, col_st4 = st.columns(4)
            with col_st1:
                st.metric("Total de Backups", stats["total_backups"])
            with col_st2:
                st.metric("Espaço Usado", f"{stats['tamanho_total_mb']} MB")
            with col_st3:
                if stats["ultimo_backup"]:
                    ultimo = datetime.fromisoformat(stats["ultimo_backup"]["datetime"])
                    st.metric("Último Backup", ultimo.strftime("%d/%m/%Y %H:%M"))
                else:
                    st.metric("Último Backup", "Nenhum")
            with col_st4:
                hist_info = stats_hist.get("ultimo_backup")
                label_hist = "Histórico: Nenhum" if not hist_info else datetime.fromisoformat(hist_info["datetime"]).strftime("%d/%m/%Y %H:%M")
                st.metric("Backup Histórico", label_hist)

        with tab_automatico:
            st.markdown("### ⚙️ Configurar Backup Automático")

            config_atual = backup_manager.config

            col_cfg1, col_cfg2 = st.columns(2)

            with col_cfg1:
                auto_enabled = st.checkbox("Ativar backup automático", value=config_atual.get("enabled", False))
                frequencia = st.selectbox("Frequência", ["daily", "weekly"],
                                        index=0 if config_atual.get("frequency") == "daily" else 1)
                frequencia_label = "Diário" if frequencia == "daily" else "Semanal (domingo)"

            with col_cfg2:
                hora = st.number_input("Hora do dia (0-23)", min_value=0, max_value=23,
                                      value=config_atual.get("hour", 2))
                keep_last = st.number_input("Manter últimos N backups", min_value=5, max_value=100,
                                           value=config_atual.get("keep_last", 30))

            if st.button("💾 Salvar Configuração"):
                backup_manager.configurar_backup_automatico(
                    enabled=auto_enabled,
                    frequency=frequencia,
                    hour=hora,
                    keep_last=keep_last
                )
                st.success(f"✅ Configuração salva! Backup {frequencia_label.lower()} às {hora}:00h")

                if auto_enabled:
                    backup_manager.iniciar_backup_automatico()
                    st.info("🚀 Serviço de backup automático iniciado!")

            st.divider()
            st.info(f"""
            **Configuração atual:**
            - Status: {'✅ Ativo' if config_atual.get('enabled') else '❌ Desativado'}
            - Frequência: {frequencia_label}
            - Horário: {config_atual.get('hour', 2)}:00h
            - Manter: {config_atual.get('keep_last', 30)} backups
            """)

        with tab_restaurar:
            st.markdown("### ♻️ Restaurar Backup")

            backups = backup_manager.listar_backups()

            if not backups:
                st.info("Nenhum backup disponível ainda. Crie um backup primeiro!")
            else:
                st.warning("⚠️ Restaurar um backup substituirá todos os dados atuais!")

                # Lista de backups
                for backup in backups:
                    with st.container():
                        col_b1, col_b2, col_b3, col_b4 = st.columns([2, 2, 1, 1])

                        backup_dt = datetime.fromisoformat(backup["datetime"])

                        with col_b1:
                            st.write(f"📅 **{backup_dt.strftime('%d/%m/%Y %H:%M')}**")
                        with col_b2:
                            st.caption(backup.get("descricao", ""))
                        with col_b3:
                            st.caption(f"{backup['tamanho_mb']} MB")
                        with col_b4:
                            if st.button("♻️ Restaurar", key=f"restore_{backup['timestamp']}"):
                                with st.spinner("Restaurando backup..."):
                                    resultado = backup_manager.restaurar_backup(backup["timestamp"])

                                    if resultado["sucesso"]:
                                        st.success("✅ Backup restaurado com sucesso!")
                                        time.sleep(2)
                                        st.rerun()
                                    else:
                                        st.error(f"❌ Erro: {resultado['erro']}")

                        st.divider()

    st.divider()

    # === ZONA DE PERIGO ===
    with st.expander("🗑️ Zona de Perigo - Limpeza de Dados"):
        st.warning("Cuidado: As ações abaixo são irreversíveis.")
        
        col_limp1, col_limp2 = st.columns(2)
        
        with col_limp1:
            # Opção para limpar mês específico
            meses_para_limpar = session.query(ResumoMensal).all()
            opcoes_limpeza = [f"{m.mes}/{m.ano}" for m in meses_para_limpar]
            
            sel_limpeza = st.selectbox("Selecionar Mês para Excluir", ["Selecione..."] + opcoes_limpeza)
            
            if st.button("Apagar Mês Selecionado", type="primary"):
                if sel_limpeza != "Selecione...":
                    try:
                        mes_del, ano_del = sel_limpeza.split('/')
                        # Delete logic
                        session.query(ExtratoBB).filter_by(mes_referencia=mes_del, ano_referencia=int(ano_del)).delete()
                        session.query(ResumoMensal).filter_by(mes=mes_del, ano=int(ano_del)).delete()
                        session.commit()
                        st.success(f"Dados de {sel_limpeza} apagados!")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao apagar: {e}")
        
        with col_limp2:
            st.write("Apagar TUDO")
            if st.button("💣 Apagar TODOS os dados financeiros", type="primary"):
                session.query(ExtratoBB).delete()
                session.query(ResumoMensal).delete()
                session.commit()
                st.success("Banco financeiro completamente zerado!")
                time.sleep(1)
                st.rerun()

    session.close()

elif page == "Configurações":
    st.header("⚙️ Configurações do Sistema")
    
    session = get_session()
    
    # --- Seção 1: Configuração IA ---
    st.subheader("🤖 Configuração da IA")
    st.markdown("""
    Configure a chave de API do OpenRouter (IA do sistema).
    """)
    
    st.markdown("**🆓 OpenRouter**")
    st.caption("Modelos gratuitos disponíveis no OpenRouter (sujeitos às políticas do provedor)")
        
    config_openrouter = session.query(Configuracao).filter_by(chave='openrouter_api_key').first()
    if not config_openrouter:
        config_openrouter = Configuracao(chave='openrouter_api_key', valor='')
        session.add(config_openrouter)
        session.commit()
        
    nova_openrouter_key = st.text_input("OpenRouter API Key", value=config_openrouter.valor, type="password", key="openrouter_key")
    if st.button("Salvar OpenRouter Key"):
        config_openrouter.valor = nova_openrouter_key
        session.commit()
        st.success("✅ OpenRouter Key salva!")
        
    st.caption("Obtenha em: https://openrouter.ai/keys")
        
    st.divider()
        
    # --- Seção 2: Notificações WhatsApp (Multi-usuário) ---
    st.subheader("🔔 Notificações WhatsApp (CallMeBot)")
    st.markdown("""
    Gerencie a lista de pessoas que receberão os alertas de licitações.
    """)
    
    import json
    
    # Carrega configuração de contatos (Lista JSON)
    config_contacts = session.query(Configuracao).filter_by(chave='whatsapp_contacts').first()
    
    # Migração Automática (Se tiver configuração antiga, converte para lista)
    if not config_contacts:
        old_phone = session.query(Configuracao).filter_by(chave='whatsapp_phone').first()
        old_key = session.query(Configuracao).filter_by(chave='whatsapp_apikey').first()
        
        initial_list = []
        if old_phone and old_key and old_phone.valor:
            initial_list.append({"nome": "Principal (Migrado)", "phone": old_phone.valor, "apikey": old_key.valor})
            
        config_contacts = Configuracao(chave='whatsapp_contacts', valor=json.dumps(initial_list))
        session.add(config_contacts)
        session.commit()
    
    # Parse da lista
    try:
        contacts_list = json.loads(config_contacts.valor) if config_contacts.valor else []
    except:
        contacts_list = []
    
    # Lista de Contatos
    if contacts_list:
        msg_padrao = "🔔 Teste de notificação Medcal realizado com sucesso!"
        msg_custom_global = st.text_area(
            "Mensagem de teste (será enviada para todos)",
            value=msg_padrao,
            key="msg_wpp_global"
        )
        st.write("**Contatos Cadastrados:**")
        for idx, contact in enumerate(contacts_list):
            with st.container():
                c1, c2, c3, c4 = st.columns([3, 3, 1, 1])
                c1.markdown(f"👤 **{contact.get('nome', 'Sem Nome')}**")
                c2.text(f"📞 {contact.get('phone', '')}")
                
                if c3.button("🔔", key=f"test_wpp_{idx}", help="Enviar mensagem de teste"):
                    notifier = WhatsAppNotifier(contact.get('phone'), contact.get('apikey'))
                    texto = (msg_custom_global or "").strip() or msg_padrao
                    if notifier.enviar_mensagem(texto):
                        st.toast(f"Mensagem enviada para {contact.get('nome')}!", icon="✅")
                    else:
                        erro_msg = notifier.ultimo_erro or "Erro desconhecido"
                        st.error(f"Erro ao enviar para {contact.get('nome')}: {erro_msg}")

                if c4.button("🗑️", key=f"del_wpp_{idx}", help="Excluir este contato"):
                    contacts_list.pop(idx)
                    config_contacts.valor = json.dumps(contacts_list)
                    session.commit()
                    st.rerun()
                st.divider()
    else:
        st.info("Nenhum contato cadastrado ainda.")
        
    # Formulário para Adicionar
    with st.expander("➕ Adicionar Novo Contato", expanded=False):
        with st.form("form_add_wpp"):
            st.markdown("Para obter a API Key: Adicione **+34 644 56 55 18** e envie `I allow callmebot to send me messages`.")
            col_n1, col_n2 = st.columns(2)
            n_nome = col_n1.text_input("Nome do Contato")
            n_phone = col_n2.text_input("Número (com DDI e DDD)", placeholder="5584999999999")
            n_key = st.text_input("API Key (CallMeBot)", type="password")
            
            if st.form_submit_button("Salvar Contato"):
                if n_nome and n_phone and n_key:
                    contacts_list.append({"nome": n_nome, "phone": n_phone, "apikey": n_key})
                    config_contacts.valor = json.dumps(contacts_list)
                    session.commit()
                    st.success("Contato adicionado com sucesso!")
                    st.rerun()
                else:
                    st.error("Preencha todos os campos obrigatórios.")
                    
    session.close()
