import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import io
from pypdf import PdfReader
import re
import unicodedata
import json
import google.generativeai as genai
from modules.database.database import get_session, Configuracao
from .pncp_client import PNCPClient

class ExternalScraper:
    """Classe base para scrapers de portais externos"""
    def buscar_oportunidades(self):
        raise NotImplementedError("Método buscar_oportunidades deve ser implementado")


class DiarioMunicipalScraper(ExternalScraper):
    """
    Classe base para scrapers do sistema diariomunicipal.com.br (FEMURN, FAMUP, AMUPE, etc).
    """
    def __init__(self, base_url, uf, origem_nome):
        self.BASE_URL = base_url
        self.UF = uf
        self.ORIGEM = origem_nome

    def _get_pdf_url(self, soup):
        # 1. Tenta link direto
        link_tag = soup.find('a', id='downloadPdf')
        if link_tag: return link_tag.get('href')
        
        # 2. Tenta input hidden
        input_tag = soup.find('input', id='urlPdf')
        if input_tag: return input_tag.get('value')
        
        # 3. Tenta imagem da capa (hack solicitado pelo usuário)
        # Ex: .../publicado_...pdf.jpg -> .../publicado_...pdf
        img_tag = soup.find('img', class_='capa')
        if img_tag:
            src = img_tag.get('src')
            if src:
                if src.endswith('.jpg'):
                    return src[:-4]
                return src
        
        return None

    def _enrich_with_ai(self, texto_aviso):
        """Usa Gemini para extrair itens e resumir objeto"""
        try:
            session = get_session()
            config = session.query(Configuracao).filter_by(chave='gemini_api_key').first()
            session.close()
            
            if not config or not config.valor:
                return None

            genai.configure(api_key=config.valor)
            model = genai.GenerativeModel('gemini-2.0-flash')
            
            prompt = f"""
            Analise o seguinte aviso de licitação extraído de um Diário Oficial.
            
            Tarefa:
            1. Identifique o Objeto principal de forma resumida.
            2. Extraia a lista de itens/produtos (se houver) com quantidade estimada.
            3. Se não houver itens explícitos, retorne lista vazia.
            
            Texto:
            {texto_aviso[:8000]}            
            Retorne APENAS um JSON válido no formato:
            {{
                "objeto_resumido": "...",
                "itens": [
                    {{"descricao": "Nome do Item", "quantidade": 100, "unidade": "UN", "valor_estimado": 0.0, "valor_unitario": 0.0}}
                ]
            }}
            """
            
            response = model.generate_content(prompt)
            raw_json = response.text.replace('```json', '').replace('```', '').strip()
            
            # Tenta limpar o JSON se vier sujo
            if '{' in raw_json:
                raw_json = raw_json[raw_json.find('{'):raw_json.rfind('}')+1]
                
            data = json.loads(raw_json)
            return data
            
        except Exception as e:
            print(f"Erro na IA (Enrich): {e}")
            return None

    def buscar_oportunidades(self, termos_busca=None, termos_negativos=None):
        """
        Baixa o PDF do dia e busca por termos chave.
        """
        resultados = []
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            
            # 1. Fetch Homepage
            response = requests.get(self.BASE_URL, headers=headers, timeout=15, verify=False)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 2. Find PDF Link
            pdf_url = self._get_pdf_url(soup)
            
            if not pdf_url:
                return [{
                    "pncp_id": f"{self.ORIGEM}-ERROR",
                    "orgao": self.ORIGEM,
                    "uf": self.UF,
                    "modalidade": "Erro",
                    "data_sessao": datetime.now().isoformat(),
                    "data_publicacao": datetime.now().isoformat(),
                    "objeto": "Não foi possível encontrar o link do PDF do dia.",
                    "link": self.BASE_URL,
                    "itens": [],
                    "origem": self.ORIGEM
                }]

            # 3. Download PDF
            pdf_response = requests.get(pdf_url, headers=headers, timeout=60, verify=False)
            pdf_response.raise_for_status()
            
            # 4. Read PDF
            f = io.BytesIO(pdf_response.content)
            reader = PdfReader(f)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            
            # Helper to normalize text (remove accents)
            def normalize_text(text):
                if not text: return ""
                return unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('ASCII').upper()

            text_normalized = normalize_text(text)
            
            # 5. Search Terms & Extract Notices
            if termos_busca is None:
                termos_busca = PNCPClient.TERMOS_PRIORITARIOS
            
            terms_to_search_norm = [normalize_text(t) for t in termos_busca if t and t.strip()]
            
            terms_negativos_norm = []
            if termos_negativos:
                terms_negativos_norm = [normalize_text(t) for t in termos_negativos]

            # Compile Regex Patterns
            positive_pattern = None
            if terms_to_search_norm:
                terms_to_search_norm.sort(key=len, reverse=True)
                positive_pattern = re.compile(r'\b(?:' + '|'.join(map(re.escape, terms_to_search_norm)) + r')\b')

            negative_pattern = None
            if terms_negativos_norm:
                terms_negativos_norm.sort(key=len, reverse=True)
                negative_pattern = re.compile(r'\b(?:' + '|'.join(map(re.escape, terms_negativos_norm)) + r')\b')

            # Split text into "notices" using "Código Identificador:" as delimiter
            chunks = re.split(r'(Código Identificador:\s*[\w\d]+)', text)
            
            if len(chunks) < 2:
                # Use Regex Search on normalized text (Full Text Fallback)
                if positive_pattern and positive_pattern.search(text_normalized):
                     if not (negative_pattern and negative_pattern.search(text_normalized)):
                        resultados.append({
                            "pncp_id": f"{self.ORIGEM}-{datetime.now().strftime('%Y%m%d')}-FULL",
                            "orgao": f"Municípios {self.UF} ({self.ORIGEM})",
                            "uf": self.UF,
                            "modalidade": "Diário Oficial",
                            "data_sessao": datetime.now().isoformat(),
                            "data_publicacao": datetime.now().isoformat(),
                            "objeto": text[:5000] + "... (Texto muito longo, verifique o PDF)",
                            "link": pdf_url,
                            "itens": [],
                            "origem": self.ORIGEM
                        })
            else:
                # Reconstruct notices
                for i in range(0, len(chunks)-1, 2):
                    body = chunks[i]
                    code = chunks[i+1]
                    full_notice = body + "\n" + code
                    full_notice_clean = re.sub(r'\n+', '\n', full_notice).strip()
                    full_notice_norm = normalize_text(full_notice_clean)
                    
                    if positive_pattern and positive_pattern.search(full_notice_norm):
                        if negative_pattern and negative_pattern.search(full_notice_norm):
                            continue

                        code_match = re.search(r'Código Identificador:\s*([\w\d]+)', code)
                        code_id = code_match.group(1) if code_match else f"UNK-{i}"
                        
                        # Extract Orgao (Heuristic)
                        orgao_name = f"Município {self.UF} ({self.ORIGEM})"
                        patterns_orgao = [
                            r'(PREFEITURA MUNICIPAL (?:DE|DA|DO) [^\n]+)',
                            r'(CÂMARA MUNICIPAL (?:DE|DA|DO) [^\n]+)',
                            r'(CAMARA MUNICIPAL (?:DE|DA|DO) [^\n]+)',
                            r'(FUNDO MUNICIPAL (?:DE|DA|DO) [^\n]+)',
                            r'(CONSÓRCIO INTERMUNICIPAL [^\n]+)',
                            r'(CONSORCIO INTERMUNICIPAL [^\n]+)',
                            r'(SERVIÇO AUTÔNOMO [^\n]+)'
                        ]
                        
                        for pat in patterns_orgao:
                            match = re.search(pat, full_notice_clean, re.IGNORECASE)
                            if match:
                                orgao_name = match.group(1).strip()
                                break

                        # Extract Modalidade (Heuristic)
                        if "INEXIGIBILIDADE" in full_notice_norm: 
                            continue # Ignora Inexigibilidade

                        modalidade = "Diário Oficial"
                        if "DISPENSA" in full_notice_norm: modalidade = "Dispensa"
                        elif "PREGAO" in full_notice_norm: modalidade = "Pregão"
                        elif "CONCORRENCIA" in full_notice_norm: modalidade = "Concorrência"
                        elif "TOMADA DE PRECO" in full_notice_norm: modalidade = "Tomada de Preço"
                        elif "CHAMADA PUBLICA" in full_notice_norm: modalidade = "Chamada Pública"
                        elif "AVISO DE LICITACAO" in full_notice_norm: modalidade = "Aviso de Licitação"
                        elif "EXTRATO" in full_notice_norm: modalidade = "Extrato/Contrato"

                        # ============================================================
                        # FILTRO RIGOROSO: Só aceita documentos de LICITAÇÃO ABERTA
                        # ============================================================
                        
                        # Termos que indicam LICITAÇÃO ABERTA (deve ter pelo menos um)
                        termos_licitacao_valida = [
                            "AVISO DE LICITACAO", "AVISO DE LICITAÇÃO",
                            "PREGAO ELETRONICO", "PREGÃO ELETRÔNICO", "PREGAO PRESENCIAL", "PREGÃO PRESENCIAL",
                            "DISPENSA DE LICITACAO", "DISPENSA DE LICITAÇÃO", "DISPENSA ELETRONICA", "DISPENSA ELETRÔNICA",
                            "TOMADA DE PRECO", "TOMADA DE PREÇO", "TOMADA DE PREÇOS",
                            "CONCORRENCIA PUBLICA", "CONCORRÊNCIA PÚBLICA",
                            "CHAMAMENTO PUBLICO", "CHAMAMENTO PÚBLICO",
                            "CHAMADA PUBLICA", "CHAMADA PÚBLICA",
                            "EDITAL DE LICITACAO", "EDITAL DE LICITAÇÃO",
                            "PROCESSO LICITATORIO", "PROCESSO LICITATÓRIO"
                        ]
                        
                        # Verifica se é uma licitação válida
                        eh_licitacao_valida = any(termo in full_notice_norm for termo in termos_licitacao_valida)
                        
                        if not eh_licitacao_valida:
                            continue  # Pula documentos que não são licitações abertas
                        
                        # Termos que indicam documentos NÃO desejados (mesmo que tenham termos positivos)
                        termos_documento_invalido = [
                            "NOTIFICACAO", "NOTIFICAÇÃO",
                            "ATRASO NA ENTREGA", "ATRASO DE ENTREGA",
                            "PENALIDADE", "PENALIDADES", "MULTA", "ADVERTENCIA", "ADVERTÊNCIA",
                            "RESCISAO", "RESCISÃO", "RESCISAO DE CONTRATO", "RESCISÃO DE CONTRATO",
                            "EXTRATO DE CONTRATO", "EXTRATO DO CONTRATO",
                            "EXTRATO DE TERMO ADITIVO", "TERMO ADITIVO",
                            "RATIFICACAO", "RATIFICAÇÃO", "HOMOLOGACAO", "HOMOLOGAÇÃO",
                            "ADJUDICACAO", "ADJUDICAÇÃO",
                            "RESULTADO DE JULGAMENTO", "RESULTADO DO JULGAMENTO",
                            "ATA DE REGISTRO DE PRECO", "ATA DE REGISTRO DE PREÇO",
                            "PUBLICACAO DE ATA", "PUBLICAÇÃO DE ATA",
                            "ERRATA", "RETIFICACAO", "RETIFICAÇÃO",
                            "CONVOCACAO PARA ASSINATURA", "CONVOCAÇÃO PARA ASSINATURA",
                            "ORDEM DE FORNECIMENTO", "ORDEM DE SERVICO", "ORDEM DE SERVIÇO",
                            "DESPACHO", "PARECER", "PORTARIA"
                        ]
                        
                        # Se contém termo de documento inválido, pula
                        tem_termo_invalido = any(termo in full_notice_norm for termo in termos_documento_invalido)
                        
                        if tem_termo_invalido:
                            continue  # Pula notificações, extratos, aditivos, etc.

                        # FILTRO ADICIONAL: Detecta contratos já assinados (com contratado)
                        # Padrões que indicam que já tem vencedor/contratado
                        skip_patterns = [
                            r'CONTRATAD[OA]\s*:\s*[A-Z]',  # "Contratado: NOME" ou "Contratada: NOME"
                            r'CONTRATAD[OA]\s*\([Aa]\)\s*:\s*[A-Z]',  # "Contratado (a): NOME"
                            r'VENCEDOR\s*:\s*[A-Z]',  # "Vencedor: NOME"
                            r'EMPRESA\s+VENCEDORA\s*:\s*[A-Z]',  # "Empresa Vencedora: NOME"
                        ]

                        should_skip = False
                        for skip_pat in skip_patterns:
                            if re.search(skip_pat, full_notice_clean, re.IGNORECASE):
                                should_skip = True
                                break

                        if should_skip:
                            continue  # Pula este aviso, já tem contratado
                        
                        # === IA ENRICHMENT ===
                        # Usa Gemini para estruturar o aviso (itens e objeto limpo)
                        ai_data = self._enrich_with_ai(full_notice_clean)
                        
                        objeto_final = full_notice_clean
                        itens_final = []
                        
                        if ai_data:
                            if ai_data.get('objeto_resumido'):
                                objeto_final = ai_data['objeto_resumido'] + "\n\n[IA] Texto Original Resumido."
                            
                            if ai_data.get('itens'):
                                for it in ai_data['itens']:
                                    itens_final.append({
                                        "numero": 0, 
                                        "descricao": it.get('descricao', 'Item sem nome'),
                                        "quantidade": it.get('quantidade', 1.0),
                                        "unidade": it.get('unidade', 'UN'),
                                        "valor_estimado": it.get('valor_estimado', 0.0),
                                        "valor_unitario": it.get('valor_unitario', 0.0)
                                    })

                        resultados.append({
                            "pncp_id": f"{self.ORIGEM}-{datetime.now().strftime('%Y%m%d')}-{code_id}",
                            "orgao": orgao_name,
                            "uf": self.UF,
                            "modalidade": f"{modalidade} ({self.ORIGEM})",
                            "data_sessao": datetime.now().isoformat(),
                            "data_publicacao": datetime.now().isoformat(),
                            "objeto": objeto_final,
                            "link": pdf_url,
                            "itens": itens_final, # Agora populado pela IA!
                            "origem": self.ORIGEM
                        })
            
            # Se não encontrou nada relevante, retorna lista vazia (não cria registro de debug)
            # O usuário será informado no dashboard que "0 resultados foram encontrados"

        except Exception as e:
            # Log do erro mas não cria registro falso
            print(f"⚠️ Erro ao processar PDF do {self.ORIGEM}: {str(e)}")
            
        return resultados

