from sqlalchemy import create_engine
import pandas as pd
from database import Base

# Configuração
DB_PATH = 'sqlite:///medcal.db'
engine = create_engine(DB_PATH)

def fix_db_dates_v2():
    print("🔧 Atualizando tabela de Licitações (Adicionando data_encerramento_proposta)...")
    
    # 1. Backup dos Produtos
    print("📦 Fazendo backup do catálogo...")
    try:
        with engine.connect() as conn:
            df_produtos = pd.read_sql("SELECT * FROM produtos", conn)
            print(f"✅ {len(df_produtos)} produtos salvos.")
    except Exception as e:
        print(f"⚠️ Erro ao ler produtos: {e}")
        df_produtos = pd.DataFrame()

    # 2. Drop All Tables
    print("🗑️ Limpando banco de dados (Licitações antigas serão removidas)...")
    Base.metadata.drop_all(engine)
    
    # 3. Create All Tables
    print("✨ Recriando tabelas com novo schema...")
    Base.metadata.create_all(engine)
    
    # 4. Restore Produtos
    if not df_produtos.empty:
        print("♻️ Restaurando catálogo...")
        with engine.connect() as conn:
            df_produtos.to_sql('produtos', conn, if_exists='append', index=False)
            print("✅ Catálogo restaurado!")
            
    print("\n🚀 Migração V2 concluída! Agora o sistema suporta Data de Encerramento.")
    print("👉 Por favor, faça uma nova busca no Dashboard.")

if __name__ == "__main__":
    fix_db_dates_v2()
