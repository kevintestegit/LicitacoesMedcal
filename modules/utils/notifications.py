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
        self.ultimo_erro = None  # Armazena a última mensagem de erro

    def enviar_mensagem(self, mensagem):
        self.ultimo_erro = None  # Limpa erro anterior

        if not self.phone_number or not self.api_key:
            self.ultimo_erro = "⚠️ Telefone ou API Key não configurados. Vá em Configurações → WhatsApp."
            print(self.ultimo_erro)
            return False

        try:
            # Remove o "+" do telefone se existir (CallMeBot não aceita + na URL)
            phone_clean = str(self.phone_number).replace('+', '').strip()

            # Codifica a mensagem para URL
            texto_encoded = urllib.parse.quote(mensagem)
            url = f"{self.base_url}?phone={phone_clean}&text={texto_encoded}&apikey={self.api_key}"

            response = requests.get(url, timeout=10)

            # Debug: log da resposta completa
            print(f"[WhatsApp] Status: {response.status_code}, Resposta: {response.text[:200]}")

            # CallMeBot retorna 200 mas pode ter erro no corpo da resposta
            response_text = response.text.lower()
            
            if response.status_code == 200 and "message queued" in response_text:
                return True
            elif response.status_code == 200 and ("error" in response_text or "invalid" in response_text):
                self.ultimo_erro = f"❌ API CallMeBot: {response.text[:200]}"
                print(self.ultimo_erro)
                return False
            elif response.status_code == 200:
                # Assume sucesso se status 200 e não tem erro explícito
                return True
            else:
                self.ultimo_erro = f"❌ API CallMeBot retornou erro: {response.status_code} - {response.text[:100]}"
                print(self.ultimo_erro)
                return False
        except requests.exceptions.Timeout:
            self.ultimo_erro = "⏱️ Timeout: A API do CallMeBot não respondeu a tempo. Tente novamente."
            print(self.ultimo_erro)
            return False
        except requests.exceptions.ConnectionError:
            self.ultimo_erro = "🌐 Erro de conexão: Verifique sua internet ou se o CallMeBot está funcionando."
            print(self.ultimo_erro)
            return False
        except Exception as e:
            self.ultimo_erro = f"❌ Erro inesperado: {str(e)}"
            print(self.ultimo_erro)
            return False
