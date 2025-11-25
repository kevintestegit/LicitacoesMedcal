from pncp_client import PNCPClient

client = PNCPClient()

test_cases = [
    "AQUISIÇÃO DE COMPUTADORES,NOTEBOOK E WEBCAM PARA ATENDER A DEMANDA DESTA UNIDADE HOSPITALAR",
    "Contratação de empresa para realização de intercâmbio educacional e cultural para os estudantes da rede estadual de ensino da paraíba",
    "Registro de Preços para futura e eventual Aquisição de água mineral potável, acondicionada em garrafas de 500 ml e copos de 200 ml",
    "LOCAÇÃO DE EQUIPAMENTOS DE HEMATOLOGIA E BIOQUIMICA", # Should pass
    "AQUISIÇÃO DE REAGENTES LABORATORIAIS" # Should pass
]

print("Testing Filters...")
termos_negativos = client.TERMOS_NEGATIVOS_PADRAO
termos_negativos_upper = [t.upper() for t in termos_negativos]

for title in test_cases:
    obj = title.upper()
    blocked = False
    for t in termos_negativos_upper:
        if t in obj:
            print(f"❌ BLOCKED: '{title}' (Matched: '{t}')")
            blocked = True
            break
    
    if not blocked:
        print(f"✅ PASSED: '{title}'")
