"""
Script de migração para adicionar coluna analise_profunda_json à tabela licitacoes.
Também migra dados existentes do campo 'comentarios' para a nova coluna.
"""
import sqlite3
import json
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'data', 'medcal.db')


def migrate():
    """Adiciona coluna analise_profunda_json e migra dados existentes"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("🔄 Verificando estrutura da tabela licitacoes...")
    
    # Verifica se a coluna já existe
    cursor.execute("PRAGMA table_info(licitacoes)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if 'analise_profunda_json' in columns:
        print("✅ Coluna 'analise_profunda_json' já existe!")
    else:
        print("📝 Adicionando coluna 'analise_profunda_json'...")
        cursor.execute("ALTER TABLE licitacoes ADD COLUMN analise_profunda_json TEXT")
        conn.commit()
        print("✅ Coluna adicionada com sucesso!")
    
    # Migra dados existentes do campo comentarios que contenham deep_analysis
    print("🔄 Migrando dados de análise profunda existentes...")
    cursor.execute("SELECT id, comentarios FROM licitacoes WHERE comentarios IS NOT NULL")
    rows = cursor.fetchall()
    
    migrados = 0
    for row_id, comentarios in rows:
        if not comentarios:
            continue
        try:
            data = json.loads(comentarios)
            if isinstance(data, dict) and 'deep_analysis' in data:
                # Move para a nova coluna
                cursor.execute(
                    "UPDATE licitacoes SET analise_profunda_json = ?, comentarios = NULL WHERE id = ?",
                    (comentarios, row_id)
                )
                migrados += 1
        except (json.JSONDecodeError, TypeError):
            # Não é JSON, mantém como comentário de texto
            pass
    
    conn.commit()
    print(f"✅ {migrados} registros migrados para nova coluna!")
    
    conn.close()
    print("🎉 Migração concluída com sucesso!")


if __name__ == "__main__":
    migrate()
