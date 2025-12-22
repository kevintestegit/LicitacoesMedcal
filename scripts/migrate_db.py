import sys
import os

# Add root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.database.database import get_session, Configuracao, init_db
from modules.scrapers.pncp_client import PNCPClient

def migrate():
    print("Iniciando migração...")
    init_db()
    session = get_session()
    
    # 1. Configuração de Termos Padrão
    config_termos = session.query(Configuracao).filter_by(chave='termos_busca_padrao').first()
    if not config_termos:
        print("Criando configuração padrão de termos de busca...")
        termos_str = ", ".join(PNCPClient.TERMOS_POSITIVOS_PADRAO)
        novo_config = Configuracao(chave='termos_busca_padrao', valor=termos_str)
        session.add(novo_config)
    else:
        print("Configuração de termos já existe.")

    # 2. Configuração de API Key (OpenRouter)
    config_api = session.query(Configuracao).filter_by(chave='openrouter_api_key').first()
    if not config_api:
        print("Criando placeholder para OpenRouter API Key...")
        session.add(Configuracao(chave='openrouter_api_key', valor=''))

    # 3. Configuração de WhatsApp (Placeholder)
    config_wpp_phone = session.query(Configuracao).filter_by(chave='whatsapp_phone').first()
    if not config_wpp_phone:
        session.add(Configuracao(chave='whatsapp_phone', valor=''))
        
    config_wpp_key = session.query(Configuracao).filter_by(chave='whatsapp_apikey').first()
    if not config_wpp_key:
        session.add(Configuracao(chave='whatsapp_apikey', valor=''))

    session.commit()
    session.close()
    print("Migração concluída com sucesso!")

if __name__ == "__main__":
    migrate()
