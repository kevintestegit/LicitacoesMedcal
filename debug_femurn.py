import requests
from bs4 import BeautifulSoup
from datetime import datetime

def test_femurn():
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    # 1. Get Search Page
    url_search = "https://www.diariomunicipal.com.br/femurn/pesquisar"
    print(f"Accessing {url_search}...")
    resp = session.get(url_search, headers=headers, verify=False)
    
    if resp.status_code != 200:
        print(f"Failed to access page: {resp.status_code}")
        return

    soup = BeautifulSoup(resp.content, 'html.parser')
    token_input = soup.find('input', {'name': 'busca_avancada[_token]'})
    
    if not token_input:
        print("Token not found!")
        return
        
    token = token_input['value']
    print(f"Token found: {token}")
    
    # 2. Perform Search
    # Search for "PREGÃO" today
    today = datetime.now().strftime("%d/%m/%Y")
    
    payload = {
        "busca_avancada[entidadeUsuaria]": "",
        "busca_avancada[nome_orgao]": "",
        "busca_avancada[titulo]": "",
        "busca_avancada[texto]": "PREGÃO",
        "busca_avancada[dataInicio]": today,
        "busca_avancada[dataFim]": today,
        "busca_avancada[_token]": token,
        "busca_avancada[Enviar]": "" # Button
    }
    
    print("Sending POST request...")
    # The form action is /femurn/pesquisar (same URL, POST method usually, or check action)
    # The HTML said action="/femurn/pesquisar/identificador" ?? No, wait.
    # <form name="identifier" method="post" action="/femurn/pesquisar/identificador" ...>
    # <form ... action="/femurn/materia/calendario" ...>
    # Wait, I need to check the action of the MAIN search form.
    # The grep output showed:
    # <button type="submit" ... formnovalidate="true" ...>Pesquisar</button>
    # But I missed the <form> tag for the main search in the grep output because it might have been before the inputs.
    
    # Let's assume it posts to /femurn/pesquisar based on standard behavior, or I'll check the soup.
    form = soup.find('button', {'id': 'busca_avancada_Enviar'}).find_parent('form')
    if form:
        action = form.get('action')
        print(f"Form action: {action}")
        if action:
            post_url = f"https://www.diariomunicipal.com.br{action}"
        else:
            post_url = url_search
    else:
        print("Form not found, trying default /femurn/pesquisar")
        post_url = url_search

    resp_post = session.post(post_url, data=payload, headers=headers, verify=False)
    
    print(f"POST Status: {resp_post.status_code}")
    print(f"Response length: {len(resp_post.content)}")
    
    if "g-recaptcha-response" in resp_post.text or "recaptcha" in resp_post.text.lower():
        print("Recaptcha detected in response!")
    
    # Check if results exist
    if "Nenhum resultado encontrado" in resp_post.text:
        print("No results found.")
    else:
        print("Results might be present.")
        # Save to file to inspect
        with open("debug_femurn_result.html", "w") as f:
            f.write(resp_post.text)

if __name__ == "__main__":
    test_femurn()
