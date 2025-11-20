import requests
import time
from datetime import datetime, date, timedelta

# --- CONFIGURAÇÕES GERAIS ---
ESTADOS_ALVO = ['RN', 'PE', 'PB', 'AL']

# Termos POSITIVOS: o que você quer (bens/insumos/equipamentos da área de saúde)
TERMOS_POSITIVOS = [
    # materiais / insumos / reagentes
    "MATERIAL HOSPITALAR",
    "MATERIAIS HOSPITALARES",
    "MATERIAL MEDICO",
    "MATERIAIS MEDICOS",
    "MATERIAL MÉDICO",
    "MATERIAIS MÉDICOS",
    "MATERIAL LABORATORIAL",
    "MATERIAIS LABORATORIAIS",
    "MATERIAL DE LABORATORIO",
    "MATERIAIS DE LABORATORIO",
    "INSUMO",
    "INSUMOS",
    "REAGENTE",
    "REAGENTES",
    "PRODUTOS MEDICOS",
    "PRODUTOS MÉDICOS",
    "PRODUTOS HOSPITALARES",
    "PRODUTOS LABORATORIAIS",

    # equipamentos e instrumentos
    "EQUIPAMENTO HOSPITALAR",
    "EQUIPAMENTOS HOSPITALARES",
    "EQUIPAMENTO MEDICO",
    "EQUIPAMENTOS MEDICOS",
    "EQUIPAMENTO MÉDICO",
    "EQUIPAMENTOS MÉDICOS",
    "EQUIPAMENTO LABORATORIAL",
    "EQUIPAMENTOS LABORATORIAIS",
    "EQUIPAMENTOS DE LABORATORIO",
    "APARELHOS HOSPITALARES",
    "APARELHOS MEDICOS",
    "APARELHOS MÉDICOS",
    "APARELHOS LABORATORIAIS",
    "INSTRUMENTOS CIRURGICOS",
    "INSTRUMENTOS CIRÚRGICOS",
    "INSTRUMENTOS HOSPITALARES",
    "INSTRUMENTOS LABORATORIAIS",

    # gases medicinais
    "GASES MEDICINAIS",
    "GAS MEDICINAL",
    "GÁS MEDICINAL",
    "OXIGENIO MEDICINAL",
    "OXIGÊNIO MEDICINAL",
    "AR MEDICINAL",
    "AR COMPRIMIDO MEDICINAL",

    # contexto típico da área de saúde que aponta para bens
    "LABORATORIAL",
    "LABORATORIO",
    "LABORATÓRIO",
    "HOSPITALAR",
    "HOSPITALARES",
    "ODONTOLOGICO",
    "ODONTOLÓGICO",
    "ODONTOLOGICOS",
    "ODONTOLÓGICOS",
    "ODONTO-MEDICO-HOSPITALAR",
    "ODONTOMEDICOHOSPITALAR",
]

# Termos NEGATIVOS: o que você NÃO quer (planos/serviços médicos + viagens, etc.)
TERMOS_NEGATIVOS = [
    # planos/assistência em saúde (já existiam)
    "PLANO DE SAUDE",
    "PLANO DE SAÚDE",
    "PLANOS DE SAÚDE",
    "PLANOS DE SAUDE",
    "ASSISTENCIA MEDICA",
    "ASSISTÊNCIA MÉDICA",
    "ASSISTENCIA HOSPITALAR",
    "ASSISTÊNCIA HOSPITALAR",
    "ASSISTENCIA AMBULATORIAL",
    "ASSISTÊNCIA AMBULATORIAL",
    "COBERTURA MINIMA OBRIGATORIA",
    "COBERTURA MÍNIMA OBRIGATÓRIA",
    "ROL DE PROCEDIMENTOS",
    "ROL DE PROCEDIMENTOS E EVENTOS EM SAUDE",
    "ROL DE PROCEDIMENTOS E EVENTOS EM SAÚDE",
    "BENEFICIARIOS",
    "BENEFICIÁRIOS",
    "BENEFICIARIO",
    "BENEFICIÁRIO",
    "USUARIOS DO PLANO",
    "USUÁRIOS DO PLANO",
    "OPERADORA DE PLANO",
    "OPERADORA DE PLANOS",
    "PLANO COLETIVO EMPRESARIAL",
    "PLANO COLETIVO POR ADESAO",
    "PLANO COLETIVO POR ADESÃO",
    "ATENDIMENTO MÉDICO",
    "ATENDIMENTO MEDICO",
    "CONSULTAS MÉDICAS",
    "CONSULTAS MEDICAS",
    "ASSISTENCIA PSIQUIATRICA",
    "ASSISTÊNCIA PSIQUIÁTRICA",
    "ASSISTENCIA OBSTETRICA",
    "ASSISTÊNCIA OBSTÉTRICA",
    "SERVIÇOS DE ASSISTÊNCIA MÉDICA",
    "SERVICOS DE ASSISTENCIA MEDICA",

    # viagens / passagens (NOVO)
    "AGENCIA DE VIAGENS",
    "AGÊNCIA DE VIAGENS",
    "AGENCIA DE VIAGEM",
    "AGÊNCIA DE VIAGEM",
    "AGENCIAMENTO DE VIAGENS",
    "AGENCIAMENTO DE VIAGEM",
    "OPERADORA DE VIAGENS",
    "OPERADORA DE TURISMO",
    "AGENCIA DE TURISMO",
    "AGÊNCIA DE TURISMO",
    "PASSAGEM AEREA",
    "PASSAGEM AÉREA",
    "PASSAGENS AEREAS",
    "PASSAGENS AÉREAS",
    "PASSAGEM AEREA NACIONAL",
    "PASSAGEM AÉREA NACIONAL",
    "PASSAGENS AEREAS NACIONAIS",
    "PASSAGENS AÉREAS NACIONAIS",
    "PASSAGEM AEREA INTERNACIONAL",
    "PASSAGEM AÉREA INTERNACIONAL",
    "PASSAGENS AEREAS INTERNACIONAIS",
    "PASSAGENS AÉREAS INTERNACIONAIS",
    "RESERVA DE PASSAGEM",
    "RESERVA DE PASSAGENS",
    "EMISSAO DE PASSAGEM",
    "EMISSÃO DE PASSAGEM",
    "EMISSAO DE PASSAGENS",
    "EMISSÃO DE PASSAGENS",
    "REMARCACAO DE PASSAGEM",
    "REMARCAÇÃO DE PASSAGEM",
    "REMARCACAO DE PASSAGENS",
    "REMARCAÇÃO DE PASSAGENS",
]

