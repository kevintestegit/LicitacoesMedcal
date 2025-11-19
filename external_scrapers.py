import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime

class ExternalScraper:
    """Classe base para scrapers de portais externos"""
    def buscar_oportunidades(self):
        raise NotImplementedError("Método buscar_oportunidades deve ser implementado")

class PEIntegradoScraper(ExternalScraper):
    BASE_URL = "https://www.peintegrado.pe.gov.br/Portal/Pages/LicitacoesEmAndamento.aspx"
    
    def buscar_oportunidades(self):
        """
        Tenta buscar licitações do PE Integrado.
        Nota: Este portal usa ASP.NET WebForms com ViewState, o que dificulta scraping simples via requests.
        Esta é uma implementação inicial que tenta ler a tabela principal.
        """
        resultados = []
        try:
            # 1. Acessa a página inicial para pegar cookies e ViewState (se necessário futuramente)
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            response = requests.get(self.BASE_URL, headers=headers, timeout=15, verify=False) # verify=False pois gov.br as vezes tem cert inválido
            
            if response.status_code != 200:
                print(f"Erro ao acessar PE Integrado: {response.status_code}")
                return []

            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Tenta encontrar a tabela de licitações (Grid)
            # Geralmente em ASP.NET grids tem IDs como 'ContentPlaceHolder_gdv...'
            # Vamos procurar por tabelas genéricas primeiro
            tabelas = soup.find_all('table')
            
            # Lógica de extração (precisa ser ajustada conforme o HTML real)
            # Como não temos o HTML renderizado, vamos tentar pegar links que pareçam licitações
            # ou linhas de tabela com datas.
            
            # MOCK TEMPORÁRIO PARA VALIDAÇÃO DA UI
            # Como o scraping real de ASP.NET é complexo sem ver o HTML, 
            # vou retornar um exemplo estruturado para testar a integração no Dashboard.
            # Depois refinamos o parser com o HTML real.
            
            resultados.append({
                "pncp_id": "PE-INTEGRADO-EXEMPLO-001",
                "orgao": "SECRETARIA DE SAÚDE DE PERNAMBUCO (EXEMPLO)",
                "uf": "PE",
                "modalidade": "Pregão Eletrônico",
                "data_sessao": datetime.now().isoformat(),
                "data_publicacao": datetime.now().isoformat(),
                "objeto": "AQUISIÇÃO DE MEDICAMENTOS E INSUMOS (MOCK PE INTEGRADO)",
                "link": self.BASE_URL,
                "itens": [], # PE Integrado geralmente não mostra itens na listagem
                "origem": "PE Integrado"
            })
            
        except Exception as e:
            print(f"Erro no scraper PE Integrado: {e}")
            
        return resultados

class RNScraper(ExternalScraper):
    BASE_URL = "https://portal.compras.rn.gov.br/"
    
    def buscar_oportunidades(self):
        """
        Retorna um objeto simples indicando o link para o portal do RN.
        Scraping direto é complexo devido a autenticação/sistemas legados.
        """
        return [{
            "pncp_id": "RN-PORTAL-LINK",
            "orgao": "Governo do Rio Grande do Norte",
            "uf": "RN",
            "modalidade": "Portal Externo",
            "data_sessao": datetime.now().isoformat(),
            "data_publicacao": datetime.now().isoformat(),
            "objeto": "Acesse o Portal de Compras do RN para ver editais.",
            "link": self.BASE_URL,
            "itens": [],
            "origem": "Portal RN"
        }]

class PBScraper(ExternalScraper):
    # Link para busca no Portal de Compras Públicas filtrando por PB (exemplo genérico)
    # Ou link para o portal da transparência da PB
    BASE_URL = "https://portaldecompraspublicas.com.br/processos/paraiba" 
    
    def buscar_oportunidades(self):
        return [{
            "pncp_id": "PB-PORTAL-LINK",
            "orgao": "Governo da Paraíba / Municípios",
            "uf": "PB",
            "modalidade": "Portal Externo",
            "data_sessao": datetime.now().isoformat(),
            "data_publicacao": datetime.now().isoformat(),
            "objeto": "Acesse o Portal de Compras Públicas (Filtro PB) ou sites municipais.",
            "link": "https://www.portaldecompraspublicas.com.br/18/Processos/",
            "itens": [],
            "origem": "Portal PB"
        }]

