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
        Gate: exige licitacao aberta (aviso/pregao/dispensa/edital) antes de termos positivos/negativos.
        """
        resultados = []
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            response = requests.get(self.BASE_URL, headers=headers, timeout=15, verify=False)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            pdf_url = self._get_pdf_url(soup)
            if not pdf_url:
                return [{
                    "pncp_id": f"{self.ORIGEM}-ERROR",
                    "orgao": self.ORIGEM,
                    "uf": self.UF,
                    "modalidade": "Erro",
                    "data_sessao": datetime.now().isoformat(),
                    "data_publicacao": datetime.now().isoformat(),
                    "objeto": "Nao foi possivel encontrar o link do PDF do dia.",
                    "link": self.BASE_URL,
                    "itens": [],
                    "origem": self.ORIGEM
                }]

            pdf_response = requests.get(pdf_url, headers=headers, timeout=60, verify=False)
            pdf_response.raise_for_status()

            f = io.BytesIO(pdf_response.content)
            reader = PdfReader(f)
            text = "".join(((page.extract_text() or "") + "\n") for page in reader.pages)

            def normalize_text(txt: str) -> str:
                if not txt:
                    return ""
                return unicodedata.normalize('NFKD', txt).encode('ASCII', 'ignore').decode('ASCII').upper()

            text_normalized = normalize_text(text)

            if termos_busca is None:
                termos_busca = PNCPClient.TERMOS_PRIORITARIOS  # foco estrito

            terms_to_search_norm = [normalize_text(t) for t in termos_busca if t and t.strip()]
            terms_negativos_norm = [normalize_text(t) for t in termos_negativos] if termos_negativos else []

            positive_pattern = None
            if terms_to_search_norm:
                terms_to_search_norm.sort(key=len, reverse=True)
                positive_pattern = re.compile(r'\b(?:' + '|'.join(map(re.escape, terms_to_search_norm)) + r')\b')

            negative_pattern = None
            if terms_negativos_norm:
                terms_negativos_norm.sort(key=len, reverse=True)
                negative_pattern = re.compile(r'\b(?:' + '|'.join(map(re.escape, terms_negativos_norm)) + r')\b')

            termos_licitacao_valida = [
                "AVISO DE LICITACAO",
                "PREGAO ELETRONICO", "PREGAO PRESENCIAL",
                "DISPENSA DE LICITACAO", "DISPENSA ELETRONICA",
                "TOMADA DE PRECO", "TOMADA DE PRECOS",
                "CONCORRENCIA PUBLICA",
                "CHAMAMENTO PUBLICO", "CHAMADA PUBLICA",
                "EDITAL DE LICITACAO",
                "PROCESSO LICITATORIO"
            ]

            def eh_licitacao_aberta(txt_norm: str) -> bool:
                return any(t in txt_norm for t in termos_licitacao_valida)

            chunks = re.split(r'(CODIGO IDENTIFICADOR:\s*[\w\d]+)', text_normalized)

            if len(chunks) < 2:
                if eh_licitacao_aberta(text_normalized):
                    if positive_pattern and positive_pattern.search(text_normalized):
                        if not (negative_pattern and negative_pattern.search(text_normalized)):
                            resultados.append({
                                "pncp_id": f"{self.ORIGEM}-{datetime.now().strftime('%Y%m%d')}-FULL",
                                "orgao": f"Municipios {self.UF} ({self.ORIGEM})",
                                "uf": self.UF,
                                "modalidade": "Diario Oficial",
                                "data_sessao": datetime.now().isoformat(),
                                "data_publicacao": datetime.now().isoformat(),
                                "objeto": text[:5000] + "... (Texto muito longo, verifique o PDF)",
                                "link": pdf_url,
                                "itens": [],
                                "origem": self.ORIGEM
                            })
            else:
                for i in range(0, len(chunks)-1, 2):
                    body = chunks[i]
                    code = chunks[i+1]
                    full_notice_clean = re.sub(r'\n+', '\n', body + "\n" + code).strip()
                    full_notice_norm = normalize_text(full_notice_clean)

                    if not eh_licitacao_aberta(full_notice_norm):
                        continue
                    if positive_pattern and not positive_pattern.search(full_notice_norm):
                        continue
                    if negative_pattern and negative_pattern.search(full_notice_norm):
                        continue

                    code_match = re.search(r'CODIGO IDENTIFICADOR:\s*([\w\d]+)', full_notice_norm)
                    code_id = code_match.group(1) if code_match else f"UNK-{i}"

                    orgao_name = f"Municipio {self.UF} ({self.ORIGEM})"
                    patterns_orgao = [
                        r'(PREFEITURA MUNICIPAL (?:DE|DA|DO) [^\n]+)',
                        r'(CAMARA MUNICIPAL (?:DE|DA|DO) [^\n]+)',
                        r'(FUNDO MUNICIPAL (?:DE|DA|DO) [^\n]+)',
                        r'(CONSORCIO INTERMUNICIPAL [^\n]+)',
                        r'(SERVICO AUTONOMO [^\n]+)'
                    ]
                    for pat in patterns_orgao:
                        match = re.search(pat, full_notice_clean, re.IGNORECASE)
                        if match:
                            orgao_name = match.group(1).strip()
                            break

                    if "INEXIGIBILIDADE" in full_notice_norm:
                        continue

                    modalidade = "Diario Oficial"
                    if "DISPENSA" in full_notice_norm:
                        modalidade = "Dispensa"
                    elif "PREGAO" in full_notice_norm:
                        modalidade = "Pregao"
                    elif "CONCORRENCIA" in full_notice_norm:
                        modalidade = "Concorrencia"
                    elif "TOMADA DE PRECO" in full_notice_norm:
                        modalidade = "Tomada de Preco"
                    elif "CHAMADA PUBLICA" in full_notice_norm:
                        modalidade = "Chamada Publica"
                    elif "AVISO DE LICITACAO" in full_notice_norm:
                        modalidade = "Aviso de Licitacao"
                    elif "EXTRATO" in full_notice_norm:
                        modalidade = "Extrato/Contrato"

                    termos_documento_invalido = [
                        "NOTIFICACAO",
                        "ATRASO NA ENTREGA", "ATRASO DE ENTREGA",
                        "PENALIDADE", "PENALIDADES", "MULTA", "ADVERTENCIA",
                        "RESCISAO", "RESCISAO DE CONTRATO",
                        "EXTRATO DE CONTRATO", "EXTRATO DO CONTRATO",
                        "EXTRATO DE TERMO ADITIVO", "TERMO ADITIVO",
                        "RATIFICACAO", "HOMOLOGACAO",
                        "ADJUDICACAO",
                        "RESULTADO DE JULGAMENTO",
                        "ATA DE REGISTRO DE PRECO",
                        "PUBLICACAO DE ATA",
                        "ERRATA", "RETIFICACAO",
                        "CONVOCACAO PARA ASSINATURA",
                        "ORDEM DE FORNECIMENTO", "ORDEM DE SERVICO",
                        "DESPACHO", "PARECER", "PORTARIA"
                    ]
                    if any(termo in full_notice_norm for termo in termos_documento_invalido):
                        continue

                    skip_patterns = [
                        r'CONTRATAD[OA]\s*:\s*[A-Z]',
                        r'CONTRATAD[OA]\s*\([Aa]\)\s*:\s*[A-Z]',
                        r'VENCEDOR\s*:\s*[A-Z]',
                        r'EMPRESA\s+VENCEDORA\s*:\s*[A-Z]',
                    ]
                    if any(re.search(pat, full_notice_clean, re.IGNORECASE) for pat in skip_patterns):
                        continue

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
                        "itens": itens_final,
                        "origem": self.ORIGEM
                    })

        except Exception as e:
            print(f"[WARN] Erro ao processar PDF do {self.ORIGEM}: {str(e)}")
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
