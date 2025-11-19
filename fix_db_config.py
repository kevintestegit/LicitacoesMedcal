from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database import Base, Configuracao
from pncp_client import PNCPClient

# Configuração
DB_PATH = 'sqlite:///medcal.db'
engine = create_engine(DB_PATH)
Session = sessionmaker(bind=engine)

def fix_db_config():
    print("🔧 Atualizando banco de dados (Criando tabela Configurações)...")
    
    # Cria tabelas novas (não afeta as existentes se já estiverem lá, mas o create_all é seguro)
    Base.metadata.create_all(engine)
    
    session = Session()
    
    # Verifica se já existe a configuração
    config = session.query(Configuracao).filter_by(chave='termos_busca_padrao').first()
    
    if not config:
        print("⚙️ Inicializando termos padrão no banco...")
        client = PNCPClient()
        termos_iniciais = ", ".join(client.TERMOS_POSITIVOS_PADRAO)
        
        nova_config = Configuracao(chave='termos_busca_padrao', valor=termos_iniciais)
        session.add(nova_config)
        session.commit()
        print("✅ Termos padrão migrados do código para o banco!")
    else:
        print("ℹ️ Configuração já existe. Nenhuma alteração feita.")
        
    session.close()
    print("\n🚀 Migração de Configurações concluída!")

if __name__ == "__main__":
    fix_db_config()
