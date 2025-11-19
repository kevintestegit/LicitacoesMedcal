import requests
from datetime import datetime, timedelta, date
import time

class PNCPClient:
    BASE_URL = "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"
    
    # Termos NEGATIVOS padrão (podem ser sobrescritos ou extendidos)
    TERMOS_NEGATIVOS_PADRAO = [
        "PLANO DE SAUDE", "PLANO DE SAÚDE", "PLANOS DE SAÚDE", "PLANOS DE SAUDE",
        "ASSISTENCIA MEDICA", "ASSISTÊNCIA MÉDICA", 
        "COBERTURA MINIMA OBRIGATORIA", "COBERTURA MÍNIMA OBRIGATÓRIA", "ROL DE PROCEDIMENTOS",
        "ROL DE PROCEDIMENTOS E EVENTOS EM SAUDE", "BENEFICIARIOS", "BENEFICIÁRIOS", "BENEFICIARIO", "BENEFICIÁRIO", 
        "USUARIOS DO PLANO", "USUÁRIOS DO PLANO", "OPERADORA DE PLANO", "OPERADORA DE PLANOS", "PLANO COLETIVO EMPRESARIAL", "PLANO COLETIVO POR ADESAO",
        "PLANO COLETIVO POR ADESÃO", "ATENDIMENTO MÉDICO", "ATENDIMENTO MEDICO", "CONSULTAS MÉDICAS",
        "CONSULTAS MEDICAS", "ASSISTENCIA PSIQUIATRICA", "ASSISTÊNCIA PSIQUIÁTRICA", "ASSISTENCIA OBSTETRICA",
        "ASSISTÊNCIA OBSTÉTRICA", "SERVIÇOS DE ASSISTÊNCIA MÉDICA", "SERVICOS DE ASSISTENCIA MEDICA",   
        "AGENCIA DE VIAGENS", "AGÊNCIA DE VIAGENS", "AGENCIA DE VIAGEM", "AGÊNCIA DE VIAGEM", "EXTINTORES",
        "AGENCIAMENTO DE VIAGENS", "AGENCIAMENTO DE VIAGEM", "OPERADORA DE VIAGENS", "OPERADORA DE TURISMO",
        "AGENCIA DE TURISMO", "AGÊNCIA DE TURISMO", "PASSAGEM AEREA", "PASSAGEM AÉREA", "PASSAGENS AEREAS",
        "PASSAGENS AÉREAS", "PASSAGEM AEREA NACIONAL", "PASSAGEM AÉREA NACIONAL", "PASSAGENS AEREAS NACIONAIS",
        "PASSAGENS AÉREAS NACIONAIS", "PASSAGEM AEREA INTERNACIONAL", "PASSAGEM AÉREA INTERNACIONAL",
        "PASSAGENS AEREAS INTERNACIONAIS", "PASSAGENS AÉREAS INTERNACIONAIS", "RESERVA DE PASSAGEM",
        "RESERVA DE PASSAGENS", "EMISSAO DE PASSAGEM", "EMISSÃO DE PASSAGEM", "EMISSAO DE PASSAGENS",
        "EMISSÃO DE PASSAGENS", "REMARCACAO DE PASSAGEM", "REMARCAÇÃO DE PASSAGEM", "REMARCACAO DE PASSAGENS",
        "REMARCAÇÃO DE PASSAGENS", "Prestação de Serviço de Limpeza", "CONDICIONADORES DE AR", "AQUISIÇÃO DE PNEUS",
        "câmaras de ar", "baterias", "Contratação de instituição financeira", "banco", "CONTROLE EM ZOONOSES",
        "AQUISIÇÃO DE MEDICAMENTOS (ONCOLÓGICOS)", "MEDICAMENTOS", "PRESTAÇÃO DE SERVIÇO DE LIMPEZA",
        "PRESTAÇÃO DE SERVIÇO DE LIMPEZA E CONSERVAÇÃO", "SISTEMA DE ESTAÇÃO DE TRATAMENTO DE ÁGUA E ESGOTO",
        "SERVIÇOS CONTÍNUOS DE LIMPEZA E DESINFECÇÃO", "LIMPEZA E DESINFECÇÃO", "DESINFECÇÃO", "DESINFECCAO", "LOCAÇÃO DE VEÍCULOS",
        "PRESTAÇÃO DE SERVIÇOS DE LIMPEZA", "RECEPÇÃO", "LIMPEZA", "AQUISIÇÃO DE MATERIAIS E UTENSÍLIOS DOMÉSTICOS",
        "AQUISIÇÃO DE MATERIAL DE FISIOTERAPIA", "SERVIÇOS DE CONFECÇÃO", "PLACAS DE SINALIZAÇÃO VISUAL", 
        "SERVIÇO MANUTENÇÃO DE VEÍCULOS", "SERVIÇO MANUTENÇÃO DE VEÍCULOS E MAQUINAS PESADAS","IMPLEMENTOS AGRÍCOLAS", 
        "MOTOCICLETAS", "CBUQ", "Concreto Betuminoso Usinado a Quente","EMPRESA DE ENGENHARIA", "PINTURA",
        "PINTURA E POLIMENTO", "SERVIÇOS COMUNS DE ENGENHARIA", "MANUTENÇÃO PREDIAL",
        "MATERIAIS DE SEGURANÇA", "EPIS", "VEÍCULOS LEVES E PESADOS", "HORAS DE TRATOR", "VEÍCULOS LEVES", "VEÍCULOS PESADOS",
        "MATERIAIS DIDÁTICOS", "MATERIAL DIDÁTICO", "COMBUSTÍVEL", "PEÇAS DE VEÍCULOS", "SERVIÇOS MECÂNICOS"
        "OUTSOURCING", "TERCEIRIZADO", "TERCEIRIZAÇÃO", "TERCEIRIZAÇÃO DE SERVIÇOS", "MATERIAL ESPORTIVO",
        "REQUALIFICAÇÃO DOS SISTEMAS DE PROTEÇÃO E COMBATE A INCÊNDIO E PANICO", "LOCACAO DE ESTRUTURAS", "LOCACAO DE ESTRUTURA",
        "LOCAÇÃO DE ESTRUTURA", "MATERIAIS DE CONSTRUÇÕES", "MATERIAIS DE CONSTRUCAO", "MATERIAL DE CONSTRUCAO",
        "PEÇAS AUTOMOTIVAS", "PECAS AUTOMOTIVAS", "LOCAÇÃO DE VEÍCULOS", "LOCAÇÃO DE VEÍCULO", "LOCACAO DE VEICULO",
        "MATERIAL DE COPA E COZINHA", "MATERIAIS DE COZINHA", "MATERIAIS DE COPA", "LOCAÇÃO DE ESCAVADEIRA",
        "ROUPAS DE SERVIÇOS DE SAÚDE", "LAVANDERIA HOSPITALAR", "PPCIP", "INCENDIO", "INCÊNDIO", "ÔNIBUS",
        "ONIBUS", "MICRO-ÔNIBUS", "MICRO-ONIBUS", "CAMINHÕES", "CAMINHOES", "CAMINHAO", "CARROCERIA",
        "CAÇAMBA", "CACAMBA", "BASCULANTE", "ESCAVADEIRA", "HIDRAULICA"
    ]           

    # Termos POSITIVOS padrão (do app.py original)
    TERMOS_POSITIVOS_PADRAO = [
        "Aquisição de aparelhos", "equipamentos e utensílios médicos", "laboratoriais e hospitalares", 
        "MATERIAL HOSPITALAR", "MATERIAIS HOSPITALARES", "MATERIAL MEDICO", "MATERIAIS MEDICOS",
        "MATERIAIS MÉDICOS", "MATERIAL LABORATORIAL", "MATERIAIS LABORATORIAIS",
        "MATERIAL DE LABORATORIO", "MATERIAIS DE LABORATORIO", "INSUMO", "INSUMOS", "REAGENTE",
        "REAGENTES", "PRODUTOS MEDICOS", "PRODUTOS MÉDICOS", "PRODUTOS HOSPITALARES",
        "PRODUTOS LABORATORIAIS", "EQUIPAMENTO HOSPITALAR", "EQUIPAMENTOS HOSPITALARES",
        "EQUIPAMENTO MEDICO", "EQUIPAMENTOS MEDICOS", "EQUIPAMENTO MÉDICO", "EQUIPAMENTOS MÉDICOS",
        "EQUIPAMENTO LABORATORIAL", "EQUIPAMENTOS LABORATORIAIS", "EQUIPAMENTOS DE LABORATORIO",
        "EQUIPAMENTO BIOMEDICO", "EQUIPAMENTOS BIOMEDICOS", "ANALISE CLINICA", "ANALISES CLINICAS",
        "Anatomia Patológica", "Citopatologia","BIOQUIMICA", "HEMATOLOGIA", "IMUNOLOGIA", "TT/TTPA",
        "COAGULAÇÃO", "APARELHO DE COAGULAÇÃO", "IMUNO-HISTOQUÍMICA"
        "APARELHOS HOSPITALARES", "APARELHOS MEDICOS", "APARELHOS MÉDICOS", "APARELHOS LABORATORIAIS",
        "INSTRUMENTOS CIRURGICOS", "INSTRUMENTOS CIRÚRGICOS", "INSTRUMENTOS HOSPITALARES",
        "INSTRUMENTOS LABORATORIAIS", "GASES MEDICINAIS", "GAS MEDICINAL", "GÁS MEDICINAL",
        "OXIGENIO MEDICINAL", "OXIGÊNIO MEDICINAL", "AR MEDICINAL", "AR COMPRIMIDO MEDICINAL",
        "LABORATORIAL", "LABORATORIO", "LABORATÓRIO", "HOSPITALAR", "HOSPITALARES", "ODONTOLOGICO",
        "ODONTOLÓGICO", "ODONTOLOGICOS", "ODONTOLÓGICOS", "ODONTO-MEDICO-HOSPITALAR",
        "ODONTOMEDICOHOSPITALAR", "UTENSILIO", "UTENSÍLIO", "UTENSILIOS", "UTENSÍLIOS",
        "APARELHO", "APARELHOS", "INSTRUMENTAL", "INSTRUMENTAIS", "MATERIAIS", "MATERIAL",
        "MANUTENCAO", "MANUTENÇÃO", "CALIBRACAO", "CALIBRAÇÃO", "AFERICAO", "AFERIÇÃO",
        "ALUGUEL", "LOCACAO", "LOCAÇÃO", "COMODATO", "COMODATOS",
        "FARMACEUTICO", "FARMACÊUTICO", "FARMACIA", "FARMÁCIA",
        "ORTOPEDIA", "ORTOPEDICO", "ORTOPÉDICO", "PROTESE", "PRÓTESE", "HIGIENE",
        "SANEANTE", "SANEANTES", "DOMISSANITARIO", "DOMISSANITÁRIO", "LIMPEZA",
        "PECA", "PEÇA", "PECAS", "PEÇAS", "ACESSORIO", "ACESSÓRIO",
        "SERVIÇOS CONTÍNUOS DE CALIBRAÇÃO","MANUTENÇÃO PREVENTIVA E CORRETIVA",
        "MANUTENÇÃO E REPARO NOS COMPONENTES DE EQUIPAMENTO",  "ASSISTENCIA HOSPITALAR", "ASSISTÊNCIA HOSPITALAR",
        "ASSISTENCIA AMBULATORIAL", "ASSISTÊNCIA AMBULATORIAL", "MATERIAL AMBULATORIAL", "MATERIAIS AMBULATORIAIS",
        "PEÇAS CIRÚRGICAS"  
    ]

    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"
        }

    def calcular_dias(self, data_iso):
        """Retorna número de dias entre HOJE e a data (só a parte AAAA-MM-DD)."""
        if not data_iso:
            return -999
        try:
            dia = data_iso[:10]
            dt = datetime.strptime(dia, "%Y-%m-%d").date()
            hoje = date.today()
            return (dt - hoje).days
        except Exception:
            return -999

    def buscar_oportunidades(self, dias_busca=30, estados=['RN', 'PB', 'PE', 'AL'], termos_positivos=[], termos_negativos=None):
        """
        Busca licitações (Pregão/Dispensa) publicadas nos últimos X dias.
        Aplica filtros de termos positivos (OR) e negativos (NOT).
        """
        if termos_negativos is None:
            termos_negativos = self.TERMOS_NEGATIVOS_PADRAO

        hoje = datetime.now()
        hoje = datetime.now()
        data_inicial = (hoje - timedelta(days=dias_busca)).strftime('%Y%m%d')
        # Data final = Amanhã, para garantir que pegue tudo de hoje independente do fuso/hora
        data_final = (hoje + timedelta(days=1)).strftime('%Y%m%d')
        
        resultados = []
        
        # 6=Pregão, 8=Dispensa
        for modalidade in [6, 8]:
            for uf in estados:
                # Busca ampliada: páginas 1 a 5 de cada estado/modalidade
                for pagina in range(1, 6):
                    params = {
                        "dataInicial": data_inicial,
                        "dataFinal": data_final,
                        "codigoModalidadeContratacao": modalidade,
                        "uf": uf,
                        "pagina": str(pagina),
                        "tamanhoPagina": "50"
                    }
                    
                    try:
                        resp = requests.get(self.BASE_URL, params=params, headers=self.headers, timeout=10)
                        if resp.status_code != 200: continue
                        
                        data = resp.json().get('data', [])
                        if not data: break
                        
                        for item in data:
                            # 1) Campo do objeto na API de CONSULTA é "objetoCompra" ou "objeto"
                            obj_raw = item.get('objetoCompra') or item.get('objeto') or ""
                            obj = obj_raw.upper()
                            
                            if not obj:
                                continue

                            # 2) Filtro de Termos Positivos (se houver)
                            if termos_positivos and not any(t in obj for t in termos_positivos):
                                continue

                            # 3) Filtro de Termos Negativos
                            # Garante que os termos negativos também estejam em MAIÚSCULO para comparar
                            termos_negativos_upper = [t.upper() for t in termos_negativos]
                            
                            # DEBUG TEMPORÁRIO
                            if "LIMPEZA E DESINFECÇÃO" in obj:
                                print(f"--- DEBUG FILTER ---")
                                print(f"OBJ: {obj}")
                                matches = [t for t in termos_negativos_upper if t in obj]
                                print(f"MATCHES FOUND: {matches}")
                                if matches:
                                    print("ACTION: SKIPPING (Correct)")
                                    continue
                                else:
                                    print("ACTION: INCLUDING (Why??)")
                            
                            if any(t in obj for t in termos_negativos_upper):
                                continue
                            
                            # 4) Filtro de Data (Encerramento Proposta)
                            # Só aceitamos se tiver data válida e futura (ou hoje)
                            data_encerramento = item.get("dataEncerramentoProposta")
                            dias_restantes = self.calcular_dias(data_encerramento)
                            
                            # Se não tem data de encerramento ou já passou muito (-1 ainda aceita como 'hoje' dependendo do fuso)
                            # Vamos ser permissivos aqui e deixar o filtro fino para o UI, mas descartar coisas muito antigas
                            if dias_restantes < -1: 
                                continue

                            # Adiciona dias restantes ao objeto parseado
                            parsed = self._parse_licitacao(item)
                            parsed['dias_restantes'] = dias_restantes
                            resultados.append(parsed)
                            
                    except Exception as e:
                        print(f"Erro na busca: {e}")
                    
                    time.sleep(0.2)
                    
        return resultados

    def _parse_licitacao(self, item):
        orgao = item.get('orgaoEntidade', {})
        cnpj = orgao.get('cnpj') or orgao.get('cnpjComprador')
        ano = item.get('anoCompra')
        seq = item.get('sequencialCompra')
        
        link = f"https://pncp.gov.br/app/editais/{cnpj}/{ano}/{seq}" if (cnpj and ano and seq) else ""
        
        return {
            "pncp_id": f"{cnpj}-{ano}-{seq}",
            "orgao": orgao.get('razaoSocial', 'Desconhecido'),
            "uf": orgao.get('ufSigla', 'BR'),
            "modalidade": "Pregão" if item.get('modalidadeId') == 6 else "Dispensa",
            "data_sessao": item.get('dataAberturaOuSessao'),
            "data_publicacao": item.get('dataPublicacaoPncp'),
            "data_inicio_proposta": item.get('dataInicioRecebimentoProposta'),
            "data_encerramento_proposta": item.get('dataEncerramentoProposta'),
            "objeto": item.get('objetoCompra') or item.get('objeto'),
            "link": link,
            # Dados extras para buscar itens depois
            "cnpj": cnpj,
            "ano": ano,
            "seq": seq
        }

    def buscar_arquivos(self, licitacao_dict):
        """
        Busca os arquivos (editais, anexos) de uma licitação.
        Endpoint: /api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{sequencial}/arquivos
        """
        cnpj = licitacao_dict.get('cnpj')
        ano = licitacao_dict.get('ano')
        seq = licitacao_dict.get('seq')
        
        if not (cnpj and ano and seq):
            return []
            
        url = f"https://pncp.gov.br/api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{seq}/arquivos"
        
        arquivos = []
        try:
            resp = requests.get(url, headers=self.headers, timeout=10)
            if resp.status_code == 200:
                lista = resp.json()
                for arq in lista:
                    arquivos.append({
                        "titulo": arq.get('titulo'),
                        "nome": arq.get('nomeArquivo'),
                        "url": arq.get('url')
                    })
        except Exception as e:
            print(f"Erro ao buscar arquivos: {e}")
            
        return arquivos

    def buscar_itens(self, licitacao_dict):
        """
        Busca os itens de uma licitação específica.
        Endpoint: /api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{sequencial}/itens
        """
        cnpj = licitacao_dict.get('cnpj')
        ano = licitacao_dict.get('ano')
        seq = licitacao_dict.get('seq')
        
        if not (cnpj and ano and seq):
            return []
            
        url = f"https://pncp.gov.br/api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{seq}/itens"
        
        itens_encontrados = []
        try:
            resp = requests.get(url, headers=self.headers, timeout=10)
            if resp.status_code == 200:
                lista = resp.json()
                for i in lista:
                    itens_encontrados.append({
                        "numero": i.get('numeroItem'),
                        "descricao": i.get('descricao'),
                        "quantidade": i.get('quantidade'),
                        "unidade": i.get('unidadeMedida'),
                        "valor_estimado": i.get('valorTotalEstimado'),
                        "valor_unitario": i.get('valorUnitarioEstimado')
                    })
        except Exception as e:
            print(f"Erro ao buscar itens: {e}")
            
        return itens_encontrados

    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"
        }

    def calcular_dias(self, data_iso):
        """Retorna número de dias entre HOJE e a data (só a parte AAAA-MM-DD)."""
        if not data_iso:
            return -999
        try:
            dia = data_iso[:10]
            dt = datetime.strptime(dia, "%Y-%m-%d").date()
            hoje = date.today()
            return (dt - hoje).days
        except Exception:
            return -999

    def buscar_oportunidades(self, dias_busca=30, estados=['RN', 'PB', 'PE', 'AL'], termos_positivos=[], termos_negativos=None):
        """
        Busca licitações (Pregão/Dispensa) publicadas nos últimos X dias.
        Aplica filtros de termos positivos (OR) e negativos (NOT).
        """
        if termos_negativos is None:
            termos_negativos = self.TERMOS_NEGATIVOS_PADRAO

        hoje = datetime.now()
        hoje = datetime.now()
        data_inicial = (hoje - timedelta(days=dias_busca)).strftime('%Y%m%d')
        # Data final = Amanhã, para garantir que pegue tudo de hoje independente do fuso/hora
        data_final = (hoje + timedelta(days=1)).strftime('%Y%m%d')
        
        resultados = []
        
        # 6=Pregão, 8=Dispensa
        for modalidade in [6, 8]:
            for uf in estados:
                # Busca simplificada: página 1 e 2 de cada estado/modalidade
                for pagina in range(1, 3):
                    params = {
                        "dataInicial": data_inicial,
                        "dataFinal": data_final,
                        "codigoModalidadeContratacao": modalidade,
                        "uf": uf,
                        "pagina": str(pagina),
                        "tamanhoPagina": "50"
                    }
                    
                    try:
                        resp = requests.get(self.BASE_URL, params=params, headers=self.headers, timeout=10)
                        if resp.status_code != 200: continue
                        
                        data = resp.json().get('data', [])
                        if not data: break
                        
                        for item in data:
                            # 1) Campo do objeto na API de CONSULTA é "objetoCompra" ou "objeto"
                            obj_raw = item.get('objetoCompra') or item.get('objeto') or ""
                            obj = obj_raw.upper()
                            
                            if not obj:
                                continue

                            # 2) Filtro de Termos Positivos (se houver)
                            if termos_positivos and not any(t in obj for t in termos_positivos):
                                continue

                            # 3) Filtro de Termos Negativos
                            if any(t in obj for t in termos_negativos):
                                continue
                            
                            # 4) Filtro de Data (Encerramento Proposta)
                            # Só aceitamos se tiver data válida e futura (ou hoje)
                            data_encerramento = item.get("dataEncerramentoProposta")
                            dias_restantes = self.calcular_dias(data_encerramento)
                            
                            # Se não tem data de encerramento ou já passou muito (-1 ainda aceita como 'hoje' dependendo do fuso)
                            # Vamos ser permissivos aqui e deixar o filtro fino para o UI, mas descartar coisas muito antigas
                            if dias_restantes < -1: 
                                continue

                            # Adiciona dias restantes ao objeto parseado
                            parsed = self._parse_licitacao(item)
                            parsed['dias_restantes'] = dias_restantes
                            resultados.append(parsed)
                            
                    except Exception as e:
                        print(f"Erro na busca: {e}")
                    
                    time.sleep(0.2)
                    
        return resultados

    def _parse_licitacao(self, item):
        orgao = item.get('orgaoEntidade', {})
        cnpj = orgao.get('cnpj') or orgao.get('cnpjComprador')
        ano = item.get('anoCompra')
        seq = item.get('sequencialCompra')
        
        link = f"https://pncp.gov.br/app/editais/{cnpj}/{ano}/{seq}" if (cnpj and ano and seq) else ""
        
        return {
            "pncp_id": f"{cnpj}-{ano}-{seq}",
            "orgao": orgao.get('razaoSocial', 'Desconhecido'),
            "uf": orgao.get('ufSigla', 'BR'),
            "modalidade": "Pregão" if item.get('modalidadeId') == 6 else "Dispensa",
            "data_sessao": item.get('dataAberturaOuSessao'),
            "data_publicacao": item.get('dataPublicacaoPncp'),
            "data_inicio_proposta": item.get('dataInicioRecebimentoProposta'),
            "data_encerramento_proposta": item.get('dataEncerramentoProposta'),
            "objeto": item.get('objetoCompra') or item.get('objeto'),
            "link": link,
            # Dados extras para buscar itens depois
            "cnpj": cnpj,
            "ano": ano,
            "seq": seq
        }

    def buscar_arquivos(self, licitacao_dict):
        """
        Busca os arquivos (editais, anexos) de uma licitação.
        Endpoint: /api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{sequencial}/arquivos
        """
        cnpj = licitacao_dict.get('cnpj')
        ano = licitacao_dict.get('ano')
        seq = licitacao_dict.get('seq')
        
        if not (cnpj and ano and seq):
            return []
            
        url = f"https://pncp.gov.br/api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{seq}/arquivos"
        
        arquivos = []
        try:
            resp = requests.get(url, headers=self.headers, timeout=10)
            if resp.status_code == 200:
                lista = resp.json()
                for arq in lista:
                    arquivos.append({
                        "titulo": arq.get('titulo'),
                        "nome": arq.get('nomeArquivo'),
                        "url": arq.get('url')
                    })
        except Exception as e:
            print(f"Erro ao buscar arquivos: {e}")
            
        return arquivos

    def buscar_itens(self, licitacao_dict):
        """
        Busca os itens de uma licitação específica.
        Endpoint: /api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{sequencial}/itens
        """
        cnpj = licitacao_dict.get('cnpj')
        ano = licitacao_dict.get('ano')
        seq = licitacao_dict.get('seq')
        
        if not (cnpj and ano and seq):
            return []
            
        url = f"https://pncp.gov.br/api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{seq}/itens"
        
        itens_encontrados = []
        try:
            resp = requests.get(url, headers=self.headers, timeout=10)
            if resp.status_code == 200:
                lista = resp.json()
                for i in lista:
                    itens_encontrados.append({
                        "numero": i.get('numeroItem'),
                        "descricao": i.get('descricao'),
                        "quantidade": i.get('quantidade'),
                        "unidade": i.get('unidadeMedida'),
                        "valor_estimado": i.get('valorTotalEstimado'),
                        "valor_unitario": i.get('valorUnitarioEstimado')
                    })
        except Exception as e:
            print(f"Erro ao buscar itens: {e}")
            
        return itens_encontrados
