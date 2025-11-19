from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database import Base, Licitacao, ItemLicitacao
from pncp_client import PNCPClient

# Configuração
DB_PATH = 'sqlite:///medcal.db'
engine = create_engine(DB_PATH)
Session = sessionmaker(bind=engine)
session = Session()

def clean_bad_biddings():
    print("🧹 Iniciando limpeza retroativa de licitações indesejadas...")
    
    # Instancia o client para pegar a lista ATUALIZADA de termos negativos
    client = PNCPClient()
    termos_negativos = client.TERMOS_NEGATIVOS_PADRAO
    termos_negativos_upper = [t.upper() for t in termos_negativos]
    
    print(f"📋 Verificando licitações contra {len(termos_negativos)} termos negativos...")
    
    licitacoes = session.query(Licitacao).all()
    removidos = 0
    
    for lic in licitacoes:
        if not lic.objeto:
            continue
            
        obj_upper = lic.objeto.upper()
        
        # Verifica se tem termo negativo
        match = False
        for termo in termos_negativos_upper:
            if termo in obj_upper:
                match = True
                print(f"❌ Removendo ID {lic.id}: Encontrado termo '{termo}'")
                print(f"   Objeto: {lic.objeto[:100]}...")
                break
        
        if match:
            # Deleta itens primeiro (cascade deve cuidar, mas garantindo)
            session.query(ItemLicitacao).filter_by(licitacao_id=lic.id).delete()
            session.delete(lic)
            removidos += 1
            
    session.commit()
    session.close()
    
    print(f"\n✅ Limpeza concluída! {removidos} licitações indesejadas foram removidas do banco.")
    print("👉 Por favor, recarregue o Dashboard (F5) para ver a lista limpa.")

if __name__ == "__main__":
    clean_bad_biddings()
