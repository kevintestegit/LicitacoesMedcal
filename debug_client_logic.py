from pncp_client import PNCPClient
import json

def test_logic():
    print("🕵️ Testando lógica do PNCPClient isoladamente...")
    
    client = PNCPClient()
    
    # 1. Verificar se os termos estão carregados
    termos = client.TERMOS_NEGATIVOS_PADRAO
    print(f"📋 Total de termos negativos: {len(termos)}")
    
    termo_chave = "serviços contínuos de limpeza e desinfecção"
    tem_termo = any(t.lower() == termo_chave.lower() for t in termos)
    print(f"🧐 Termo '{termo_chave}' está na lista? {'✅ SIM' if tem_termo else '❌ NÃO'}")
    
    # 2. Simular um objeto que DEVERIA ser filtrado
    objeto_teste = "Contratação de empresa especializada na prestação de serviços contínuos de limpeza e desinfecção/descontaminação de superfícies..."
    
    print(f"\n🧪 Testando filtro com objeto fake:")
    print(f"   Objeto: {objeto_teste}")
    
    # Copiando a lógica exata do buscar_oportunidades
    obj = objeto_teste.upper()
    termos_negativos_upper = [t.upper() for t in termos]
    
    matches = [t for t in termos_negativos_upper if t in obj]
    print(f"   Matches encontrados (Lógica Manual): {matches}")
    
    if matches:
        print("   ✅ Lógica Manual: FILTRARIA.")
    else:
        print("   ❌ Lógica Manual: NÃO FILTRARIA.")

    # 3. Teste Real (Busca na API)
    print("\n🌍 Testando busca real na API (pode demorar um pouco)...")
    # Vamos buscar em PE/PB onde esse item costuma aparecer, modalidade 6 ou 8
    # Precisamos garantir que a busca pegue esse item. Se ele for antigo, talvez precise de mais dias.
    # O user disse que "apareceu aqui", então deve ser recente ou a busca está pegando dias para trás.
    
    resultados = client.buscar_oportunidades(dias_busca=30, estados=['PB', 'RN', 'PE'])
    
    # Verificar se o item proibido apareceu nos resultados
    encontrou_proibido = False
    for res in resultados:
        if "LIMPEZA E DESINFECÇÃO" in res['objeto'].upper():
            encontrou_proibido = True
            print(f"❌ FALHA: Item proibido encontrado nos resultados!")
            print(f"   Objeto: {res['objeto']}")
            break
            
    if not encontrou_proibido:
        print("✅ SUCESSO: Nenhum item com 'LIMPEZA E DESINFECÇÃO' foi retornado na busca real.")

if __name__ == "__main__":
    test_logic()