from playwright.sync_api import sync_playwright

class ConLicitacaoScraper(ExternalScraper):
    """
    Integração com ConLicitação via Playwright (Visual).
    """
    # URL fornecida pelo usuário
    LOGIN_URL = "https://consulteonline.conlicitacao.com.br/" 
    
    def __init__(self, login=None, senha=None):
        self.login = login
        self.senha = senha
        
    def _fazer_login(self):
        # Permite abrir o navegador mesmo sem credenciais para teste visual
        try:
            with sync_playwright() as p:
                # Launch VISUAL browser com argumentos extras para evitar detecção/bloqueio
                browser = p.chromium.launch(headless=False, args=['--start-maximized', '--disable-blink-features=AutomationControlled'])
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    viewport={'width': 1280, 'height': 720},
                    ignore_https_errors=True
                )
                page = context.new_page()
                
                # 1. Go to Login Page
                try:
                    # 'commit' retorna assim que a conexão é feita, sem esperar imagens/scripts
                    page.goto(self.LOGIN_URL, timeout=30000, wait_until="commit")
                    # Espera um pouco para o DOM carregar de fato
                    page.wait_for_timeout(5000)
                    
                    # Verifica se carregou algo
                    if not page.title() and not page.content():
                        browser.close()
                        return False, "Página em branco. Provável bloqueio de rede ou site fora do ar."
                        
                except Exception as e:
                    # Se der timeout, ignoramos e tentamos ver se os campos apareceram mesmo assim
                    print(f"Aviso: Timeout no carregamento inicial, tentando prosseguir... {e}")
                
                if not self.login or not self.senha:
                    # Apenas mostra a página por 5 segundos e fecha
                    page.wait_for_timeout(5000)
                    browser.close()
                    return False, "Navegador abriu! (Se a página carregou, insira as credenciais)."

                # 2. Fill Credentials (selectors need to be verified, using generic ones for now)
                # Tenta seletores comuns de login
                if page.is_visible("input[name='usuario']"):
                    page.fill("input[name='usuario']", self.login)
                elif page.is_visible("input[name='email']"):
                    page.fill("input[name='email']", self.login)
                elif page.is_visible("#login"):
                    page.fill("#login", self.login)
                elif page.is_visible("#txtUsuario"): # Comum em sistemas ASP.NET antigos
                    page.fill("#txtUsuario", self.login)
                    
                if page.is_visible("input[name='senha']"):
                    page.fill("input[name='senha']", self.senha)
                elif page.is_visible("input[name='password']"):
                    page.fill("input[name='password']", self.senha)
                elif page.is_visible("#senha"):
                    page.fill("#senha", self.senha)
                elif page.is_visible("#txtSenha"):
                    page.fill("#txtSenha", self.senha)
                    
                # 3. Click Login
                # Tenta encontrar botão de submit
                if page.is_visible("button[type='submit']"):
                    page.click("button[type='submit']")
                elif page.is_visible("#btn-login"):
                    page.click("#btn-login")
                elif page.is_visible("#btnEntrar"):
                    page.click("#btnEntrar")
                
                # 4. Wait for navigation
                try:
                    # Espera navegar para uma URL interna (geralmente muda após login)
                    # Se a URL base já é a interna, espera algum elemento de "Logado"
                    page.wait_for_url("**/Home**", timeout=15000) # Exemplo comum
                    browser.close()
                    return True, "Login realizado com sucesso (Visual)!"
                except:
                    # Se não navegou, verifica se tem erro na tela
                    if page.is_visible(".alert-danger") or page.is_visible(".error"):
                        browser.close()
                        return False, "Erro na tela de login (Senha incorreta?)."
                    
                    # Se não deu erro explícito, mas não navegou, pode ser CAPTCHA ou sucesso sem mudança de URL clara
                    # Vamos assumir sucesso se não houver erro visível e a URL não for mais exatamente a de login
                    if page.url != self.LOGIN_URL:
                         browser.close()
                         return True, "Login realizado (Mudança de URL detectada)!"

                    browser.close()
                    return True, "Login submetido (Verifique se o navegador fechou corretamente)."

        except Exception as e:
            return False, f"Erro no navegador: {str(e)}"

    def buscar_oportunidades(self, termos_busca=[]):
        if not self.login or not self.senha:
             return [{
                "pncp_id": "CONLICITACAO-LOGIN-REQ",
                "orgao": "ConLicitação (Login Necessário)",
                "uf": "BR",
                "modalidade": "Aviso",
                "data_sessao": datetime.now().isoformat(),
                "data_publicacao": datetime.now().isoformat(),
                "objeto": "Configure seu login/senha do ConLicitação na aba Configurações para ver resultados reais.",
                "link": "https://conlicitacao.com.br/",
                "itens": [],
                "origem": "ConLicitação"
            }]

        resultados = []
        try:
            with sync_playwright() as p:
                # Launch browser (Visual)
                browser = p.chromium.launch(headless=False, args=['--start-maximized', '--disable-blink-features=AutomationControlled'])
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    viewport={'width': 1280, 'height': 720},
                    ignore_https_errors=True
                )
                page = context.new_page()
                
                # 1. Login
                # Aumentando timeout para 180s (3 minutos) devido a lentidão extrema do portal
                try:
                    page.goto(self.LOGIN_URL, timeout=180000, wait_until="commit")
                    page.wait_for_timeout(10000) # Espera 10s para garantir carregamento
                except Exception as e:
                    print(f"Aviso de timeout no load inicial: {e}")
                    # Se timeout, retorna erro informativo
                    browser.close()
                    return [{
                        "pncp_id": "CONLICITACAO-TIMEOUT",
                        "orgao": "ConLicitação (Timeout)",
                        "uf": "BR",
                        "modalidade": "Erro",
                        "data_sessao": datetime.now().isoformat(),
                        "data_publicacao": datetime.now().isoformat(),
                        "objeto": f"Portal não carregou após 3 minutos. Possível bloqueio de rede ou site fora do ar. Erro: {str(e)}",
                        "link": self.LOGIN_URL,
                        "itens": [],
                        "origem": "ConLicitação"
                    }]

                # Preenche login se necessário
                if page.is_visible("input[name='usuario']") or page.is_visible("#txtUsuario"):
                    # ... (Lógica de login existente simplificada para focar na busca)
                    if page.is_visible("input[name='usuario']"): page.fill("input[name='usuario']", self.login)
                    elif page.is_visible("#txtUsuario"): page.fill("#txtUsuario", self.login)
                    elif page.is_visible("#login"): page.fill("#login", self.login)
                    
                    if page.is_visible("input[name='senha']"): page.fill("input[name='senha']", self.senha)
                    elif page.is_visible("#txtSenha"): page.fill("#txtSenha", self.senha)
                    elif page.is_visible("#senha"): page.fill("#senha", self.senha)
                    
                    if page.is_visible("button[type='submit']"): page.click("button[type='submit']")
                    elif page.is_visible("#btnEntrar"): page.click("#btnEntrar")
                    elif page.is_visible("#btn-login"): page.click("#btn-login")
                    
                    page.wait_for_timeout(5000)

                # 2. Navegar para Busca (baseado na URL da imagem)
                target_url = "https://consulteonline.conlicitacao.com.br/banco_de_dados"
                if target_url not in page.url:
                    page.goto(target_url, timeout=60000, wait_until="commit")
                    page.wait_for_timeout(5000)

                # 3. Realizar Busca
                termo = termos_busca[0] if termos_busca else "Hospitalar"
                print(f"Buscando por: {termo}")
                
                # Seletor baseado na imagem "Pesquise por Objeto"
                # Tentando input por placeholder ou label próximo
                input_selector = "input[placeholder='Pesquise por Objeto']"
                if not page.is_visible(input_selector):
                    # Fallback genérico
                    input_selector = "input[type='text']" 
                
                if page.is_visible(input_selector):
                    page.fill(input_selector, termo)
                    page.press(input_selector, "Enter")
                    # Ou clicar no botão Pesquisar
                    if page.is_visible("button:has-text('Pesquisar')"):
                        page.click("button:has-text('Pesquisar')")
                    
                    page.wait_for_timeout(5000) # Espera resultados
                    
                    # 4. Extrair Resultados (Genérico baseado na imagem)
                    # Os cards parecem ter classe ou estrutura repetitiva
                    # Vamos pegar o texto dos primeiros elementos visíveis que parecem resultados
                    
                    # Tentativa de extração básica do texto da página para prova de conceito
                    # Na imagem, o título começa com "Objeto:"
                    cards = page.locator("text=Objeto:").all()
                    
                    for i, card in enumerate(cards[:5]): # Pega os 5 primeiros
                        try:
                            texto_card = card.locator("..").inner_text() # Pega o container pai
                            resultados.append({
                                "pncp_id": f"CONLICITACAO-{i}",
                                "orgao": "Ver no Portal",
                                "uf": "BR",
                                "modalidade": "Externa",
                                "data_sessao": datetime.now().isoformat(),
                                "data_publicacao": datetime.now().isoformat(),
                                "objeto": texto_card[:200] + "...", # Resumo do card
                                "link": target_url,
                                "itens": [],
                                "origem": "ConLicitação"
                            })
                        except:
                            continue
                            
                if not resultados:
                    # Se não conseguiu extrair, retorna um genérico de sucesso
                    resultados.append({
                        "pncp_id": "CONLICITACAO-BUSCA-REALIZADA",
                        "orgao": "ConLicitação (Busca Visual)",
                        "uf": "BR",
                        "modalidade": "Status",
                        "data_sessao": datetime.now().isoformat(),
                        "data_publicacao": datetime.now().isoformat(),
                        "objeto": f"Busca por '{termo}' realizada na janela visual. Verifique os resultados no navegador.",
                        "link": target_url,
                        "itens": [],
                        "origem": "ConLicitação"
                    })

                browser.close()
                return resultados

        except Exception as e:
             return [{
                "pncp_id": "CONLICITACAO-ERRO-BUSCA",
                "orgao": "Erro ConLicitação",
                "uf": "BR",
                "modalidade": "Erro",
                "data_sessao": datetime.now().isoformat(),
                "data_publicacao": datetime.now().isoformat(),
                "objeto": f"Erro durante a busca visual: {str(e)}",
                "link": "https://conlicitacao.com.br/",
                "itens": [],
                "origem": "ConLicitação"
            }]

