import requests
from pncp_client import PNCPClient
from datetime import datetime, timedelta

def debug_rejections():
    client = PNCPClient()
    
    # Configuração de busca igual ao dashboard
    estados = ['RN', 'PB', 'PE', 'AL']
    modalidade = 6 # Pregão
    
    # Termos
    termos_negativos = client.TERMOS_NEGATIVOS_PADRAO + client.TERMOS_EVENTOS_NEGATIVOS
    termos_negativos_upper = list(dict.fromkeys(t.upper() for t in termos_negativos))
    
    termos_positivos = client.TERMOS_POSITIVOS_PADRAO
    termos_positivos_upper = list(dict.fromkeys(t.upper() for t in termos_positivos))
    
    termos_prioritarios = client.TERMOS_PRIORITARIOS
    termos_prioritarios_upper = [t.upper() for t in termos_prioritarios]

    print(f"🔍 DEBUGGING REJEIÇÕES (Amostra de 1 página por estado)")
    print(f"Termos Positivos: {len(termos_positivos_upper)}")
    print(f"Termos Negativos: {len(termos_negativos_upper)}")
    
    hoje = datetime.now()
    data_inicial = (hoje - timedelta(days=15)).strftime('%Y%m%d')
    data_final = hoje.strftime('%Y%m%d')
    
    stats = {
        "total": 0,
        "rejected_negative": 0,
        "rejected_no_positive": 0,
        "rejected_date": 0,
        "accepted": 0
    }

    for uf in estados:
        print(f"\n📍 Analisando {uf}...")
        params = {
            "dataInicial": data_inicial,
            "dataFinal": data_final,
            "codigoModalidadeContratacao": modalidade,
            "uf": uf,
            "pagina": "1",
            "tamanhoPagina": "20"
        }
        
        try:
            resp = requests.get(client.BASE_URL, params=params, headers=client.headers, timeout=10)
            data = resp.json().get('data', [])
            
            for item in data:
                stats["total"] += 1
                obj = (item.get('objetoCompra') or item.get('objeto') or "").upper()
                
                # 1. Check Negativos
                neg_match = next((t for t in termos_negativos_upper if t in obj), None)
                if neg_match:
                    print(f"❌ [NEGATIVO] '{neg_match}': {obj[:100]}...")
                    stats["rejected_negative"] += 1
                    continue
                    
                # 2. Check Positivos/Prioritários
                tem_prio = any(t in obj for t in termos_prioritarios_upper)
                tem_pos = any(t in obj for t in termos_positivos_upper)
                
                if not tem_prio and not tem_pos:
                    print(f"⚠️ [SEM MATCH POSITIVO]: {obj[:100]}...")
                    stats["rejected_no_positive"] += 1
                    continue
                    
                # 3. Check Data
                data_enc = item.get("dataEncerramentoProposta")
                if not data_enc:
                    print(f"📅 [SEM DATA]: {obj[:100]}...")
                    stats["rejected_date"] += 1
                    continue
                    
                dias = client.calcular_dias(data_enc)
                if dias < 0:
                    print(f"📅 [DATA PASSADA ({dias}d)]: {obj[:100]}...")
                    stats["rejected_date"] += 1
                    continue
                    
                print(f"✅ [ACEITO]: {obj[:100]}...")
                stats["accepted"] += 1
                
        except Exception as e:
            print(f"Erro ao buscar {uf}: {e}")

    print("\n📊 ESTATÍSTICAS FINAIS")
    print(stats)

if __name__ == "__main__":
    debug_rejections()
