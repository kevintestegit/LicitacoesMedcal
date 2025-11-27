import sqlite3
import os

# Configuração do Banco
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'data', 'medcal.db')

def migrate():
    print(f"Iniciando migração direta em {DB_PATH}...")
    
    if not os.path.exists(DB_PATH):
        print("ERRO: Banco de dados não encontrado. Rode o dashboard pelo menos uma vez para criar o arquivo vazio.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Termos Padrão
    TERMOS_POSITIVOS_PADRAO = [
        "Material Hospitalar", "Medicamentos", "Insumos Médicos", "Equipamentos Médicos",
        "Luvas Cirúrgicas", "Seringas", "Agulhas", "Gaze", "Atadura",
        "Soro Fisiológico", "Álcool 70", "Cateter", "Sonda", "Máscara Descartável",
        "Aparelho de Pressão", "Estetoscópio", "Termômetro", "Oxímetro",
        "Fios de Sutura", "Bisturi", "Lâmina de Bisturi", "Coletor de Urina",
        "Fralda Geriátrica", "Lençol Hospitalar", "Avental Descartável",
        "Touca Descartável", "Propé", "Algodão Hidrófilo", "Esparadrapo",
        "Fita Microporosa", "Scalp", "Jaleco", "Instrumental Cirúrgico",
        "Pinça Cirúrgica", "Tesoura Cirúrgica", "Cuba Rim", "Bacia de Inox",
        "Mesa Auxiliar", "Foco Cirúrgico", "Cadeira de Rodas", "Muletas",
        "Andador", "Cama Hospitalar", "Colchão Hospitalar", "Suporte de Soro",
        "Negatoscópio", "Autoclave", "Estufa de Esterilização", "Detergente Enzimático",
        "Papel Grau Cirúrgico", "Tubo de Ensaio", "Lâmina de Microscopia",
        "Reagentes Laboratoriais", "Teste Rápido", "Glicosímetro", "Tiras de Glicemia",
        "Lancetas", "Nebulizador", "Inalador", "Aspirador Cirúrgico", "Desfibrilador",
        "Monitor Multiparâmetro", "Eletrocardiógrafo", "Ventilador Mecânico", "Respirador",
        "Ambú", "Laringoscópio", "Otoscópio", "Oftalmoscópio", "Balança Antropométrica",
        "Fita Métrica", "Martelo de Reflexo", "Diapasão", "Lanterna Clínica"
    ]

    # 1. Verificar/Criar Tabela se não existir (Fallback)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS configuracoes (
        id INTEGER PRIMARY KEY,
        chave TEXT UNIQUE NOT NULL,
        valor TEXT
    )
    """)

    # 2. Inserir Termos
    try:
        cursor.execute("SELECT valor FROM configuracoes WHERE chave = 'termos_busca_padrao'")
        if not cursor.fetchone():
            print("Inserindo termos padrão...")
            termos_str = ", ".join(TERMOS_POSITIVOS_PADRAO)
            cursor.execute("INSERT INTO configuracoes (chave, valor) VALUES (?, ?)", ('termos_busca_padrao', termos_str))
        else:
            print("Termos já configurados.")
    except Exception as e:
        print(f"Erro ao inserir termos: {e}")

    # 3. Inserir API Key
    try:
        cursor.execute("SELECT valor FROM configuracoes WHERE chave = 'gemini_api_key'")
        if not cursor.fetchone():
            print("Inserindo placeholder API Key...")
            cursor.execute("INSERT INTO configuracoes (chave, valor) VALUES (?, ?)", ('gemini_api_key', ''))
    except Exception as e:
        print(f"Erro API Key: {e}")

    # 4. WhatsApp
    try:
        cursor.execute("SELECT valor FROM configuracoes WHERE chave = 'whatsapp_phone'")
        if not cursor.fetchone():
            cursor.execute("INSERT INTO configuracoes (chave, valor) VALUES (?, ?)", ('whatsapp_phone', ''))
            
        cursor.execute("SELECT valor FROM configuracoes WHERE chave = 'whatsapp_apikey'")
        if not cursor.fetchone():
            cursor.execute("INSERT INTO configuracoes (chave, valor) VALUES (?, ?)", ('whatsapp_apikey', ''))
    except Exception as e:
        print(f"Erro WhatsApp: {e}")

    conn.commit()
    conn.close()
    print("Migração direta concluída.")

if __name__ == "__main__":
    migrate()
