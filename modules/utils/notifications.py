import requests
import urllib.parse

class WhatsAppNotifier:
    def __init__(self, phone_number, api_key):
        """
        Inicializa o notificador WhatsApp usando CallMeBot (Free API).
        Para pegar a API Key: Adicione o número +34 644 56 55 18 nos contatos,
        e envie a mensagem "I allow callmebot to send me messages".
        """
        self.phone_number = phone_number
        self.api_key = api_key
        self.base_url = "https://api.callmebot.com/whatsapp.php"

    def enviar_mensagem(self, mensagem):
        if not self.phone_number or not self.api_key:
            print("⚠️ Configurações de WhatsApp não encontradas.")
            return False

        try:
            # Codifica a mensagem para URL
            texto_encoded = urllib.parse.quote(mensagem)
            url = f"{self.base_url}?phone={self.phone_number}&text={texto_encoded}&apikey={self.api_key}"
            
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                return True
            else:
                print(f"Erro ao enviar WhatsApp: {response.text}")
                return False
        except Exception as e:
            print(f"Erro de conexão ao enviar WhatsApp: {e}")
            return False
