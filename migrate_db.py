from sqlalchemy import create_engine, text

engine = create_engine('sqlite:///medcal.db')

with engine.connect() as conn:
    result = conn.execute(text("PRAGMA table_info(licitacoes)"))
    columns = [row[1] for row in result]
    
    if 'status' not in columns:
        print("Adicionando coluna status...")
        conn.execute(text("ALTER TABLE licitacoes ADD COLUMN status VARCHAR DEFAULT 'Nova'"))
    
    if 'comentarios' not in columns:
        print("Adicionando coluna comentarios...")
        conn.execute(text("ALTER TABLE licitacoes ADD COLUMN comentarios TEXT"))
        
    if 'data_captura' not in columns:
        print("Adicionando coluna data_captura...")
        conn.execute(text("ALTER TABLE licitacoes ADD COLUMN data_captura DATETIME"))

print("Migração concluída.")