# 6 = Pregão Eletrônico, 8 = Dispensa de Licitação, 9 = Inexigibilidade
MODALIDADES = [6, 8, 9]

# Faixas em DIAS (contando a partir de hoje) sobre a data de encerramento das propostas
FAIXAS = [
    ("0-7", 0, 7),
    ("8-14", 8, 14),
    ("15-28", 15, 28),
]

BASE_URL = "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"


def formatar_data(data_iso):
    """Converte '2025-11-25T10:00:00-03:00' para '25/11/2025'."""
    if not data_iso:
        return "??/??/????"
    try:
        dia = data_iso[:10]  # "2025-11-25"
        dt = datetime.strptime(dia, "%Y-%m-%d")
        return dt.strftime("%d/%m/%Y")
    except Exception:
        return "Data Inválida"


def calcular_dias(data_iso):
    """
    Retorna número de dias entre HOJE e a data (só a parte AAAA-MM-DD).
    Futuro = dias >= 0 | Passado = dias < 0.
    """
    if not data_iso:
        return -999
    try:
        dia = data_iso[:10]
        dt = datetime.strptime(dia, "%Y-%m-%d").date()
        hoje = date.today()
        return (dt - hoje).days
    except Exception:
        return -999


def classificar_faixa(dias):
    """Retorna a chave da faixa (0-7, 8-14, 15-28) ou None."""
    for chave, minimo, maximo in FAIXAS:
        if minimo <= dias <= maximo:
            return chave
    return None


def montar_intervalo_publicacao():
    """
    Janela de publicação no PNCP: últimos 30 dias.
    Ajuste se quiser outro intervalo.
    """
    hoje = date.today()
    data_final = hoje
    data_inicial = hoje - timedelta(days=30)
    return data_inicial.strftime("%Y%m%d"), data_final.strftime("%Y%m%d")


