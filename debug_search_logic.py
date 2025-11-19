from pncp_client import PNCPClient
from datetime import datetime
import pandas as pd

def debug_search():
    print("🕵️ Validando resultados da busca (Simulação Dashboard)...")
    
    client = PNCPClient()
    
    # Parâmetros IGUAIS ao Dashboard
    dias = 15
    estados = ['RN', 'PB', 'PE', 'AL']
    termos = client.TERMOS_POSITIVOS_PADRAO # Simulando busca com termos padrão
    
    print(f"🌍 Buscando últimos {dias} dias em {estados}...")
    print(f"   Filtro de Termos: {len(termos)} termos padrão")
    
    # Busca com termos (como no dashboard sem varredura total)
    resultados_raw = client.buscar_oportunidades(dias, estados, termos_positivos=termos)
    
    total_api = len(resultados_raw)
    print(f"📊 Total retornado pela API (antes do filtro de data): {total_api}")
    
    hoje_date = datetime.now().date()
    
    resultados_finais = []
    ignorados_data = 0
    
    print("\n🔍 Analisando amostra dos resultados:")
    
    for i, res in enumerate(resultados_raw):
        inicio_str = res.get('data_inicio_proposta')
        fim_str = res.get('data_encerramento_proposta')
        objeto = res.get('objeto', '')[:60]
        
        should_exclude = False
        reason = ""
        
        # Lógica do Dashboard (Filtro Futuro)
        if inicio_str:
            try:
                inicio_dt = datetime.fromisoformat(inicio_str).date()
                if inicio_dt < hoje_date:
                    should_exclude = True
                    reason = f"Início {inicio_dt} < Hoje (JÁ COMEÇOU)"
                else:
                    reason = f"Início {inicio_dt} >= Hoje (FUTURO/HOJE)"
            except:
                pass 
        else:
            if fim_str:
                try:
                    fim_dt = datetime.fromisoformat(fim_str).date()
                    if fim_dt < hoje_date:
                        should_exclude = True
                        reason = f"Fim {fim_dt} < Hoje (VENCEU)"
                    else:
                        reason = f"Fim {fim_dt} >= Hoje (ABERTO)"
                except:
                    pass

        if not should_exclude:
            resultados_finais.append(res)
            if len(resultados_finais) <= 10:
                print(f"✅ MANTIDO | {reason} | {objeto}...")
        else:
            ignorados_data += 1
            # print(f"❌ EXCLUÍDO | {reason} | {objeto}...")

    print(f"\n📉 Resumo Final:")
    print(f"   Total API: {total_api}")
    print(f"   Excluídos (Passado): {ignorados_data}")
    print(f"   Mantidos (Válidos): {len(resultados_finais)}")

if __name__ == "__main__":
    debug_search()
