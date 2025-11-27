import sqlite3
import os

db_path = "data/medcal.db"

if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        print("Tentando adicionar colunas 'total_entradas' e 'total_saidas' na tabela 'resumos_mensais'...")
        cursor.execute("ALTER TABLE resumos_mensais ADD COLUMN total_entradas FLOAT DEFAULT 0.0")
        cursor.execute("ALTER TABLE resumos_mensais ADD COLUMN total_saidas FLOAT DEFAULT 0.0")
        conn.commit()
        print("Colunas adicionadas com sucesso.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("Colunas já existem.")
        else:
            print(f"Erro: {e}")
            
    conn.close()
else:
    print(f"Banco de dados não encontrado em: {db_path}")
