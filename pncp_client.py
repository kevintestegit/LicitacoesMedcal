import requests
from datetime import datetime, timedelta, date
import time
import re

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
        "SERVIÇO MANUTENÇÃO DE VEÍCULOS", "SERVIÇO MANUTENÇÃO DE VEÍCULOS E MAQUINAS PESADAS","IMPLEMENTOS AGRÍCOLAS", "máquinas e equipamentos agrícolas",
        "MAQUINAS E EQUIPAMENTOS AGRICOLAS", "MAQUINÁS E EQUIPAMENTOS AGRÍCOLAS", "MAQUINAS E EQUIPAMENTOS AGRÍCOLAS",
        "MOTOCICLETAS", "CBUQ", "Concreto Betuminoso Usinado a Quente","EMPRESA DE ENGENHARIA", "PINTURA",
        "PINTURA E POLIMENTO", "SERVIÇOS COMUNS DE ENGENHARIA", "MANUTENÇÃO PREDIAL", "COMBUSTIVEL", "COMBUSTIVEL E LUBRIFICANTE",
        "MATERIAIS DE SEGURANÇA", "EPIS", "VEÍCULOS LEVES E PESADOS", "HORAS DE TRATOR", "VEÍCULOS LEVES", "VEÍCULOS PESADOS",
        "MATERIAIS DIDÁTICOS", "MATERIAL DIDÁTICO", "COMBUSTÍVEL", "PEÇAS DE VEÍCULOS", "SERVIÇOS MECÂNICOS",
        "OUTSOURCING", "TERCEIRIZADO", "TERCEIRIZAÇÃO", "TERCEIRIZAÇÃO DE SERVIÇOS", "MATERIAL ESPORTIVO",
        "REQUALIFICAÇÃO DOS SISTEMAS DE PROTEÇÃO E COMBATE A INCÊNDIO E PANICO", "LOCACAO DE ESTRUTURAS", "LOCACAO DE ESTRUTURA",
        "LOCAÇÃO DE ESTRUTURA", "MATERIAIS DE CONSTRUÇÕES", "MATERIAIS DE CONSTRUCAO", "MATERIAL DE CONSTRUCAO",
        "PEÇAS AUTOMOTIVAS", "PECAS AUTOMOTIVAS", "LOCAÇÃO DE VEÍCULOS", "LOCAÇÃO DE VEÍCULO", "LOCACAO DE VEICULO",
        "MATERIAL DE COPA E COZINHA", "MATERIAIS DE COZINHA", "MATERIAIS DE COPA", "LOCAÇÃO DE ESCAVADEIRA",
        "ROUPAS DE SERVIÇOS DE SAÚDE", "LAVANDERIA HOSPITALAR", "PPCIP", "INCENDIO", "INCÊNDIO", "ÔNIBUS",
        "ONIBUS", "MICRO-ÔNIBUS", "MICRO-ONIBUS", "CAMINHÕES", "CAMINHOES", "CAMINHAO", "CARROCERIA", "OLEO DIESEL",
        "CAÇAMBA", "CACAMBA", "BASCULANTE", "ESCAVADEIRA", "HIDRAULICA", "BRINQUEDOS", "PARQUE INFANTIL",
        "REMANUFATURA DE TONER", "TONER", "FARDAMENTO", "UNIFORME", "UNIFORMES", "RAIO X", "RAYOS X", "RAIOS X",
        "RAIO-X", "RAYO-X", "APARELHO DE RAIO X", "APARELHO DE RAYOS X", "RAIOS-X", "VENTILADORES", "VENTILO PULMONAR",
        "VENTILADOR PULMONAR", "EPI'S", "INVENTÁRIOS", "INVENTARIOS", "INVENTARIO", "MATERIAL DE EXPEDIENTE", "MATERIAIS DE EXPEDIENTE",
        "EXPEDIENTE", "MATERIAL DE ESCRITÓRIO", "MATERIAIS DE ESCRITÓRIO", "MATERIAL DE INFORMÁTICA", "MATERIAIS DE INFORMÁTICA", "DESSANILIZADOR",
        "DESANILIZADOR", "ÁGUA DESANILIZADA", "AGUA DESANILIZADA", "ÁGUA DESSANILIZADA", "AGUA DESSANILIZADA", "DESSANILIZADORES", "AQUISIÇÃO DE OPME",
        "ILUMINAÇÃO PUBLICA", "ILUMINACAO PUBLICA", "RASTREAMENTO DE VEÍCULOS", "RASTREAMENTO DE VEICULOS", "MATERIAIS ODONTOLÓGICOS",
        "MATERIAIS ODONTOLOGICOS", "MATERIAL ODONTOLOGICO", "MATERIAL ODONTOLÓGICO", "INSTITUIÇÃO FINANCEIRA", "INSTITUICAO FINANCEIRA",
        "SERVIÇOS DE ENGENHARIA", "SERVICOS DE ENGENHARIA", "SERVIÇO DE ENGENHARIA", "SERVICO DE ENGENHARIA", "ALMOXARIFADO",
        "SERVIÇOS DE ENGENHARIA CIVIL", "SERVICOS DE ENGENHARIA CIVIL", "ALMOXARIFADO VIRTUAL", "DIVULGAÇÃO DE PROPAGANDA INSTITUCIONAL",
        "DIVULGAÇÃO DE PROPAGANDA", "DIVULGACAO DE PROPAGANDA INSTITUCIONAL", "DIVULGACAO DE PROPAGANDA", "dessalinizadores", "sistemas de dessalinizadores",
        "SISTEMA DE DESSANILIZADORES", "SISTEMA DE DESSALINIZADORES", "SISTEMAS DE DESSANILIZADORES", "SISTEMAS DE DESSALINIZADORES", "SUPLEMENTOS ALIMENTARES",
        "SUPLEMENTO ALIMENTAR", " Recursos Google Workspace", " Recursos Microsoft 365", " Recursos Microsoft365", "SERVIÇOS DE VIGILÂNCIA",
        "SERVICOS DE VIGILANCIA", "RECURSOS GOOGLE WORKSPACE FOR EDUCATION", "Softwares Educacionais", "SOFTWARES EDUCACIONAIS", "Serviços Vigilância Eletrônica", "SERVIÇOS DE VIGILANCIA ELETRONICA",
        "SERVICOS DE VIGILANCIA ELETRONICA",
        "SERVIÇO DE VIGILÂNCIA", "SERVICO DE VIGILANCIA", "Materiais de OPME", "MATERIAIS DE OPME", "MATERIAL DE OPME", "Serviços Administrativos",
        "SERVIÇOS ADMINISTRATIVOS", "SERVICOS ADMINISTRATIVOS", "SERVIÇO ADMINISTRATIVO", "SERVICO ADMINISTRATIVO", "AQUISIÇÃO DE LEITES ESPECIAIS",
        "LEITES ESPECIAIS", "LEITE ESPECIAL", "LEITE ESPECIAIS", "ADMINISTRAÇÃO DA FOLHA", "ADMINISTRACAO DA FOLHA",
        "FOLHA DE PAGAMENTO", "FOLHA DE PAGAMENTOS", "SERVIÇOS DE FOLHA DE PAGAMENTO", "SERVICOS DE FOLHA DE PAGAMENTO", "FROTA DE VEÍCULOS",
        "FROTA DE VEICULOS", "SISTEMA INTEGRADO DE PROTEÇÃO INTELIGENTE", "SISTEMA INTEGRADO DE PROTECAO INTELIGENTE", "higiene pessoal", "HIGIENE PESSOAL",
        "MATERIAL DE HIGIENE PESSOAL", "MATERIAIS DE HIGIENE PESSOAL", "MATERIAL DE HIGIENE", "MATERIAIS DE HIGIENE", "mobiliários", "MOBILIÁRIOS", "MOBILIARIOS",
        "MATERIAL DE MOBILIÁRIO", "MATERIAL DE MOBILIARIO", "MATERIAIS DE MOBILIÁRIO", "MATERIAIS DE MOBILIARIO", "coletes balísticos", "COLETES BALÍSTICOS", "COLETES BALISTICOS",
        "material elétrico", "MATERIAL ELÉTRICO", "MATERIAL ELETRICO", "MATERIAIS ELÉTRICOS", "MATERIAIS ELETRICOS", "materiais pré-moldados",
        "MATERIAIS PRÉ-MOLDADOS", "MATERIAIS PRE-MOLDADOS","MATERIAIS DESCARTÁVEIS", "MATERIAL DESCARTÁVEL", "MATERIAL DESCARTAVEL", "corrida de rua",
        "CORRIDA DE RUA", "aquisição de combustíveis", "AQUISIÇÃO DE COMBUSTÍVEIS", "AQUISICAO DE COMBUSTIVEIS", "eventos de promoção",
        "EVENTOS DE PROMOÇÃO", "EVENTOS DE PROMOCAO", "locação de espaço físico", "LOCAÇÃO DE ESPAÇO FÍSICO", "LOCAÇÃO DE ESPACO FISICO", "LOCACAO DE ESPACO FISICO",
        "sacola ecológica", "SACOLA ECOLÓGICA", "SACOLA ECOLOGICA", "AQUISIÇÃO DE MÁQUINA DE CORTAR GRAMA", "MÁQUINA DE CORTAR GRAMA", "MAQUINA DE CORTAR GRAMA",
        "aquisição de câmeras", "AQUISIÇÃO DE CAMERAS", "AQUISIÇÃO DE CÂMERAS", "equipamentos de segurança", "EQUIPAMENTOS DE SEGURANÇA", "serviços de seguro predial",
        "SERVIÇOS DE SEGURO PREDIAL", "SERVICOS DE SEGURO PREDIAL", "ANIMAIS", "VEÍCULOS", "VEICULOS", "KIT ENXOVAL INFANTIL", "Veículo Automotor", "VEÍCULO AUTOMOTOR", "VEICULO AUTOMOTOR",
        "AGENCIAMENTO DE HOSPEDAGEM", "AGÊNCIA DE HOSPEDAGEM", "AGENCIA DE HOSPEDAGEM", "HOSPEDAGEM", "HOTELARIA", "SERVIÇOS DE HOTELARIA", "SERVICOS DE HOTELARIA", 
        "AQUISIÇÃO DE MATERIAL GRÁFICO", "AQUISICAO DE MATERIAL GRAFICO", "MATERIAL GRÁFICO", "MATERIAL GRAFICO", "AQUSIÇÃO DE MÓVEIS E MATERIAIS PERMANENTES",
        "APARELHOS CELULARES", "bomba Injetora de Contraste", "BOMBA INJETORA DE CONTRASTE", "BOMBA INJETORA DE CONTRASTES", "bombas de água e materiais hidráulicos",
        "BOMBAS DE ÁGUA E MATERIAIS HIDRÁULICOS", "BOMBAS DE AGUA E MATERIAIS HIDRAULICOS", "serviços de administração", "SERVIÇOS DE ADMINISTRAÇÃO", "SERVICOS DE ADMINISTRACAO",
        "bens imóveis", "BENS IMÓVEIS", "BENS IMOVEIS", "MATERIAIS DE PROTEÇÃO INDIVIDUAL", "MATERIAL DE PROTEÇÃO INDIVIDUAL", "Aquisição de utensílios de cozinha", "UTENSÍLIOS DE COZINHA",
        "UTENSILIOS DE COZINHA", "AQUISIÇÃO DE UTENSÍLIOS DE COZINHA", "BANHEIROS PÚBLICOS INTELIGENTES", "AUTOLIMPANTES E SUSTENTÁVEIS", "locação de decorações natalinas", "LOCAÇÃO DE DECORAÇÕES NATALINAS", "LOCAÇÃO DE DECORACOES NATALINAS",
        "LOCACAO DE DECORACOES NATALINAS", "SERVIÇOS DE DECORAÇÃO NATALINA", "SERVICOS DE DECORACAO NATALINA", "sistema de climatização", "SISTEMA DE CLIMATIZAÇÃO", "SISTEMA DE CLIMATIZACAO",
        "Subestação Abrigada", "SUBESTAÇÃO ABRIGADA", "torre de controle de aeródromo", "TORRE DE CONTROLE DE AERÓDROMO", "Aquisição de aparelhos de ares-condicionados",
        "AQUISIÇÃO DE APARELHOS DE ARES-CONDICIONADOS", "Aquisição de Aparelhos de Ar Condicionado", "AQUISIÇÃO DE APARELHOS DE AR CONDICIONADO",
        "MOTOBOMBAS CENTRIFUGA", "MOTOBOMBAS CENTRÍFUGA", "MOTOBOMBAS CENTRIFUGAS", "MOTOBOMBAS CENTRÍFUGAS", "matérias odontológicos", "MATERIAS ODONTOLOGICOS",
        "ensaios geotécnicos e de controle tecnológico de concreto", "ENSAIOS GEOTÉCNICOS E DE CONTROLE TECNOLÓGICO DE CONCRETO", " funcionamento dos contêineres adaptados",
        "FUNCIONAMENTO DOS CONTÊINERES ADAPTADOS", "FUNCIONAMENTO DOS CONTEINERES ADAPTADOS", "prótese dentária", " PRÓTESE DENTÁRIA", " PROTESE DENTARIA",
        "AQUISIÇÃO DE EQUIPAMENTOS DE ILUMINAÇÃO E SOM", "TEATRO", "atividades físicas, recreativas, esportivas e de reabilitação funcional", 
        "ATIVIDADES FÍSICAS, RECREATIVAS, ESPORTIVAS E DE REABILITAÇÃO FUNCIONAL", "ATIVIDADES FÍSICAS" , "ATIVIDADE FISICA", "manutenção veicular",
        "MANUTENÇÃO VEICULAR", "implementação da segurança orgânica", "IMPLEMENTAÇÃO DA SEGURANÇA ORGÂNICA", "IMPLEMENTACAO DA SEGURANCA ORGANICA",
        "manutenção e reparação de muro", "MANUTENÇÃO E REPARAÇÃO DE MURO", "MANUTENCAO E REPARACAO DE MURO", "prestação de serviços de recarga de oxigênio medicinal e ar medicinal comprimido",
        "PRESTAÇÃO DE SERVIÇOS DE RECARGA DE OXIGÊNIO MEDICINAL E AR MEDICINAL COMPRIMIDO", "PRESTACAO DE SERVICOS DE RECARGA DE OXIGENIO MEDICINAL",
        "manutenção preventiva e corretiva de elevadores", "MANUTENÇÃO PREVENTIVA E CORRETIVA DE ELEVADORES", "MANUTENCAO PREVENTIVA E CORRETIVA DE ELEVADORES",
        "Aquisição de Equipamentos de Fisioterapia", "AQUISIÇÃO DE EQUIPAMENTOS DE FISIOTERAPIA", "SERVIÇO PROFISSIONAL POR PESSOA JURÍDICA ESPECIALIZADA NO ACOMPANHAMENTO DE ÍNDICES EM SAÚDE",
        "SERVIÇO PROFISSIONAL POR PESSOA JURIDICA ESPECIALIZADA", "caminhão pipa", "CAMINHÃO PIPA", "CAMINHAO PIPA",
        "CONSTRUÇÃO", "CONSTRUCAO", "OBRA", "OBRAS", "REFORMA", "REFORMAS", "PAVIMENTAÇÃO", "PAVIMENTACAO", 
        "DRENAGEM", "EDIFICAÇÃO", "EDIFICACAO", "CRECHE", "ESCOLA", "QUADRA POLIESPORTIVA", "ENGENHARIA", 
        "CIVIL", "PREDIAL", "PREDIAIS", "ELÉTRICO", "ELETRICO", "ELÉTRICA", "ELETRICA", "HIDRÁULICO", 
        "HIDRAULICO", "HIDRÁULICA", "HIDRAULICA", "SANITÁRIO", "SANITARIO", "SANITÁRIA", "SANITARIA", 
        "URBANA", "URBANIZAÇÃO", "URBANIZACAO", "RODOVIA", "ESTRADA", "TERRAPLENAGEM", "Parque Aquático", "PARQUE AQUÁTICO", "PARQUE AQUATICO",
        "implantação de Sistema de Votação Eletrônica", "IMPLANTAÇÃO DE SISTEMA DE VOTAÇÃO ELETRÔNICA", "IMPLANTACAO DE SISTEMA DE VOTACAO ELETRONICA",
        "Lixo Hospitalar", "LIXO HOSPITALAR", "SERVIÇO DE REMOÇÃO DE LIXO HOSPITALAR", "SERVICO DE REMOCAO DE LIXO HOSPITALAR",
        "LEI COMPLEMENTAR", "LEI ORDINÁRIA", "DECRETO", "PORTARIA", "RESOLUÇÃO", "ATA DE REUNIÃO", "CONVOCAÇÃO", "POSSE", 
        "NOMEAÇÃO", "EXONERAÇÃO", "ERRATA", "RETIFICAÇÃO", "GABINETE DO PREFEITO", "SECRETARIA MUNICIPAL DE ADMINISTRAÇÃO", 
        "SECRETARIA MUNICIPAL DE GOVERNO", "CMDCA", "CMAS", "CONSELHO MUNICIPAL", "FUNDEB", "MAGISTÉRIO", "PISO SALARIAL", 
        "REAJUSTE", "ABONO", "GRATIFICAÇÃO", "AUMENTO SALARIAL", "PROCESSO SELETIVO", "CONCURSO PÚBLICO", "AUDIÊNCIA PÚBLICA",
        "LEI MUNICIPAL", "SANÇÃO", "VETO", "ADMISSÃO", "CONTRATAÇÃO DE PESSOAL", "plataforma de videomonitoramento de segurança pública",
        "PLATAFORMA DE VIDEOMONITORAMENTO DE SEGURANÇA PÚBLICA", "plataforma de videoconferência",
        "PLATAFORMA DE VIDEOCONFERÊNCIA", "PLATAFORMA DE VIDEOCONFERENCIA", "manutenção da infraestrutura", "MANUTENÇÃO DA INFRAESTRUTURA",
        "MANUTENCAO DA INFRAESTRUTURA", "SERVIÇOS DE INFRAESTRUTURA", "SERVICOS DE INFRAESTRUTURA", "materiais e utensílios de copa e cozinha",
        "manutenção de antena de Alta Frequência", "MANUTENÇÃO DE ANTENA DE ALTA FREQUÊNCIA", "MANUTENCAO DE ANTENA DE ALTA FREQUENCIA",
        "SERVIÇOS DE MANUTENÇÃO DE ANTENA DE ALTA FREQUÊNCIA", "SERVICOS DE MANUTENCAO DE ANTENA DE ALTA FREQUENCIA"
    ]
    # Termos POSITIVOS padrão (do app.py original)
    TERMOS_POSITIVOS_PADRAO = [
        "Aquisição de aparelhos", "laboratoriais e hospitalares", 
        "MATERIAL HOSPITALAR", "MATERIAIS HOSPITALARES",
        "MATERIAL LABORATORIAL", "MATERIAIS LABORATORIAIS", "LABORATORIO DE ANALISES CLINICAS",
        "MATERIAL DE LABORATORIO", "MATERIAIS DE LABORATORIO", "INSUMO", "INSUMOS", "REAGENTE", "AQUISIÇÃO DE MATERIAIS DE CONSUMO",
        "REAGENTES", "PRODUTOS MEDICOS", "PRODUTOS MÉDICOS", "PRODUTOS HOSPITALARES", "HORMONIOS", "REAGENTES LABORATORIAIS",
        "PRODUTOS LABORATORIAIS", "EQUIPAMENTO HOSPITALAR", "EQUIPAMENTOS HOSPITALARES", "REAGENTES DE LABORATORIO",
        "EQUIPAMENTO DE HEMATOLOGIA", "EQUIPAMENTO DE BIOQUIMICA", "EQUIPAMENTO DE COAGULACAO", 
        "EQUIPAMENTO DE IONOGRAMA", "AGUA DESTILADA", "CITOPALOGIA", "REAGENTES PARA LABORATORIO",
        "EQUIPAMENTO LABORATORIAL", "EQUIPAMENTOS LABORATORIAIS", "EQUIPAMENTOS DE LABORATORIO",
        "EQUIPAMENTO BIOMEDICO", "EQUIPAMENTOS BIOMEDICOS", "ANALISE CLINICA", "ANALISES CLINICAS",
        "EQUIPAMENTO", "EQUIPAMENTOS",
        "Anatomia Patológica", "Citopatologia","BIOQUIMICA", "HEMATOLOGIA", "IMUNOLOGIA", "TT/TTPA",
        "COAGULAÇÃO", "APARELHO DE COAGULAÇÃO", "IMUNO-HISTOQUÍMICA", "IMUNO", "HORMÔNIOS", "HORMONIO",
        "APARELHOS HOSPITALARES", "APARELHOS MEDICOS", "APARELHOS MÉDICOS", "APARELHOS LABORATORIAIS", 
        "INSTRUMENTOS HOSPITALARES", "COAGULACAO", "INSTRUMENTOS LABORATORIAIS",
        "LABORATORIAL", "LABORATORIO", "LABORATÓRIO", "HOSPITALAR", "HOSPITALARES", "IONS", "ION", "ÍONS",
        "GASOMETRIA", "TESTE RÁPIDO", "TESTE RAPIDO",
        "MANUTENCAO", "MANUTENÇÃO", "CALIBRACAO", "CALIBRAÇÃO", "AFERICAO", "AFERIÇÃO", "TIPAGEM SANGUINEA", "TIPAGEM SANGUÍNEA",
        "ALUGUEL", "LOCACAO", "LOCAÇÃO", "COMODATO", "COMODATOS", "URINA", "URANALISES", "HEMOCOMPONENTES", "URANALISE",
        "PECA", "PEÇA", "PECAS", "PEÇAS", "ACESSORIO", "ACESSÓRIO",
        "SERVIÇOS CONTÍNUOS DE CALIBRAÇÃO","MANUTENÇÃO PREVENTIVA E CORRETIVA",
        "MANUTENÇÃO E REPARO NOS COMPONENTES DE EQUIPAMENTO",  "ASSISTENCIA HOSPITALAR", "ASSISTÊNCIA HOSPITALAR",
        "ASSISTENCIA AMBULATORIAL", "ASSISTÊNCIA AMBULATORIAL", "MATERIAL AMBULATORIAL", "MATERIAIS AMBULATORIAIS"
    ]

    TERMOS_POSITIVOS_PRIORITARIOS = [
        "REAGENTE", "REAGENTES", "REAGENTE LABORATORIAL", "REAGENTES LABORATORIAIS",
        "EQUIPAMENTO BIOMEDICO", "EQUIPAMENTOS BIOMEDICOS", "EQUIPAMENTO BIOMÉDICO", "EQUIPAMENTOS BIOMÉDICOS",
        "BIOMEDICO", "BIOMÉDICO",
        "BIOQUIMICA", "BIOQUÍMICA", "BIOQUIMICO", "BIOQUÍMICO",
        "ANALISE CLINICA", "ANALISES CLINICAS", "ANÁLISE CLÍNICA", "ANÁLISES CLÍNICAS",
        "LABORATORIO DE ANALISES CLINICAS", "LABORATÓRIO DE ANÁLISES CLÍNICAS"
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

        termos_negativos_upper = list(dict.fromkeys(t.upper() for t in termos_negativos))
        termos_positivos_upper = list(dict.fromkeys(t.upper() for t in termos_positivos)) if termos_positivos else []

        hoje = datetime.now()
        hoje = datetime.now()
        data_inicial = (hoje - timedelta(days=dias_busca)).strftime('%Y%m%d')
        # Data final = Amanhã, para garantir que pegue tudo de hoje independente do fuso/hora
        data_final = (hoje + timedelta(days=1)).strftime('%Y%m%d')
        
        resultados = []
        
        # 6=Pregão, 8=Dispensa, 9=Inexigibilidade
        for modalidade in [6, 8, 9]:
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
                        # "modoDisputa": "1" # Removido para pegar compras diretas sem disputa aberta
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
                            if termos_positivos_upper and not any(t in obj for t in termos_positivos_upper):
                                continue

                            # 3) Filtro de Termos Negativos
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
            "modalidade": {6: "Pregão", 8: "Dispensa", 9: "Inexigibilidade"}.get(item.get('modalidadeId'), "Outra"),
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
        cnpj = licitacao_dict.get('cnpj') if licitacao_dict else None
        ano = licitacao_dict.get('ano') if licitacao_dict else None
        seq = licitacao_dict.get('seq') if licitacao_dict else None
        
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
        cache_key = '_itens_cache'
        if licitacao_dict and cache_key in licitacao_dict:
            return licitacao_dict[cache_key]

        cnpj = licitacao_dict.get('cnpj') if licitacao_dict else None
        ano = licitacao_dict.get('ano') if licitacao_dict else None
        seq = licitacao_dict.get('seq') if licitacao_dict else None
        
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

        if licitacao_dict is not None:
            licitacao_dict[cache_key] = itens_encontrados
        
        return itens_encontrados
