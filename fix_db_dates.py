from sqlalchemy import create_engine, text
import pandas as pd
from database import Base, Produto

# Configuração
DB_PATH = 'sqlite:///medcal.db'
engine = create_engine(DB_PATH)

def fix_db_dates():
    print("🔧 Atualizando tabela de Licitações (Adicionando data_inicio_proposta)...")
    
    # 1. Backup dos Produtos (Raw SQL para evitar erro de schema)
    print("📦 Fazendo backup do catálogo...")
    try:
        with engine.connect() as conn:
            df_produtos = pd.read_sql("SELECT * FROM produtos", conn)
            print(f"✅ {len(df_produtos)} produtos salvos.")
    except Exception as e:
        print(f"⚠️ Erro ao ler produtos (pode ser primeira execução): {e}")
        df_produtos = pd.DataFrame()

    # 2. Drop All Tables
    print("🗑️ Limpando banco de dados antigo (Licitações antigas serão removidas)...")
    Base.metadata.drop_all(engine)
    
    # 3. Create All Tables (com novo schema)
    print("✨ Recriando tabelas com nova coluna...")
    Base.metadata.create_all(engine)
    
    # 4. Restore Produtos
    if not df_produtos.empty:
        print("♻️ Restaurando catálogo...")
        with engine.connect() as conn:
            # Ajusta colunas se necessário (garante que bate com o novo schema)
            # O pandas to_sql é prático aqui
            df_produtos.to_sql('produtos', conn, if_exists='append', index=False)
            print("✅ Catálogo restaurado com sucesso!")
            
    print("\n🚀 Migração concluída! O histórico de licitações foi limpo para remover itens vencidos.")
    print("👉 Por favor, faça uma nova busca no Dashboard.")

if __name__ == "__main__":
    fix_db_dates()
