import requests
from datetime import datetime, timedelta

def debug_search():
    url = "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"
    
    # Configuração igual ao Dashboard
    dias_busca = 60
    hoje = datetime.now()
    data_inicial = (hoje - timedelta(days=dias_busca)).strftime('%Y%m%d')
    data_final = (hoje + timedelta(days=1)).strftime('%Y%m%d')
    
    estados = ['RN', 'PB', 'PE', 'AL']
    modalidades = [6, 8] # Pregão, Dispensa
    
    print(f"🔍 Testando API PNCP")
    print(f"📅 Período: {data_inicial} a {data_final}")
    
    total_encontrado = 0
    
    for uf in estados:
        for mod in modalidades:
            params = {
                "dataInicial": data_inicial,
                "dataFinal": data_final,
                "codigoModalidadeContratacao": mod,
                "uf": uf,
                "pagina": "1",
                "tamanhoPagina": "10"
            }
            
            try:
                print(f"   > Buscando {uf} (Mod: {mod})...", end="")
                resp = requests.get(url, params=params, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    count = len(data.get('data', []))
                    total_registros = data.get('totalRegistros', '?')
                    print(f" OK! Retornou {count} itens (Total na API: {total_registros})")
                    total_encontrado += count
                    
                    # Imprimir o primeiro item para conferir datas
                    if count > 0:
                        first = data.get('data')[0]
                        print(f"     [Exemplo] Data Publicação: {first.get('dataPublicacaoPncp')} | Inicio Proposta: {first.get('dataInicioRecebimentoProposta')}")
                else:
                    print(f" ERRO {resp.status_code}: {resp.text}")
            except Exception as e:
                print(f" EXCEPTION: {e}")

    print(f"\n📊 Total de itens brutos encontrados no teste: {total_encontrado}")

if __name__ == "__main__":
    debug_search()
