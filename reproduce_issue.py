import sys
import os
from datetime import datetime

# Adiciona o diretório atual ao path para importar os módulos
sys.path.append(os.getcwd())

from modules.scrapers.pncp_client import PNCPClient

def test_search():
    client = PNCPClient()
    
    print("=== INICIANDO DIAGNÓSTICO DE BUSCA ===")
    
    # 1. Busca AMPLA (sem filtro de data de encerramento, últimos 30 dias de publicação)
    # Estados padrão do dashboard: RN, PB, PE, AL
    estados = ['RN', 'PB', 'PE', 'AL']
    print(f"Estados: {estados}")
    
    # Vamos monkey-patch (sobrescrever) o método avaliar_objeto para logar rejeições
    original_avaliar = client.avaliar_objeto
    
    def debug_avaliar_objeto(obj_upper, termos_positivos, termos_prioritarios):
        aprovado, motivo, termos = original_avaliar(obj_upper, termos_positivos, termos_prioritarios)
        if not aprovado:
            # Logar apenas se parecer algo relevante (ex: tem 'LABORATORIO' mas foi rejeitado)
            if "LABORATORIO" in obj_upper or "HOSPITALAR" in obj_upper or "REAGENTE" in obj_upper:
                print(f"[REJEITADO - POSITIVO] Motivo: {motivo} | Obj: {obj_upper[:100]}...")
        return aprovado, motivo, termos

    client.avaliar_objeto = debug_avaliar_objeto
    
    # Vamos interceptar também o filtro negativo dentro de buscar_modalidade_uf
    # Como é difícil interceptar dentro da função, vamos fazer uma busca manual simulada
    # chamando a API diretamente para um teste controlado.
    
    print("\n--- Teste 1: Buscar TUDO (Abertas e Fechadas) nos últimos 15 dias ---")
    resultados = client.buscar_oportunidades(dias_busca=15, estados=estados, apenas_abertas=False)
    
    print(f"\nTotal encontrado (Abertas + Fechadas): {len(resultados)}")
    
    if len(resultados) > 0:
        print("\nExemplos encontrados:")
        for res in resultados[:5]:
            print(f"- [{res['data_publicacao']}] {res['orgao']} | {res['objeto'][:80]}...")
            
    # Verifica rejeições por termos negativos (Simulação)
    # Pegamos alguns termos que suspeitamos estarem bloqueando
    termos_teste = [
        "AQUISIÇÃO DE EQUIPAMENTOS PARA O LABORATORIO MUNICIPAL E MATERIAIS DE CONSTRUCAO",
        "CONTRATACAO DE SERVICOS DE MANUTENCAO DE EQUIPAMENTOS LABORATORIAIS",
        "AQUISICAO DE MEDICAMENTOS E INSUMOS LABORATORIAIS",
        "REGISTRO DE PRECOS PARA AQUISICAO DE MATERIAL MEDICO HOSPITALAR E ODONTOLOGICO"
    ]
    
    print("\n--- Teste 2: Simulação de Filtros Negativos ---")
    termos_negativos = client.TERMOS_NEGATIVOS_PADRAO
    
    for texto in termos_teste:
        texto_upper = texto.upper()
        bloqueado = False
        termo_bloqueio = ""
        
        for t in termos_negativos:
            if t.upper() in texto_upper:
                bloqueado = True
                termo_bloqueio = t
                break
        
        status = "BLOQUEADO" if bloqueado else "APROVADO"
        print(f"Texto: {texto}")
        print(f"Status: {status} " + (f"(Por: '{termo_bloqueio}')" if bloqueado else ""))
        print("-" * 30)

if __name__ == "__main__":
    test_search()
