def debug_filter():
    # Texto do objeto (copiado da reclamação do usuário)
    objeto_real = "Contratação de empresa especializada na prestação de serviços contínuos de limpeza e desinfecção/descontaminação de superfícies, com a disponibilização de mão de obra qualificada, produtos saneantes, materiais e equipamentos, para as áreas internas e externas, além de superfícies internas de ambulâncias próprias do HUAC - UFCG, filial Ebserh, conforme condições, quantidades e exigências estabelecidas neste termo de referência, por um período de 24 (vinte e quatro) meses."
    
    # Termo negativo (copiado da reclamação do usuário)
    termo_negativo = "Serviços contínuos de limpeza e desinfecção"
    
    print(f"--- Teste de Filtro Negativo ---")
    
    # Simulação da Lógica do pncp_client.py
    obj_upper = objeto_real.upper()
    termo_upper = termo_negativo.upper()
    
    print(f"Objeto (Upper): '{obj_upper}'")
    print(f"Termo (Upper):  '{termo_upper}'")
    
    match = termo_upper in obj_upper
    
    print(f"\nResultado do Match (in): {match}")
    
    if not match:
        print("\n⚠️ O match falhou! Investigando detalhes...")
        # Verificar se é problema de acentuação
        import unicodedata
        def remover_acentos(txt):
            return ''.join(c for c in unicodedata.normalize('NFD', txt) if unicodedata.category(c) != 'Mn')
            
        obj_norm = remover_acentos(obj_upper)
        termo_norm = remover_acentos(termo_upper)
        
        print(f"Objeto (Norm): '{obj_norm}'")
        print(f"Termo (Norm):  '{termo_norm}'")
        
        match_norm = termo_norm in obj_norm
        print(f"Resultado do Match (Normalizado): {match_norm}")

if __name__ == "__main__":
    debug_filter()