class FemurnScraper(DiarioMunicipalScraper):
    def __init__(self):
        super().__init__("https://www.diariomunicipal.com.br/femurn/", "RN", "FEMURN")

class FamupScraper(DiarioMunicipalScraper):
    def __init__(self):
        super().__init__("https://www.diariomunicipal.com.br/famup/", "PB", "FAMUP")

class AmupeScraper(DiarioMunicipalScraper):
    def __init__(self):
        super().__init__("https://www.diariomunicipal.com.br/amupe/", "PE", "AMUPE")

# Scrapers de Alagoas
class AmaScraper(DiarioMunicipalScraper):
    def __init__(self):
        super().__init__("https://www.diariomunicipal.com.br/ama/", "AL", "AMA")

class MaceioScraper(DiarioMunicipalScraper):
    def __init__(self):
        super().__init__("https://www.diariomunicipal.com.br/maceio/", "AL", "Maceió")

class MaceioInvesteScraper(DiarioMunicipalScraper):
    def __init__(self):
        super().__init__("https://www.diariomunicipal.com.br/maceioinveste/", "AL", "MaceióInveste")

class MaceioSaudeScraper(DiarioMunicipalScraper):
    def __init__(self):
        super().__init__("https://www.diariomunicipal.com.br/maceiosaude/", "AL", "MaceióSaúde")