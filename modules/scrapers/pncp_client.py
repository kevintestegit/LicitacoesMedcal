import requests
from datetime import datetime, timedelta, date
import time
import re

class PNCPClient:
    BASE_URL = "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"
    MAX_PAGINAS = 60  # limite alto para não perder editais em estados com muito volume
    
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
        "MATERIAIS PRÉ-MOLDADOS", "MATERIAIS PRE-MOLDADOS", "corrida de rua",
        "CORRIDA DE RUA", "aquisição de combustíveis", "AQUISIÇÃO DE COMBUSTÍVEIS", "AQUISICAO DE COMBUSTIVEIS", "eventos de promoção",
        "EVENTOS DE PROMOÇÃO", "EVENTOS DE PROMOCAO", "locação de espaço físico", "LOCAÇÃO DE ESPAÇO FÍSICO", "LOCAÇÃO DE ESPACO FISICO", "LOCACAO DE ESPACO FISICO",
        "sacola ecológica", "SACOLA ECOLÓGICA", "SACOLA ECOLOGICA", "AQUISIÇÃO DE MÁQUINA DE CORTAR GRAMA", "MÁQUINA DE CORTAR GRAMA", "MAQUINA DE CORTAR GRAMA",
        "aquisição de câmeras", "AQUISIÇÃO DE CAMERAS", "AQUISIÇÃO DE CÂMERAS", "equipamentos de segurança", "EQUIPAMENTOS DE SEGURANÇA", "serviços de seguro predial",
        "SERVIÇOS DE SEGURO PREDIAL", "SERVICOS DE SEGURO PREDIAL", "ANIMAIS", "VEÍCULOS", "VEICULOS", "KIT ENXOVAL INFANTIL", "Veículo Automotor", "VEÍCULO AUTOMOTOR", "VEICULO AUTOMOTOR",
        "AGENCIAMENTO DE HOSPEDAGEM", "AGÊNCIA DE HOSPEDAGEM", "AGENCIA DE HOSPEDAGEM", "HOSPEDAGEM", "HOTELARIA", "SERVIÇOS DE HOTELARIA", "SERVICOS DE HOTELARIA", 
        "DIETA ENTERAL", "DIETA PARENTERAL", "TERAPIA NUTRICIONAL", "DIETA ORAL", "DIETAS",
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
        "SERVIÇOS DE MANUTENÇÃO DE ANTENA DE ALTA FREQUÊNCIA", "SERVICOS DE MANUTENCAO DE ANTENA DE ALTA FREQUENCIA",
        "VIDEOMONITORAMENTO", "COZINHA", "LOUSA", "LOUSAS", "PERSIANA", "PERSIANAS",
        "GENEROS ALIMENTICIOS", "GÊNEROS ALIMENTÍCIOS", "ALIMENTOS",
        "TECNOLOGIA DA INFORMACAO", "TI", "SOFTWARE", "SOLUCAO DE TECNOLOGIA", "SOLUÇÃO DE TECNOLOGIA",
        "SHOW", "ARTISTICA", "ARTÍSTICA", "EVENTO", "FESTA", "PALCO", "TENDA", "TENDAS", "LOCAÇÃO DE TENDA", "LOCAÇÃO DE TENDAS", "LOCACAO DE TENDA", "LOCACAO DE TENDAS",
        "EVENTOS", "SONORIZACAO", "SONORIZAÇÃO", "PAINEL DE LED", "PAINEL LED", "PAINEIS DE LED", "PAINÉIS DE LED",
        "CANCELAMENTO DO PREGAO", "CANCELAMENTO DO PREGÃO", "CANCELAMENTO DO EDITAL", "REVOGACAO", "REVOGAÇÃO",
        "PAVIMENTAÇÃO", "PAVIMENTACAO", "OBRA", "CONSTRUÇÃO", "CONSTRUCAO", "REFORMA",
        "LONA", "LONAS", "LONA PLASTICA", "LONA PLÁSTICA", "BISCOITO", "BISCOITOS", "BOLACHA", "BOLACHAS",
        "PADARIA", "CONFEITARIA", "PANIFICAÇÃO", "PANIFICACAO", "PÃO", "PAO", "PÃES", "PAES",
        "BOLO", "BOLOS", "DOCES", "DOCE", "SALGADOS", "SALGADO", "SANDUÍCHE", "SANDUICHE",
        "CAFÉ DA MANHÃ", "CAFE DA MANHA", "LANCHE", "LANCHES", "REFEIÇÃO", "REFEICAO", "REFEIÇÕES", "REFEICOES",
        "ALIMENTAÇÃO ESCOLAR", "ALIMENTACAO ESCOLAR", "MERENDA", "MERENDA ESCOLAR",
        "BANDA", "BANDAS", "MÚSICO", "MUSICO", "MÚSICOS", "MUSICOS", "CANTOR", "CANTORES",
        "DJ", "DISC JOCKEY", "SOM AUTOMOTIVO", "EQUIPAMENTO DE SOM", "EQUIPAMENTOS DE SOM",
        "ARTISTA", "ARTISTAS", "APRESENTAÇÃO ARTÍSTICA", "APRESENTACAO ARTISTICA",
        "BANDEIRA", "BANDEIRAS", "FAIXA DECORATIVA", "FAIXAS DECORATIVAS", "BANNER", "BANNERS",
        "TERMO ADITIVO", "EXTRATO DE ADITIVO", "EXTRATO DE CONTRATO", "EXTRATO DO CONTRATO",
        "PRORROGAÇÃO", "PRORROGACAO", "ADITIVO DE PRORROGAÇÃO", "ADITIVO DE PRORROGACAO",
        "ADJUDICAÇÃO", "ADJUDICACAO", "HOMOLOGAÇÃO", "HOMOLOGACAO",
        "ATA DE REGISTRO DE PREÇO", "ATA DE REGISTRO DE PRECOS",
        "RESULTADO DE JULGAMENTO",

        # Bloqueia PRESTAÇÃO DE SERVIÇOS (Medcal não presta serviços, FORNECE produtos)
        "PRESTAÇÃO DE SERVIÇOS DE EXAMES", "PRESTACAO DE SERVICOS DE EXAMES",
        "SERVIÇOS DE EXAMES", "SERVICOS DE EXAMES", "SERVIÇO DE EXAMES", "SERVICO DE EXAMES",
        "REALIZAÇÃO DE EXAMES", "REALIZACAO DE EXAMES", "EXECUÇÃO DE EXAMES", "EXECUCAO DE EXAMES",
        "EXAMES LABORATORIAIS E COMPLEMENTARES", "EXAMES DE LABORATORIO E COMPLEMENTARES",
        "PRESTAÇÃO DE SERVIÇOS LABORATORIAIS", "PRESTACAO DE SERVICOS LABORATORIAIS",
        "EMPRESA ESPECIALIZADA NA PRESTAÇÃO DE SERVIÇOS DE EXAMES",
        "EMPRESA ESPECIALIZADA EM EXAMES", "EXECUÇÃO DE EXAMES LABORATORIAIS",

        # Bloqueia CAPACITAÇÃO/TREINAMENTO (Medcal não presta treinamento como serviço)
        "CAPACITAÇÃO PROFISSIONAL", "CAPACITACAO PROFISSIONAL", "CAPACITAÇÃO", "CAPACITACAO",
        "TREINAMENTO PROFISSIONAL", "TREINAMENTO", "TREINAMENTOS",
        "CURSO", "CURSOS", "FORMAÇÃO PROFISSIONAL", "FORMACAO PROFISSIONAL",
        "QUALIFICAÇÃO PROFISSIONAL", "QUALIFICACAO PROFISSIONAL",
        "SERVIÇOS DE CAPACITAÇÃO", "SERVICOS DE CAPACITACAO",
        "PRESTAÇÃO DE SERVIÇO DE CAPACITAÇÃO", "PRESTACAO DE SERVICO DE CAPACITACAO",
        "EMPRESA PARA PRESTAÇÃO DE SERVIÇO DE CAPACITAÇÃO",

        # Bloqueia outros serviços assistenciais que não são fornecimento de produtos
        "SERVIÇOS MÉDICOS", "SERVICOS MEDICOS", "PRESTAÇÃO DE SERVIÇOS MÉDICOS",
        "SERVIÇOS DE SAÚDE", "SERVICOS DE SAUDE", "PRESTAÇÃO DE SERVIÇOS DE SAÚDE",
        "ATENDIMENTO AMBULATORIAL", "CONSULTA MÉDICA", "CONSULTAS MEDICAS",

        # Novos termos adicionados (Computadores/TI, Intercâmbio, Água/Alimentos)
        "COMPUTADOR", "COMPUTADORES", "NOTEBOOK", "NOTEBOOKS", "WEBCAM", "WEBCAMS", 
        "DESKTOP", "PC", "TABLET", "TABLETS", "IMPRESSORA", "IMPRESSORAS", 
        "SCANNER", "SCANNERS", "PERIFERICOS", "PERIFÉRICOS",
        "INTERCAMBIO", "INTERCÂMBIO", "EDUCACIONAL", "CULTURAL", "ESTUDANTE", 
        "ESTUDANTES", "ALUNO", "ALUNOS", "PEDAGOGICO", "PEDAGÓGICO",
        "AGUA MINERAL", "ÁGUA MINERAL", "GARRAFÃO", "GARRAFAO", "GARRAFA", 
        "COPO", "BEBIDA", "ALIMENTACAO", "ALIMENTAÇÃO", "LANCHE", "REFEICAO", "REFEIÇÃO",
        
        # Bloqueio estrito de MEDICAMENTOS (Medcal NÃO vende remédios)
        "COMPRIMIDO", "COMPRIMIDOS", "CAPSULA", "CAPSULAS", "CÁPSULA", "CÁPSULAS",
        "INJETAVEL", "INJETÁVEL", "INJETAVEIS", "INJETÁVEIS", "AMPOLA", "AMPOLAS",
        "FRASCO-AMPOLA", "XAROPE", "SUSPENSAO ORAL", "SUSPENSÃO ORAL", "POMADA", "CREME DERMATOLOGICO",
        "ANTIBIOTICO", "ANTIBIÓTICO", "ANTIBIOTICOS", "ANTIBIÓTICOS", "ANALGESICO", "ANALGÉSICO",
        "ANTI-INFLAMATORIO", "ANTI-INFLAMATÓRIO", "ANESTESICO", "ANESTÉSICO", "PSICOTROPICO", "PSICOTRÓPICO",
        "FARMACIA BASICA", "FARMÁCIA BÁSICA", "FARMACIA HOSPITALAR", "FARMÁCIA HOSPITALAR",
        "AQUISICAO DE MEDICAMENTOS", "AQUISIÇÃO DE MEDICAMENTOS", "DISTRIBUICAO DE MEDICAMENTOS",
        
        # Bloqueio de Itens Irrelevantes (Enxoval, Livros, etc)
        "ENXOVAL", "CAMA E MESA", "ROUPARIA", "TECIDOS", "TECIDO", "LENÇOL", "LENCOL", "TRAVESSEIRO",
        "LIVRO", "LIVROS", "BIBLIOTECA", "ACERVO BIBLIOGRAFICO", "PUBLICACOES", "PUBLICAÇÕES",
        "REVISTA", "JORNAL", "PERIODICO", "COLECAO", "COLEÇÃO",
        "MATERIAL DE LIMPEZA", "HIGIENE E LIMPEZA", "COPA E COZINHA",
        
        # Itens hospitalares NÃO comercializados pela Medcal
        "BERCO", "BERÇO", "BERÇOS", "BERCOS", "CAMA HOSPITALAR", "CAMAS HOSPITALARES",
        "COLCHAO", "COLCHÃO", "COLCHOES", "COLCHÕES", "MACA", "MACAS",
        "CADEIRA DE RODAS", "CADEIRAS DE RODAS", "MULETA", "MULETAS",
        "ANDADOR", "ANDADORES", "BENGALA", "BENGALAS",
        "ROUPA DE CAMA", "ROUPAS DE CAMA", "COBERTA", "COBERTAS", "COBERTOR", "COBERTORES",
        "FRONHA", "FRONHAS", "TOALHA", "TOALHAS", "HAMPER", "HAMPERS",
        "CORTINA", "CORTINAS", "PERSIANA", "PERSIANAS",
        "AR CONDICIONADO", "CLIMATIZADOR", "CLIMATIZADORES", "SPLIT",
        "GELADEIRA", "REFRIGERADOR", "FREEZER", "FRIGORIFICO",
        "FOGAO", "FOGÃO", "MICROONDAS", "FORNO",
        "MOBILIARIO", "MOBILIÁRIO", "MOVEL", "MÓVEL", "MOVEIS", "MÓVEIS",
        "ARMARIO", "ARMÁRIO", "ESTANTE", "PRATELEIRA", "MESA", "MESAS", "CADEIRA", "CADEIRAS",
        "MAMOGRAFO", "MAMÓGRAFO", "TOMOGRAFO", "TOMÓGRAFO", "RESSONANCIA", "RESSONÂNCIA",
        "ULTRASSOM", "ULTRASSONOGRAFIA", "ECOGRAFO", "ECÓGRAFO",
        "DESFIBRILADOR", "CARDIOVERSOR", "MONITOR MULTIPARAMETRO", "MONITOR MULTIPARÂMETRO",
        "BISTURI ELETRICO", "BISTURI ELÉTRICO", "FOCO CIRURGICO", "FOCO CIRÚRGICO",
        "MESA CIRURGICA", "MESA CIRÚRGICA", "INSTRUMENTOS CIRURGICOS", "INSTRUMENTOS CIRÚRGICOS",
        "ORTESE", "ÓRTESE", "PROTESE", "PRÓTESE", "ORTESES", "ÓRTESES", "PROTESES", "PRÓTESES",
        "FRALDAS", "FRALDA", "ABSORVENTE", "ABSORVENTES",
        "OXIMETRO", "OXÍMETRO", "OXIMETROS", "OXÍMETROS", "TERMOMETRO", "TERMÔMETRO",
        "ESTETOSCOPIO", "ESTETOSCÓPIO", "ESFIGMOMANOMETRO", "ESFIGMOMANÔMETRO",
        "BALANCA", "BALANÇA", "ANTROPOMETRO", "ANTROPÔMETRO",
        "NEBULIZADOR", "INALADOR", "ASPIRADOR CIRURGICO", "ASPIRADOR CIRÚRGICO"
    ]
    # Termos POSITIVOS padrão (Unificado)
    TERMOS_POSITIVOS_PADRAO = [
        "EXAMES LABORATORIAS", "EXAMES","APARELHOS HOSPITALARES", "APARELHOS LABORATORIAIS", 
        "MATERIAL HOSPITALAR", "MATERIAIS HOSPITALARES", "HEMOSTASIA", "IMUNO FLUORECÊNCIA", "IMUNOFLUORESCÊNCIA", 
        "MATERIAL LABORATORIAL", "MATERIAIS LABORATORIAIS", "LABORATORIO DE ANALISES CLINICAS", "LABORATORIO",
        "MATERIAL DE LABORATORIO", "MATERIAIS DE LABORATORIO", "INSUMO", "INSUMOS", "REAGENTE",
        "REAGENTES", "PRODUTOS HOSPITALARES", "HORMONIOS", "REAGENTES LABORATORIAIS",
        "PRODUTOS LABORATORIAIS", "EQUIPAMENTO HOSPITALAR", "EQUIPAMENTOS HOSPITALARES", "REAGENTES DE LABORATORIO",
        "EQUIPAMENTO DE HEMATOLOGIA", "EQUIPAMENTO DE BIOQUIMICA", "EQUIPAMENTO DE COAGULACAO", "POCT",
        "EQUIPAMENTO DE IONOGRAMA", "AGUA DESTILADA", "CITOPALOGIA", "REAGENTES PARA LABORATORIO",
        "EQUIPAMENTO LABORATORIAL", "EQUIPAMENTOS LABORATORIAIS", "EQUIPAMENTOS DE LABORATORIO",
        "EQUIPAMENTO BIOMEDICO", "EQUIPAMENTOS BIOMEDICOS", "ANALISE CLINICA", "ANALISES CLINICAS",
        "ANATOMIA PATOLOGICA", "CITOPATOLOGIA","BIOQUIMICA", "HEMATOLOGIA", "IMUNOLOGIA", "TT/TTPA",
        "COAGULAÇÃO", "APARELHO DE COAGULAÇÃO", "IMUNO-HISTOQUÍMICA", "IMUNO", "HORMÔNIOS", "HORMONIO",
        "INSTRUMENTOS HOSPITALARES", "COAGULACAO", "INSTRUMENTOS LABORATORIAIS",
        "LABORATORIAL", "LABORATORIO", "LABORATÓRIO", "HOSPITALAR", "HOSPITALARES", "IONS", "ION", "ÍONS",
        "MANUTENCAO", "MANUTENÇÃO", "CALIBRACAO", "CALIBRAÇÃO", "AFERICAO", "AFERIÇÃO", "TIPAGEM SANGUINEA", "TIPAGEM SANGUÍNEA",
        "ALUGUEL", "LOCACAO", "LOCAÇÃO", "COMODATO", "COMODATOS", "URINA", "URANALISES", "HEMOCOMPONENTES", "URANALISE",
        "SERVIÇOS CONTÍNUOS DE CALIBRAÇÃO","MANUTENÇÃO PREVENTIVA E CORRETIVA",
        "MANUTENÇÃO E REPARO NOS COMPONENTES DE EQUIPAMENTO",  "ASSISTENCIA HOSPITALAR", "ASSISTÊNCIA HOSPITALAR",
        "ASSISTENCIA AMBULATORIAL", "ASSISTÊNCIA AMBULATORIAL", "MATERIAL AMBULATORIAL", "MATERIAIS AMBULATORIAIS",
        "REAGENTE LABORATORIAL", "REAGENTES DE LABORATORIO", "EQUIPAMENTO BIOMÉDICO", "EQUIPAMENTOS BIOMÉDICOS", 
        "EQUIPAMENTO HEMATOLOGIA", "EQUIPAMENTOS HEMATOLOGIA", "EQUIPAMENTOS BIOQUIMICA", "EQUIPAMENTO BIOQUIMICA", 
        "EQUIPAMENTO IONOGRAMA", "EQUIPAMENTOS IONOGRAMA", "EQUIPAMENTOS COAGULACAO", "EQUIPAMENTO COAGULACAO",
        "BIOMEDICO", "BIOMÉDICO", "BIOMEDICINA", "BIOQUIMICO", "BIOQUÍMICO", "IONOGRAMA", "EQUIPAMENTO AUTOMATIZADO",
        "EQUIPAMENTOS AUTOMATIZADOS",
        "ANÁLISE CLÍNICA", "ANÁLISES CLÍNICAS", "LABORATÓRIO DE ANÁLISES CLÍNICAS",
        "TUBO", "TUBOS", "COLETA DE SANGUE", "COVID", "GASOMETRIA", "TESTE RÁPIDO", "TESTE RAPIDO"
    ]

    # Subconjunto prioritário para reduzir falsos positivos (usado como filtro inicial)
    # REGRA: Termos devem indicar EQUIPAMENTO ou PRODUTO, não apenas área/setor
    TERMOS_PRIORITARIOS = [
        # Locação/Comodato de Equipamentos (foco principal Medcal)
        "LOCAÇÃO DE EQUIPAMENTOS", "LOCAÇÃO DE EQUIPAMENTO", "ALUGUEL DE EQUIPAMENTOS", "COMODATO",
        "LOCACAO DE EQUIPAMENTOS", "LOCACAO DE EQUIPAMENTO", "ALUGUEL DE EQUIPAMENTO",
        "DISPONIBILIZAÇÃO DE EQUIPAMENTO", "DISPONIBILIZACAO DE EQUIPAMENTO",
        "CESSÃO DE EQUIPAMENTO", "CESSAO DE EQUIPAMENTO",
        
        # Equipamentos ESPECÍFICOS (não apenas a área)
        "EQUIPAMENTO DE HEMATOLOGIA", "EQUIPAMENTO DE BIOQUIMICA", "EQUIPAMENTO DE COAGULACAO",
        "EQUIPAMENTO DE IMUNOLOGIA", "EQUIPAMENTO DE IONOGRAMA", "EQUIPAMENTO DE GASOMETRIA",
        "ANALISADOR HEMATOLOGICO", "ANALISADOR HEMATOLÓGICO", "ANALISADOR DE HEMATOLOGIA",
        "ANALISADOR BIOQUIMICO", "ANALISADOR BIOQUÍMICO", "ANALISADOR DE BIOQUIMICA",
        "ANALISADOR DE COAGULACAO", "ANALISADOR DE COAGULAÇÃO", "COAGULOMETRO", "COAGULÔMETRO",
        "ANALISADOR DE IMUNOLOGIA", "ANALISADOR IMUNOLOGICO", "ANALISADOR IMUNOLÓGICO",
        "ANALISADOR DE IONOGRAMA", "ANALISADOR DE IONS", "ANALISADOR DE ELETRÓLITOS",
        "ANALISADOR DE GASOMETRIA", "HEMOGASOMETRO", "HEMOGASÔMETRO", "GASOMETRO", "GASÔMETRO",
        "EQUIPAMENTO AUTOMATIZADO", "EQUIPAMENTOS AUTOMATIZADOS",
        "EQUIPAMENTO LABORATORIAL", "EQUIPAMENTOS LABORATORIAIS",
        
        # Reagentes e Insumos ESPECÍFICOS
        "REAGENTES PARA HEMATOLOGIA", "REAGENTE HEMATOLOGICO", "REAGENTES HEMATOLOGICOS",
        "REAGENTES PARA BIOQUIMICA", "REAGENTE BIOQUIMICO", "REAGENTES BIOQUIMICOS",
        "REAGENTES PARA COAGULACAO", "REAGENTE COAGULACAO", "REAGENTES COAGULACAO",
        "REAGENTES PARA IMUNOLOGIA", "REAGENTE IMUNOLOGICO", "REAGENTES IMUNOLOGICOS",
        "REAGENTES PARA IONOGRAMA", "REAGENTE IONOGRAMA", "REAGENTES IONOGRAMA",
        "REAGENTES PARA GASOMETRIA", "REAGENTE GASOMETRIA", "REAGENTES GASOMETRIA",
        "REAGENTES LABORATORIAIS", "REAGENTE LABORATORIAL",
        "INSUMOS LABORATORIAIS", "INSUMO LABORATORIAL",
        "REAGENTES PARA LABORATORIO", "REAGENTES DE LABORATORIO",
        
        # Análises Clínicas (termos compostos mais específicos)
        "LABORATORIO DE ANALISES CLINICAS", "LABORATÓRIO DE ANÁLISES CLÍNICAS",
        "ANALISES CLINICAS", "ANÁLISES CLÍNICAS",
        
        # Consumíveis ESPECÍFICOS
        "TUBO DE COLETA", "TUBOS DE COLETA", "TUBO VACUO", "TUBO VÁCUO",
        "TUBO EDTA", "TUBO HEPARINA", "TUBO CITRATO",
        "COLETA DE SANGUE", "COLETA SANGUINEA", "COLETA SANGUÍNEA",
        "LUVA DE PROCEDIMENTO", "LUVAS DE PROCEDIMENTO",
        "MASCARA CIRURGICA", "MÁSCARA CIRÚRGICA", "MASCARAS CIRURGICAS",
        
        # Manutenção de equipamentos laboratoriais
        "MANUTENCAO DE EQUIPAMENTO LABORATORIAL", "MANUTENÇÃO DE EQUIPAMENTO LABORATORIAL",
        "MANUTENCAO PREVENTIVA E CORRETIVA", "MANUTENÇÃO PREVENTIVA E CORRETIVA",
        "CALIBRACAO DE EQUIPAMENTO", "CALIBRAÇÃO DE EQUIPAMENTO"
    ]
    # Bloqueios adicionais para eventos/inscrições genéricas
    TERMOS_EVENTOS_NEGATIVOS = [
        "INSCRICAO", "INSCRIÇÃO", "CONFERENCIA", "CONFERÊNCIA", "CONGRESSO",
        "SEMINARIO", "SEMINÁRIO", "WORKSHOP", "PALESTRA", "EVENTOS"
    ]

    # Anti-ruido adicional (fora do escopo Medcal)
    TERMOS_NEGATIVOS_EXTRA = [
        "LEITE", "LEITES", "FORMULA INFANTIL", "F?RMULA INFANTIL", "SUPLEMENTO NUTRICIONAL", "SUPLEMENTO ALIMENTAR",
        "INSUMOS PARA SAUDE DA MULHER", "SAUDE DA MULHER", "ABSORVENTE", "HIGIENE FEMININA",
        "CREDENCIAMENTO", "ATENDIMENTO DOMICILIAR", "HOME CARE", "AMBULATORIAL", "AMBULATORIO", "PLANTAO", "PLANT?O",
        "SERVI?OS MEDICOS", "SERVICOS MEDICOS", "SERVI?O MEDICO", "SERVICO MEDICO", "CONSULTA MEDICA", "CONSULTA M?DICA",
        "SERVI?OS ODONTOLOGICOS", "SERVICOS ODONTOLOGICOS", "ODONTOLOGIA",
        "URGENCIA", "URG?NCIA", "EMERGENCIA", "EMERG?NCIA", "SAMU", "24 HORAS",
        "METALURGICA", "METAL?RGICA", "SERRALHERIA", "ESTRUTURA METALICA", "ESTRUTURA MET?LICA", "PORTAO", "PORT?O", "GRADE", "ESQUADRIA", "FERRAGEM",
        # Novos blocos de ruido (fora do escopo Medcal)
        "VIDEOMAKER", "VIDEO", "FILMAGEM", "AUDIOVISUAL", "FOTOGRAFIA", "CAPTACAO DE IMAGEM",
        "AR CONDICIONADO", "AR-CONDICIONADO", "APARELHO DE AR CONDICIONADO", "APARELHOS DE AR CONDICIONADO",
        "DECORACAO NATALINA", "ILUMINACAO NATALINA", "MONTAGEM DE DECORACAO", "DESMONTAGEM DE DECORACAO", "NATALINA",
        "CREDENCIAMENTO DE PERMISSIONARIOS", "PERMISSIONARIOS", "BOXES", "ESPAÇO PUBLICO", "ESPACO PUBLICO", "MERCADO MUNICIPAL",
        "MATERIAL PERSONALIZADO", "BRINDES", "EVENTO ACADEMICO", "EVENTO EDUCACIONAL",
        "CAFE TORRADO", "CAFE MOIDO", "CAFE SUPERIOR", "CAFE TORRADO MOIDO",
        "ELETROBOMBA", "ELETROBOMBAS", "BOMBA ELETRICA", "BOMBA HIDRAULICA",
        "GASES ESPECIAIS", "CILINDRO DE GAS", "FORNECIMENTO DE GAS", "COMODATO DE CILINDRO",
        # Novos filtros solicitados
        "DRONE", "VANT", "RTK",
        "BARRA NUTRICIONAL", "BARRAS NUTRICIONAIS",
        "GASES MEDICINAIS", "GAS MEDICINAL", "COMODATO DE GAS", "BACKUP DE GAS",
        "PROPAGANDA VOLANTE", "CARRO DE SOM", "DIVULGACAO SONORA", "AUDIO EM CARRO DE SOM",
        "TUBO PVC", "TUBOS PVC", "PVC SOLDAVEL",
        "PERFURATRIZ", "MANUTENCAO DE PERFURATRIZ",
        "MUDAS", "PLANTAS ORNAMENTAIS", "ARVORES", "GRAMAS", "FLORES", "REVITALIZACAO DE PRACAS", "AREAS VERDES",
        "LOCACAO DE CONTAINER", "LOCAÇÃO DE CONTAINER",
        "INSUMOS DE PETREO", "PAVIMENTACAO CAUQ", "CAUQ", "CBUQ", "ASFALTO", "ASFALTICO",
        "LOCACAO DE VIATURA", "LOCAÇÃO DE VIATURA", "VIATURA POLICIAL",
        "AUDITORIA INDEPENDENTE", "AUDITORIA DE FATURAMENTO", "AUDITORIA CONTRATUAL",
        "RECARGA DE OXIGENIO", "OXIGENIO MEDICINAL", "CESSAO DE CILINDRO", "COMODATO DE CILINDROS",
        "TELECOMUNICACOES", "TELECOMUNICAÇÕES", "REDE DE DADOS", "REDE WIFI", "WI-FI", "WIFI",
        "MATERIAL PARA EMBALAGEM", "MATERIAIS PARA EMBALAGEM", "CONDICIONAMENTO E EMBALAGEM",
        "VALVULA", "VALVULAS", "CONEXAO", "CONEXOES", "TRATAMENTO DE AGUA", "SANEAMENTO",
        
        # Novos filtros solicitados (Atualização Recente)
        "LAVANDERIA", "LAVAGEM DE ROUPA", "HIGIENIZACAO DE TEXTEIS",
        "SOFTWARE", "SOFTWARES", "SISTEMA DE GESTAO", "SIAFIC", "LICENCA DE USO",
        "MATERIAL PERSONALIZADO", "BRINDES PERSONALIZADOS",
        "FOTOVOLTAICA", "FOTOVOLTAICO", "USINA SOLAR", "ENERGIA SOLAR", "PAINEL SOLAR",
        "ARES CONDICIONADOS", "ARES-CONDICIONADOS", "APARELHO DE AR",
        "PISCINA", "ESPELHO D'AGUA", "ESPELHO D AGUA", "LIMPEZA DE PISCINA",
        "MEDICINA DO TRABALHO", "EXAMES OCUPACIONAIS", "SAUDE OCUPACIONAL", "ASO"
    ]
    TERMOS_NEGATIVOS_PADRAO = TERMOS_NEGATIVOS_PADRAO + TERMOS_NEGATIVOS_EXTRA


    def __init__(self):
        self.session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(max_retries=3)
        self.session.mount('https://', adapter)
        self.session.mount('http://', adapter)
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

    def buscar_oportunidades(self, dias_busca=30, estados=['RN', 'PB', 'PE', 'AL'], termos_positivos=[], termos_negativos=None, apenas_abertas=True):
        """
        Busca licitações (Pregão/Dispensa) publicadas nos últimos X dias.
        Aplica filtros de termos positivos (OR) e negativos (NOT).
        Se apenas_abertas=True, exige dataEncerramentoProposta >= hoje.
        """
        if termos_negativos is None:
            termos_negativos = self.TERMOS_NEGATIVOS_PADRAO + self.TERMOS_EVENTOS_NEGATIVOS

        termos_negativos_upper = list(dict.fromkeys(t.upper() for t in termos_negativos))
        termos_positivos_upper = list(dict.fromkeys(t.upper() for t in termos_positivos)) if termos_positivos else []
        termos_prioritarios_upper = [t.upper() for t in self.TERMOS_PRIORITARIOS]

        hoje = datetime.now()
        
        # LÓGICA OTIMIZADA:
        # Se queremos apenas abertas, não importa quando foi publicado (pode ser há 30 dias).
        # Importa que o encerramento seja futuro.
        # Por isso, estendemos a dataInicial de publicação para garantir que não perdemos nada,
        # mas filtramos rigidamente pela dataFinalEncerramentoProposta.
        
        if apenas_abertas:
            data_inicial_dt = hoje - timedelta(days=120) # Janela segura de publicação (4 meses)
            data_inicial_enc_dt = hoje # Encerramento a partir de HOJE
            data_final_enc_dt = hoje + timedelta(days=120) # Até 4 meses pra frente
        else:
            data_inicial_dt = hoje - timedelta(days=dias_busca)
            data_inicial_enc_dt = None
            data_final_enc_dt = None

        data_final_dt = hoje

        # Formatos aceitos pela API variam; tentaremos AAAAMMDD e AAAA-MM-DD
        data_inicial = data_inicial_dt.strftime('%Y%m%d')
        data_final = data_final_dt.strftime('%Y%m%d')
        data_inicial_iso = data_inicial_dt.strftime('%Y-%m-%d')
        data_final_iso = data_final_dt.strftime('%Y-%m-%d')
        
        data_inicial_enc = data_inicial_enc_dt.strftime('%Y%m%d') if data_inicial_enc_dt else None
        data_final_enc = data_final_enc_dt.strftime('%Y%m%d') if data_final_enc_dt else None
        
        resultados = []

        print(f"\n{'='*80}")
        print("[PNCP] INICIANDO BUSCA NO PNCP")
        print(f"Publicado entre: {data_inicial} e {data_final}")
        if apenas_abertas:
            print(f"Encerramento entre: {data_inicial_enc} e {data_final_enc}")
        print(f"Estados: {estados}")
        print(f"Filtro apenas abertas: {apenas_abertas}")
        print(f"{'='*80}\n")

        total_api = 0

        # 6=Pregão Eletrônico, 8=Dispensa de Licitação/Compra Direta, 12=Dispensa Emergencial
        for modalidade in [6, 8, 12]:
            modalidade_nome = {6: "Pregão Eletrônico", 8: "Dispensa/Compra Direta", 12: "Dispensa Emergencial"}.get(modalidade)

            for uf in estados:
                print(f"\n[PNCP] Buscando {modalidade_nome} em {uf}...")

                # Busca paginada com limite
                tamanho_pagina = 50  # API retorna erro 400 acima de 50
                for pagina in range(1, self.MAX_PAGINAS + 1):
                    params = {
                        "dataInicial": data_inicial,
                        "dataFinal": data_final,
                        "codigoModalidadeContratacao": modalidade,
                        "uf": uf,
                        "pagina": str(pagina),
                        "tamanhoPagina": str(tamanho_pagina)
                    }
                    if apenas_abertas and data_inicial_enc and data_final_enc:
                        # Alguns clusters aceitam filtro direto por encerramento de proposta
                        params["dataInicialEncerramentoProposta"] = data_inicial_enc
                        params["dataFinalEncerramentoProposta"] = data_final_enc

                    try:
                        # Aumentado timeout para 30s e usando session com retry
                        resp = self.session.get(self.BASE_URL, params=params, headers=self.headers, timeout=30)

                        # Fallback: alguns clusters do PNCP exigem data no formato AAAA-MM-DD
                        if resp.status_code == 400:
                            params_iso = params.copy()
                            params_iso["dataInicial"] = data_inicial_iso
                            params_iso["dataFinal"] = data_final_iso
                            resp = self.session.get(self.BASE_URL, params=params_iso, headers=self.headers, timeout=30)

                        if resp.status_code != 200:
                            print(f"  [WARN] Erro HTTP {resp.status_code} - Pagina {pagina}")
                            # Não quebra o loop, tenta a próxima página ou modalidade
                            continue

                        data = resp.json().get('data', [])
                        total_api += len(data)

                        if not data:
                            print(f"  [INFO] Pagina {pagina} vazia - fim da busca para {uf}")
                            break

                        print(f"  [OK] Pagina {pagina}: {len(data)} licitacoes encontradas")
                        
                        for item in data:

                            # 1) Campo do objeto na API de CONSULTA é "objetoCompra" ou "objeto"
                            obj_raw = item.get('objetoCompra') or item.get('objeto') or ""
                            obj = obj_raw.upper()
                            
                            if not obj:
                                continue

                            # 2) Filtro de Termos Prioritários (reduz ruído) ou Positivos
                            tem_prio = any(t in obj for t in termos_prioritarios_upper)
                            tem_pos = any(t in obj for t in termos_positivos_upper) if termos_positivos_upper else False
                            if not tem_prio and not tem_pos:
                                continue

                            # 3) Filtro de Termos Negativos
                            if any(t in obj for t in termos_negativos_upper):
                                continue
                            
                            # 4) Filtro de Data (Encerramento Proposta)
                            # Bloqueia se tem data e já encerrou.
                            data_encerramento = item.get("dataEncerramentoProposta")
                            if not data_encerramento:
                                continue  # Sem data = descarta (não dá para participar)
                            dias_restantes = -999  # Valor padrão para itens sem data

                            if data_encerramento:
                                dias_restantes = self.calcular_dias(data_encerramento)
                                if dias_restantes < 0:
                                    continue  # fora do prazo

                            # Adiciona dias restantes ao objeto parseado
                            parsed = self._parse_licitacao(item)
                            parsed['dias_restantes'] = dias_restantes
                            resultados.append(parsed)
                            
                    except requests.exceptions.ReadTimeout:
                        print(f"  [FAIL] Timeout na pagina {pagina} de {uf}. Tentando proxima...")
                        continue
                    except Exception as e:
                        print(f"  [FAIL] ERRO na pagina {pagina}: {e}")
                        continue

                    # Se veio menos que o tamanho da página, acabou a lista
                    if len(data) < tamanho_pagina:
                        break

                    time.sleep(0.05)

        print(f"\n{'='*80}")
        print("[PNCP] RESUMO DA BUSCA")
        print(f"Total retornado pela API: {total_api}")
        print(f"Total APROVADO (após filtros): {len(resultados)}")
        print(f"{'='*80}\n")

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
            "modalidade": {6: "Pregão", 8: "Dispensa", 9: "Inexigibilidade", 12: "Emergencial"}.get(item.get('modalidadeId'), "Outra"),
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

    def download_arquivo(self, url):
        """
        Baixa o conteúdo de um arquivo (PDF) em memória.
        Retorna bytes ou None.
        """
        try:
            resp = requests.get(url, headers=self.headers, timeout=30)
            if resp.status_code == 200:
                return resp.content
        except Exception as e:
            print(f"Erro ao baixar arquivo {url}: {e}")
        return None

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
            
        urls_tentativas = [
            f"https://pncp.gov.br/api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{seq}/itens",
            f"https://pncp.gov.br/api/consulta/v1/contratacoes/{cnpj}/{ano}/{seq}/itens",  # Fallback público
        ]

        itens_encontrados = []
        for url in urls_tentativas:
            try:
                resp = requests.get(url, headers=self.headers, timeout=10)
                if resp.status_code != 200:
                    print(f"[PNCP] Itens HTTP {resp.status_code} em {url}")
                    continue

                lista = resp.json() or []
                if not lista:
                    # tenta próximo endpoint se resposta vazia
                    print(f"[PNCP] Itens vazios em {url}")
                    continue

                for i in lista:
                    itens_encontrados.append({
                        "numero": i.get('numeroItem'),
                        "descricao": i.get('descricao'),
                        "quantidade": i.get('quantidade'),
                        "unidade": i.get('unidadeMedida'),
                        "valor_estimado": i.get('valorTotalEstimado'),
                        "valor_unitario": i.get('valorUnitarioEstimado')
                    })
                break  # já achou itens, não precisa tentar demais
            except Exception as e:
                print(f"Erro ao buscar itens em {url}: {e}")

        if licitacao_dict is not None:
            licitacao_dict[cache_key] = itens_encontrados
        
        return itens_encontrados

    def buscar_por_id(self, cnpj: str, ano: str, seq: str):
        """
        Busca uma licitação específica por CNPJ/ano/seq direto no endpoint de compra.
        Retorna o dict parseado ou None.
        """
        if not (cnpj and ano and seq):
            return None
        url = f"https://pncp.gov.br/api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{seq}"
        try:
            resp = requests.get(url, headers=self.headers, timeout=10)
            if resp.status_code != 200:
                print(f"Erro buscar_por_id: {resp.status_code} {resp.text[:200]}")
                return None
            data = resp.json()
            parsed = self._parse_licitacao(data)
            parsed['dias_restantes'] = self.calcular_dias(data.get("dataEncerramentoProposta"))
            return parsed
        except Exception as e:
            print(f"Erro buscar_por_id: {e}")
            return None

    def buscar_precos_historicos(self, descricao_item, uf=None, dias=90):
        """
        Busca histórico de preços HOMOLOGADOS para um item similar.
        Usa a API de Itens: /api/consulta/v1/contratacoes/itens
        Retorna estatísticas (média, min, max) e lista de preços.
        """
        url = "https://pncp.gov.br/api/consulta/v1/contratacoes/itens"
        
        hoje = datetime.now()
        data_ini = (hoje - timedelta(days=dias)).strftime('%Y%m%d')
        data_fim = hoje.strftime('%Y%m%d')
        
        params = {
            "dataInicial": data_ini,
            "dataFinal": data_fim,
            "descricao": descricao_item,
            "pagina": "1",
            "tamanhoPagina": "20"
        }
        if uf:
            params["uf"] = uf
            
        try:
            resp = self.session.get(url, params=params, headers=self.headers, timeout=15)
            if resp.status_code == 200:
                dados = resp.json().get('data', [])
                precos = []
                for d in dados:
                    # Prioriza valor homologado (vencedor), senão pega estimado
                    val = d.get('valorUnitarioHomologado') or d.get('valorUnitarioEstimado')
                    if val and val > 0:
                        precos.append(val)
                
                if not precos:
                    return None
                    
                return {
                    "media": sum(precos) / len(precos),
                    "min": min(precos),
                    "max": max(precos),
                    "amostra": len(precos)
                }
        except Exception as e:
            print(f"Erro ao buscar preços: {e}")
            return None
