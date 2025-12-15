import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, date
import io
from pypdf import PdfReader
import re
import unicodedata
import json
import google.generativeai as genai
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Suprime avisos de SSL inseguro (comuns em sites de diários municipais)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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
        
        # Configura sessão com retries para maior robustez
        self.session = requests.Session()
        retries = Retry(total=5, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount('https://', adapter)
        self.session.mount('http://', adapter)

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
            # Aumentado timeout para 30s e usando session com retry
            response = self.session.get(self.BASE_URL, headers=headers, timeout=30, verify=False)
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

            # Aumentado timeout para 90s para download de PDF
            pdf_response = self.session.get(pdf_url, headers=headers, timeout=90, verify=False)
            pdf_response.raise_for_status()

            f = io.BytesIO(pdf_response.content)
            reader = PdfReader(f)
            text = "".join(((page.extract_text() or "") + "\n") for page in reader.pages)

            def normalize_text(txt: str) -> str:
                if not txt:
                    return ""
                return unicodedata.normalize('NFKD', txt).encode('ASCII', 'ignore').decode('ASCII').upper()

            text_normalized = normalize_text(text)
            
            # DIAGNOSTICO: Logs para debug
            print(f"[{self.ORIGEM}] PDF baixado: {len(text)} caracteres, {len(reader.pages)} páginas")
            
            # Verifica termos importantes
            count_hospitalar = text_normalized.count("MATERIAL HOSPITALAR") + text_normalized.count("MATERIAL MEDICO HOSPITALAR")
            count_pregao = text_normalized.count("PREGAO ELETRONICO")
            count_aviso = text_normalized.count("AVISO DE LICITACAO")
            print(f"[{self.ORIGEM}] Termos encontrados: MATERIAL HOSPITALAR={count_hospitalar}, PREGAO={count_pregao}, AVISO={count_aviso}")

            if termos_busca is None:
                termos_busca = PNCPClient.TERMOS_PRIORITARIOS  # foco estrito

            terms_to_search_norm = [normalize_text(t) for t in termos_busca if t and t.strip()]
            terms_negativos_norm = [normalize_text(t) for t in termos_negativos] if termos_negativos else []
            
            print(f"[{self.ORIGEM}] Buscando {len(terms_to_search_norm)} termos positivos, {len(terms_negativos_norm)} negativos")

            termos_licitacao_valida = [
                "AVISO DE LICITACAO",
                "PREGAO ELETRONICO", "PREGAO PRESENCIAL",
                "DISPENSA ELETRONICA", 
                "SETOR DE LICITAÇOES",
            ]

            def eh_licitacao_aberta(txt_norm: str) -> bool:
                return any(t in txt_norm for t in termos_licitacao_valida)
            
            def tem_termo_positivo(txt_norm: str) -> bool:
                """Verifica se tem algum termo positivo (busca simples por substring)"""
                # Primeiro: busca direta por termos específicos
                for termo in terms_to_search_norm:
                    if termo in txt_norm:
                        return True
                
                # Segundo: busca por combinação EQUIPAMENTOS + CONTEXTO SAÚDE
                # (para pegar "Aquisição de equipamentos... para Hospital Municipal")
                contexto_saude = [
                    "HOSPITAL", "SAUDE", "UBS", "UNIDADE BASICA",
                    "SECRETARIA DE SAUDE", "FUNDO MUNICIPAL DE SAUDE",
                    "ATENCAO PRIMARIA", "AMBULATORIO", "PRONTO SOCORRO"
                ]
                
                if "EQUIPAMENTO" in txt_norm:
                    for ctx in contexto_saude:
                        if ctx in txt_norm:
                            return True
                
                return False
            
            def tem_termo_negativo(txt_norm: str) -> bool:
                """Verifica se tem algum termo negativo"""
                for termo in terms_negativos_norm:
                    if termo in txt_norm:
                        return True
                return False

            # Tenta dividir por diferentes padrões de separador
            separadores = [
                r'(CODIGO IDENTIFICADOR:\s*[\w\d]+)',
                r'(Código Identificador:\s*[\w\d]+)',
                r'(PREFEITURA MUNICIPAL (?:DE|DA|DO)\s+[A-Z]+)',  # Cada prefeitura é um aviso
            ]
            
            chunks = [text_normalized]  # Default: PDF inteiro
            for sep in separadores:
                test_chunks = re.split(sep, text_normalized, flags=re.IGNORECASE)
                if len(test_chunks) > 2:
                    chunks = test_chunks
                    print(f"[{self.ORIGEM}] PDF dividido em {len(chunks)//2} avisos usando: {sep[:30]}...")
                    break
            
            # Se não conseguiu dividir, tenta por "AVISO DE LICITACAO"
            if len(chunks) <= 2:
                aviso_chunks = re.split(r'(AVISO DE LICITAC[AÃ]O)', text_normalized, flags=re.IGNORECASE)
                if len(aviso_chunks) > 2:
                    chunks = aviso_chunks
                    print(f"[{self.ORIGEM}] PDF dividido em {len(chunks)//2} avisos por 'AVISO DE LICITACAO'")

            if len(chunks) <= 2:
                # PDF não foi dividido - processa inteiro buscando licitações
                print(f"[{self.ORIGEM}] PDF não dividido - buscando no texto completo...")
                
                if eh_licitacao_aberta(text_normalized) and tem_termo_positivo(text_normalized):
                    if not tem_termo_negativo(text_normalized):
                        # Encontra todos os avisos de licitação no texto
                        avisos = re.findall(
                            r'((?:AVISO DE LICITAC[AÃ]O|PREGAO ELETRONICO|DISPENSA)[^\n]*(?:\n(?!AVISO DE LICITAC|PREGAO ELETRONICO|DISPENSA)[^\n]*){0,50})',
                            text_normalized,
                            flags=re.IGNORECASE
                        )
                        
                        if avisos:
                            for idx, aviso in enumerate(avisos):
                                if tem_termo_positivo(aviso) and not tem_termo_negativo(aviso):
                                    # Extrai nome do órgão
                                    orgao_match = re.search(r'PREFEITURA MUNICIPAL (?:DE|DA|DO)\s+([A-Z]+)', aviso)
                                    orgao_name = f"Prefeitura de {orgao_match.group(1)}" if orgao_match else f"Municipio {self.UF}"
                                    
                                    resultados.append({
                                        "pncp_id": f"{self.ORIGEM}-{datetime.now().strftime('%Y%m%d')}-{idx+1}",
                                        "orgao": orgao_name,
                                        "uf": self.UF,
                                        "modalidade": "Pregao" if "PREGAO" in aviso else "Diario Oficial",
                                        "data_sessao": datetime.now().isoformat(),
                                        "data_publicacao": datetime.now().isoformat(),
                                        "objeto": aviso[:2000],
                                        "link": pdf_url,
                                        "itens": [],
                                        "origem": self.ORIGEM
                                    })
                                    print(f"[{self.ORIGEM}] ✅ Encontrado: {orgao_name}")
                        else:
                            # Fallback: retorna o PDF inteiro como um resultado
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
                # PDF foi dividido - processa cada chunk
                avisos_licitacao = 0
                avisos_positivos = 0
                avisos_bloqueados_negativo = 0
                
                for i in range(0, len(chunks)-1, 2):
                    body = chunks[i]
                    code = chunks[i+1] if i+1 < len(chunks) else ""
                    full_notice_clean = re.sub(r'\n+', '\n', body + "\n" + code).strip()
                    full_notice_norm = normalize_text(full_notice_clean)

                    if not eh_licitacao_aberta(full_notice_norm):
                        continue
                    
                    avisos_licitacao += 1
                    
                    if not tem_termo_positivo(full_notice_norm):
                        continue
                    
                    avisos_positivos += 1
                    
                    # Sincroniza com a lista robusta do PNCP e adiciona termos específicos de Diários Oficiais
                    termos_negativos_diario = list(PNCPClient.TERMOS_NEGATIVOS_PADRAO)
                    
                    # Adiciona termos específicos que poluem Diários Oficiais (atos administrativos)
                    termos_negativos_diario.extend([
                        # Documentos administrativos (não são editais de abertura)
                        "INEXIGIBILIDADE",
                        "EXTRATO DE CONTRATO",
                        "EXTRATO DO CONTRATO", 
                        "EXTRATO DE ADITIVO",
                        "TERMO ADITIVO",
                        "HOMOLOGACAO",
                        "ADJUDICACAO",
                        "RATIFICACAO",
                        "RESULTADO DE JULGAMENTO",
                        "RESULTADO DO JULGAMENTO",
                        "RESCISAO DE CONTRATO",
                        "PENALIDADE",
                        "MULTA APLICADA",
                        "NOTIFICACAO DE",
                        "PORTARIA N",
                        "DECRETO N",
                        "LEI MUNICIPAL",
                        "ERRATA",
                        "RETIFICACAO",
                        
                        # Serviços que não interessam (Mão de Obra e Serviços Contínuos)
                        "MAO DE OBRA", 
                        "SERVICOS CONTINUOS", 
                        "DEDICACAO EXCLUSIVA",
                        "LOCACAO DE MAO DE OBRA",
                        "TERCEIRIZACAO DE MAO DE OBRA",
                        "APOIO ADMINISTRATIVO",
                        "RECEPCIONISTA",
                        "MOTORISTA",
                        "COPEIRA",
                        "SERVENTE",
                        
                        # Termos extras para garantir limpeza
                        "CONSULTORIA", "ASSESSORIA", "VIAGEM", "HOSPEDAGEM", "PASSAGEM",
                        "SHOW", "FESTA", "EVENTO", "PALCO", "SONORIZACAO",

                        # Termos específicos de Odontologia para reforçar bloqueio
                        "CONSULTORIO ODONTOLOGICO",
                        "CLINICA ODONTOLOGICA",
                        "MANUTENCAO ODONTOLOGICA",
                        "REPARO ODONTOLOGICO",
                        "EQUIPAMENTOS ODONTOLOGICOS",
                        "CADEIRA ODONTOLOGICA",

                        # Termos específicos de Material de Expediente/Papelaria
                        "PAPELARIA",
                        "RESMA DE PAPEL",
                        "CANETA",
                        "LAPIS",
                        "BLOCO DE ANOTACOES",
                        "CADERNO",
                        "GRAMPEADOR",
                        "PERFURADOR",
                        "CLIPE",
                        "PASTA ARQUIVO"
                    ])
                    
                    # Normaliza para comparação
                    termos_negativos_diario_norm = [normalize_text(t) for t in termos_negativos_diario]
                    
                    termo_neg_encontrado = None
                    for termo in termos_negativos_diario_norm:
                        if termo in full_notice_norm:
                            termo_neg_encontrado = termo
                            break
                    
                    if termo_neg_encontrado:
                        avisos_bloqueados_negativo += 1
                        if avisos_bloqueados_negativo <= 5:
                            # Extrai nome do órgão para o log
                            orgao_log = "?"
                            for pat in [r'PREFEITURA (?:MUNICIPAL )?(?:DE |DA |DO )?([A-Z\s]+)', r'FUNDO MUNICIPAL DE ([A-Z\s]+)']:
                                m = re.search(pat, full_notice_norm)
                                if m:
                                    orgao_log = m.group(1).strip()[:20]
                                    break
                            print(f"[{self.ORIGEM}] Bloqueado: '{termo_neg_encontrado}' em {orgao_log}")
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
                    print(f"[{self.ORIGEM}] ✅ Aprovado: {orgao_name[:50]}")
                
                # Log estatísticas
                print(f"[{self.ORIGEM}] Estatísticas: {avisos_licitacao} avisos de licitação, {avisos_positivos} com termo positivo, {avisos_bloqueados_negativo} bloqueados por negativo, {len(resultados)} aprovados")

        except Exception as e:
            print(f"[WARN] Erro ao processar PDF do {self.ORIGEM}: {str(e)}")
        return resultados


class BncScraper(ExternalScraper):
    """
    Busca licitações no BNC (bnccompras.com) via endpoint interno usado no widget.
    Filtra atividades relevantes de saúde/laboratório e estados informados.
    """
    BASE_URL = "https://bnccompras.com"
    SEARCH_PAGE = f"{BASE_URL}/Process/ProcessSearchActivity"
    API_URL = f"{BASE_URL}/Process/GetProcessByActivity"

    def __init__(self):
        self.session = requests.Session()
        retries = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount('https://', adapter)
        self.session.mount('http://', adapter)

    def _fetch_filters(self):
        resp = self.session.get(self.SEARCH_PAGE, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')

        atividades = []
        for opt in soup.select('#fkActivity option'):
            if opt.get('value'):
                atividades.append({
                    "id": opt.get('value'),
                    "nome": opt.text.strip().upper()
                })

        estados = {}
        for opt in soup.select('#fkState option'):
            if opt.get('value'):
                estados[opt.text.strip().upper()] = opt.get('value')

        return atividades, estados

    def _atividades_relevantes(self, atividades):
        """
        Seleciona apenas atividades ligadas a saúde/laboratório para evitar ruído.
        """
        palavras_chave = [
            "MEDIC", "HOSP", "LABOR", "REAGEN", "ANALIS", "ANÁLISE", "SAUDE", "SAÚDE",
            "BIOMED", "BIOQUIM", "HEMATO", "DIAGN", "EQUIPAMENTO MEDICO", "EQUIPAMENTOS MEDICOS",
            "MATERIAL HOSPITALAR", "INSUMOS HOSPITALARES", "ODONTO"
        ]
        relevantes = []
        for a in atividades:
            nome = a["nome"]
            if any(pk in nome for pk in palavras_chave):
                relevantes.append(a)
        return relevantes

    def buscar_oportunidades(self, termos_positivos=None, termos_negativos=None, estados=None):
        resultados = []
        try:
            atividades, estados_map = self._fetch_filters()
            atividades = self._atividades_relevantes(atividades)

            if not atividades:
                print("[BNC] Nenhuma atividade relevante encontrada.")
                return resultados

            # Mapeia UF -> id do BNC (se não existir, ignora)
            estados_upper = [e.upper() for e in estados] if estados else list(estados_map.keys())
            estados_ids = {uf: estados_map.get(uf) for uf in estados_upper if estados_map.get(uf)}
            if estados_upper and not estados_ids:
                print("[BNC] Nenhum estado da lista está disponível no BNC.")
                return resultados

            termos_pos_upper = [t.upper() for t in termos_positivos] if termos_positivos else []
            termos_neg_upper = [t.upper() for t in termos_negativos] if termos_negativos else []

            for atividade in atividades:
                for uf, uf_id in estados_ids.items():
                    try:
                        r = self.session.post(
                            self.API_URL,
                            params={"idActivity": atividade["id"], "idState": uf_id, "token": ""},
                            timeout=30
                        )
                        if r.status_code != 200:
                            continue

                        data_json = r.json()
                        html = data_json.get("html", "")
                        soup = BeautifulSoup(html, 'html.parser')
                        for tr in soup.find_all('tr'):
                            cols = tr.find_all('td')
                            if len(cols) < 7:
                                continue
                            orgao = cols[1].get_text(strip=True)
                            proc_num = cols[2].get_text(strip=True)
                            modalidade = cols[3].get_text(strip=True)
                            objeto = cols[4].get_text(strip=True)
                            disputa_str = cols[6].get_text(strip=True)

                            obj_upper = objeto.upper()
                            if termos_neg_upper and any(t in obj_upper for t in termos_neg_upper):
                                continue
                            if termos_pos_upper and not any(t in obj_upper for t in termos_pos_upper):
                                continue

                            # Data de disputa -> usa como encerramento
                            data_enc = None
                            dias_restantes = None
                            try:
                                dt = datetime.strptime(disputa_str, "%d/%m/%Y %H:%M")
                                data_enc = dt.isoformat()
                                dias_restantes = (dt.date() - date.today()).days
                            except Exception:
                                pass

                            link_tag = tr.find('a')
                            link = self.BASE_URL + link_tag.get('href') if link_tag and link_tag.get('href') else ""

                            termos_hit = [t for t in termos_pos_upper if t in obj_upper][:5]
                            resultados.append({
                                "pncp_id": f"BNC-{uf}-{proc_num}",
                                "orgao": orgao,
                                "uf": uf,
                                "modalidade": modalidade,
                                "data_sessao": None,
                                "data_publicacao": None,
                                "data_inicio_proposta": None,
                                "data_encerramento_proposta": data_enc,
                                "objeto": objeto,
                                "link": link,
                                "dias_restantes": dias_restantes,
                                "fonte": "BNC",
                                "motivo_aprovacao": f"Atividade {atividade['nome']} / Termos: {', '.join(termos_hit) if termos_hit else 'contexto saúde'}",
                                "termos_encontrados": termos_hit
                            })
                    except Exception as e:
                        print(f"[BNC] Erro na atividade {atividade['id']} UF {uf}: {e}")

            print(f"[BNC] Total retornado: {len(resultados)}")
            return resultados

        except Exception as e:
            print(f"[BNC] Erro geral: {e}")
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