def busca_pncp():
    print("🕵️ ROBÔ MEDCAL - DIAGNÓSTICO FINAL")
    print(f"🎯 Estados: {ESTADOS_ALVO}")
    print("📅 Buscando editais COM PUBLICAÇÃO nos últimos 30 dias")
    print("   e encerramento de propostas FUTURO dentro de 0 a 28 dias.")
    print("-" * 60)

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    data_inicial, data_final = montar_intervalo_publicacao()

    contagem_faixas = {chave: 0 for chave, _, _ in FAIXAS}
    total_geral = 0

    # Contadores de debug
    total_itens_api = 0
    total_com_termo_positivo = 0
    total_descartado_negativo = 0
    total_com_data_valida = 0

    for uf in ESTADOS_ALVO:
        print(f"\n🌍 ESTADO: {uf}")

        for modalidade in MODALIDADES:
            pagina = 1
            params = {
                "dataInicial": data_inicial,
                "dataFinal": data_final,
                "codigoModalidadeContratacao": modalidade,
                "uf": uf,
                "pagina": pagina,
                "tamanhoPagina": 50,
            }

            try:
                resp = requests.get(BASE_URL, params=params, headers=headers, timeout=20)

                if resp.status_code != 200:
                    print(
                        f"   ❌ Erro API (UF={uf}, mod={modalidade}, pág={pagina}): "
                        f"{resp.status_code} {resp.text[:120]}"
                    )
                    continue

                dados = resp.json()
                itens = dados.get("data", [])

                print(
                    f"   🔎 UF={uf}, modalidade={modalidade}: "
                    f"API retornou {len(itens)} itens (página {pagina})..."
                )

                if not itens:
                    continue

                for item in itens:
                    total_itens_api += 1

                    # 1) Campo do objeto na API de CONSULTA é "objetoCompra"
                    objeto_raw = item.get("objetoCompra") or ""
                    objeto = objeto_raw.upper()
                    if not objeto:
                        continue

                    # 2) Filtrar pelos TERMOS POSITIVOS (segmento de saúde/bens)
                    if not any(termo in objeto for termo in TERMOS_POSITIVOS):
                        continue
                    total_com_termo_positivo += 1

                    # 3) Excluir os TERMOS NEGATIVOS (planos, assistência médica, viagens etc.)
                    if any(termo in objeto for termo in TERMOS_NEGATIVOS):
                        total_descartado_negativo += 1
                        continue

                    # 4) Data que vamos usar para a faixa é o ENCERRAMENTO DAS PROPOSTAS
                    data_encerramento_raw = item.get("dataEncerramentoProposta")
                    dias = calcular_dias(data_encerramento_raw)

                    if dias == -999:
                        continue
                    total_com_data_valida += 1

                    faixa_key = classificar_faixa(dias)
                    if faixa_key is None:
                        # fora das faixas 0–28
                        continue

                    total_geral += 1
                    contagem_faixas[faixa_key] += 1

                    # Cor de urgência no terminal
                    if dias <= 7:
                        cor = "\033[91m"  # vermelho
                    elif dias <= 14:
                        cor = "\033[93m"  # amarelo
                    else:
                        cor = "\033[92m"  # verde

                    orgao = (item.get("orgaoEntidade") or {})
                    razao_orgao = (
                        orgao.get("razaoSocial")
                        or orgao.get("razaosocial")
                        or "Órgão não informado"
                    )

                    # Alguns retornos podem variar o nome do campo de CNPJ
                    cnpj_orgao = (
                        orgao.get("cnpj")
                        or orgao.get("cnpjComprador")
                        or orgao.get("cnpjcomprador")
                    )
                    ano_compra = item.get("anoCompra")
                    sequencial_compra = item.get("sequencialCompra")

                    if cnpj_orgao and ano_compra is not None and sequencial_compra is not None:
                        link = f"https://pncp.gov.br/app/editais/{cnpj_orgao}/{ano_compra}/{sequencial_compra}"
                    else:
                        link = "(não foi possível montar o link do PNCP)"

                    print(f"\n   {cor}✅ ACHAMOS! ({uf} / mod={modalidade})\033[0m")
                    print(
                        f"      📅 Encerramento propostas: "
                        f"{formatar_data(data_encerramento_raw)} (daqui a {dias} dias)"
                    )
                    print(
                        f"      📣 Publicado no PNCP em: "
                        f"{formatar_data(item.get('dataPublicacaoPncp'))}"
                    )
                    print(f"      🏛️  {razao_orgao}")
                    print(f"      📄 {objeto_raw}")
                    print(f"      🔗 {link}")
                    print("-" * 40)

                time.sleep(0.5)

            except Exception as e:
                print(f"   ❌ Erro ao consultar UF={uf}, modalidade={modalidade}: {e}")

    print("\n" + "=" * 60)
    print("🏁 RESUMO POR FAIXAS DE DIAS\n")

    for chave, _, _ in FAIXAS:
        print(f"🗓️  Faixa {chave} dias -> {contagem_faixas[chave]} itens encontrados")

    print(f"\n✅ Total geral encontrado (todas as faixas): {total_geral}")

    # Debug geral pra entender filtros
    print("\n📊 ESTATÍSTICAS DE FILTRO:")
    print(f"   - Total retornado pela API (todas as chamadas): {total_itens_api}")
    print(f"   - Com algum TERMO POSITIVO: {total_com_termo_positivo}")
    print(f"   - Descartados por TERMO NEGATIVO: {total_descartado_negativo}")
    print(f"   - Com dataEncerramentoProposta válida: {total_com_data_valida}")
    print(f"   - Dentro das faixas 0–28 dias e filtros: {total_geral}")

    if total_geral == 0:
        print("\n🔍 DIAGNÓSTICO INICIAL:")
        print(" - Os filtros estão específicos para o perfil da Medcal (bens/equipamentos/insumos de saúde).")
        print(" - Se achar que está muito restritivo, você pode:")
        print("     • Adicionar nomes de linhas/produtos em TERMOS_POSITIVOS;")
        print("     • Remover algum termo em TERMOS_NEGATIVOS se cortar coisa boa;")
        print("     • Ampliar as faixas de dias, se necessário.")


if __name__ == "__main__":
    busca_pncp()
