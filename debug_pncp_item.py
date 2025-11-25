import requests
import json

cnpj = "08308470000129"
ano = "2025"
seq = "24"

# Using the Search API as in pncp_client.py
url = "https://pncp.gov.br/api/search/v1/compras"

params = {
    "cnpjOrgao": cnpj,
    "ano": ano,
    "sequencialCompra": seq,
    "pagina": "1",
    "tamanhoPagina": "10"
}

print(f"Searching: {url} with params {params}")
try:
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()
    
    print(json.dumps(data, indent=2, ensure_ascii=False))
    
    items = data.get('data', [])
    if items:
        item = items[0]
        print("\n--- FOUND ITEM ---")
        print(f"Modalidade: {item.get('modalidadeId')} ({item.get('modalidadeNome')})")
        print(f"Data Início Proposta: {item.get('dataInicioProposta')}")
        print(f"Data Encerramento Proposta: {item.get('dataEncerramentoProposta')}")
        print(f"Objeto: {item.get('objeto')}")
        print(f"Status: {item.get('statusCompraId')} ({item.get('statusCompraNome')})")
    else:
        print("\n--- ITEM NOT FOUND IN SEARCH ---")
    
except Exception as e:
    print(f"Error: {e}")