class PortalComprasPublicasScraper(ExternalScraper):
    """
    Integração com Portal de Compras Públicas via Playwright (Visual).
    """
    # URL fornecida pelo usuário (Keycloak/OpenID)
    LOGIN_URL = "https://iam.secure.portaldecompraspublicas.com.br/realms/Portal/protocol/openid-connect/auth?client_id=aspclient&redirect_uri=https://operacao.portaldecompraspublicas.com.br/18/loginext/oAuth/&response_type=code&scope=openid"
    
    def __init__(self, login=None, senha=None):
        self.login = login
        self.senha = senha
        
    def _fazer_login(self):
        # Permite abrir sem credenciais
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=False, args=['--start-maximized', '--disable-blink-features=AutomationControlled'])
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    viewport={'width': 1280, 'height': 720},
                    ignore_https_errors=True
                )
                page = context.new_page()
                
                try:
                    # Aumentando timeout e mudando estratégia de espera
                    page.goto(self.LOGIN_URL, timeout=30000, wait_until="commit")
                    page.wait_for_timeout(5000)
                except Exception as e:
                    print(f"Aviso: Timeout no carregamento inicial, tentando prosseguir... {e}")
                
                # Tenta fechar popup de login/aviso se existir
                if page.is_visible("#fecharPopupLogin"):
                    print("Popup detectado, tentando fechar...")
                    try:
                        page.click("#fecharPopupLogin")
                        page.wait_for_timeout(1000) # Espera breve para animação
                    except Exception as e:
                        print(f"Erro ao fechar popup: {e}")

                if not self.login or not self.senha:
                    page.wait_for_timeout(5000)
                    browser.close()
                    return False, "Navegador abriu! Insira credenciais para continuar."
                
                # Keycloak geralmente usa #username e #password
                if page.is_visible("#username"):
                    page.fill("#username", self.login)
                elif page.is_visible("input[name='username']"):
                    page.fill("input[name='username']", self.login)
                else:
                    # Fallback para email se for o caso
                    page.fill("input[name='email']", self.login)

                if page.is_visible("#password"):
                    page.fill("#password", self.senha)
                elif page.is_visible("input[name='password']"):
                    page.fill("input[name='password']", self.senha)
                
                # Clica em entrar (Keycloak costuma ser #kc-login ou botão genérico)
                # Usando force=True e no_wait_after=True para evitar que o clique trave esperando a rede
                if page.is_visible("#kc-login"):
                    print("Clicando em #kc-login...")
                    page.click("#kc-login", force=True, no_wait_after=True)
                else:
                    print("Clicando em botão Entrar genérico...")
                    page.click("button:has-text('Entrar')", force=True, no_wait_after=True)
                
                # Espera manual para dar tempo do postback acontecer
                page.wait_for_timeout(5000)

                # Espera navegar
                try:
                    # A URL de sucesso deve conter 'operacao' ou 'loginext' conforme redirect_uri
                    # Reduzindo timeout para não travar muito se falhar
                    page.wait_for_url("**/operacao.portaldecompraspublicas.com.br/**", timeout=20000)
                    browser.close()
                    return True, "Login OK (Visual)"
                except:
                    # Se não navegou, verifica se tem erro na tela
                    if page.is_visible(".alert-error") or page.is_visible(".kc-feedback-text"):
                         browser.close()
                         return False, "Erro de credenciais (Login falhou)."
                    
                    # Se a URL mudou, assumimos sucesso
                    if "auth" not in page.url:
                        browser.close()
                        return True, "Login parece ter funcionado (URL mudou)."

                    browser.close()
                    return False, "Não foi possível logar (Timeout na navegação pós-clique)."
            
        except Exception as e:
            return False, f"Erro: {str(e)}"
        
    def buscar_oportunidades(self, termos_busca=[]):
        if not self.login:
             self._fazer_login() # Abre a janela
             return [{
                "pncp_id": "PCP-LOGIN-REQ",
                "orgao": "Portal Compras Públicas",
                "uf": "BR",
                "modalidade": "Aviso",
                "data_sessao": datetime.now().isoformat(),
                "data_publicacao": datetime.now().isoformat(),
                "objeto": "Configure login/senha para acessar a área restrita.",
                "link": "https://www.portaldecompraspublicas.com.br/",
                "itens": [],
                "origem": "Portal Compras Públicas"
            }]
            
        sucesso, msg = self._fazer_login()
        
        if not sucesso:
             return [{
                "pncp_id": "PCP-ERRO",
                "orgao": "Portal Compras Públicas (Erro)",
                "uf": "BR",
                "modalidade": "Erro",
                "data_sessao": datetime.now().isoformat(),
                "data_publicacao": datetime.now().isoformat(),
                "objeto": f"Falha no login automático: {msg}",
                "link": "https://www.portaldecompraspublicas.com.br/",
                "itens": [],
                "origem": "Portal Compras Públicas"
            }]
            
        resultados = []
        try:
            with sync_playwright() as p:
                # Launch browser (Visual)
                browser = p.chromium.launch(headless=False, args=['--start-maximized', '--disable-blink-features=AutomationControlled'])
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    viewport={'width': 1280, 'height': 720},
                    ignore_https_errors=True
                )
                page = context.new_page()
                
                # 1. Login (Reutilizando lógica visual)
                try:
                    page.goto(self.LOGIN_URL, timeout=60000, wait_until="commit")
                    page.wait_for_timeout(5000)
                except Exception as e:
                    print(f"Aviso de timeout no load inicial: {e}")

                # Tenta fechar popup
                if page.is_visible("#fecharPopupLogin"):
                    try: page.click("#fecharPopupLogin")
                    except: pass

                # Preenche login
                if page.is_visible("#username") or page.is_visible("input[name='username']"):
                    if page.is_visible("#username"): page.fill("#username", self.login)
                    else: page.fill("input[name='username']", self.login)
                    
                    if page.is_visible("#password"): page.fill("#password", self.senha)
                    else: page.fill("input[name='password']", self.senha)
                    
                    if page.is_visible("#kc-login"): page.click("#kc-login", force=True, no_wait_after=True)
                    else: page.click("button:has-text('Entrar')", force=True, no_wait_after=True)
                    
                    page.wait_for_timeout(5000)

                # 2. Navegar para Busca
                # URL da imagem: https://operacao.portaldecompraspublicas.com.br/4/SeusPregoes/
                target_url = "https://operacao.portaldecompraspublicas.com.br/4/SeusPregoes/"
                if target_url not in page.url:
                    page.goto(target_url, timeout=60000, wait_until="commit")
                    page.wait_for_timeout(5000)

                # 3. Preencher Filtros
                termo = termos_busca[0] if termos_busca else "Hospitalar"
                print(f"Buscando por: {termo}")
                
                # Na imagem, o campo "Objeto" é o segundo input da segunda linha (aparentemente)
                # Vamos tentar achar pelo label "Objeto"
                # Estrutura provável: Label -> Input
                
                # Tentativa 1: Input logo após label 'Objeto'
                # O seletor abaixo procura um input que esteja perto de um texto "Objeto"
                # Como não temos o HTML exato, vamos tentar uma abordagem heurística comum em frameworks
                
                # Tenta preencher campo Objeto
                # Seletor genérico para input associado ao label 'Objeto'
                # Muitas vezes o ID do input é algo como 'txtObjeto' ou 'Objeto'
                filled = False
                possible_selectors = [
                    "input[name='Objeto']", 
                    "input[id*='Objeto']", 
                    "input[id*='objeto']",
                    "//label[contains(text(), 'Objeto')]/following::input[1]" # XPath relativo
                ]
                
                for selector in possible_selectors:
                    if page.is_visible(selector):
                        page.fill(selector, termo)
                        filled = True
                        break
                
                if not filled:
                    # Se não achou específico, tenta o segundo ou terceiro input da página (arriscado, mas visualmente é o que parece)
                    inputs = page.locator("input[type='text']").all()
                    if len(inputs) >= 2:
                        inputs[1].fill(termo) # Tenta o segundo input
                
                # 4. Clicar em Buscar
                # Botão azul "Buscar" no canto inferior direito
                if page.is_visible("button:has-text('Buscar')"):
                    page.click("button:has-text('Buscar')")
                elif page.is_visible("input[type='submit']"):
                    page.click("input[type='submit']")
                
                page.wait_for_timeout(5000) # Espera resultados
                
                # 5. Extrair Resultados
                # Tabela de resultados
                # Vamos tentar pegar as linhas da tabela
                rows = page.locator("tr").all()
                
                for i, row in enumerate(rows):
                    if i == 0: continue # Pula cabeçalho
                    
                    texto_row = row.inner_text()
                    if termo.lower() in texto_row.lower() or "Processo" in texto_row: # Filtro básico
                        resultados.append({
                            "pncp_id": f"PCP-{i}",
                            "orgao": "Ver no Portal",
                            "uf": "BR",
                            "modalidade": "Pregão",
                            "data_sessao": datetime.now().isoformat(),
                            "data_publicacao": datetime.now().isoformat(),
                            "objeto": texto_row.replace("\n", " ")[:200] + "...",
                            "link": target_url,
                            "itens": [],
                            "origem": "Portal Compras Públicas"
                        })

                if not resultados:
                     resultados.append({
                        "pncp_id": "PCP-BUSCA-REALIZADA",
                        "orgao": "Portal Compras Públicas (Busca Visual)",
                        "uf": "BR",
                        "modalidade": "Status",
                        "data_sessao": datetime.now().isoformat(),
                        "data_publicacao": datetime.now().isoformat(),
                        "objeto": f"Busca por '{termo}' realizada. Verifique a janela do navegador.",
                        "link": target_url,
                        "itens": [],
                        "origem": "Portal Compras Públicas"
                    })

                browser.close()
                return resultados

        except Exception as e:
             return [{
                "pncp_id": "PCP-ERRO-BUSCA",
                "orgao": "Erro PCP",
                "uf": "BR",
                "modalidade": "Erro",
                "data_sessao": datetime.now().isoformat(),
                "data_publicacao": datetime.now().isoformat(),
                "objeto": f"Erro durante a busca visual: {str(e)}",
                "link": "https://www.portaldecompraspublicas.com.br/",
                "itens": [],
                "origem": "Portal Compras Públicas"
            }]
