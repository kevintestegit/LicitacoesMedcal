#!/usr/bin/env python3
"""
Importa dados financeiros das planilhas Excel para o Turso.
"""
import os
import sys
import hashlib
import sqlite3
from pathlib import Path
import pandas as pd
from dotenv import load_dotenv
import libsql_experimental as libsql

# Setup
BASE_DIR = Path(__file__).parent.parent
load_dotenv(BASE_DIR / '.env')

TURSO_URL = os.getenv('TURSO_DATABASE_URL')
TURSO_TOKEN = os.getenv('TURSO_AUTH_TOKEN')

EXCEL_ATUAL = Path.home() / 'Downloads' / 'lancamentos_todos_meses_atual.xlsx'
EXCEL_HISTORICO = Path.home() / 'Downloads' / 'lancamentos_todos_meses_historico.xlsx'
CHUNK_SIZE = 1000
LOCAL_DB = Path('data/excel_import.db')

def get_local_conn():
    return sqlite3.connect(str(LOCAL_DB))


def get_turso_sync_conn():
    return libsql.connect(
        str(LOCAL_DB),
        sync_url=TURSO_URL,
        auth_token=TURSO_TOKEN,
    )

def create_extratos_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS extratos_bb (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            status TEXT,
            dt_balancete DATE,
            ag_origem TEXT,
            lote TEXT,
            historico TEXT,
            documento TEXT,
            valor REAL,
            fatura TEXT,
            tipo TEXT,
            historico_complementar TEXT,
            mes_referencia INTEGER,
            ano_referencia INTEGER,
            data_upload DATETIME,
            arquivo_origem TEXT,
            hash_lancamento TEXT UNIQUE,
            observacoes TEXT,
            banco TEXT
        )
    """)
    conn.commit()

def import_excel(excel_path: Path, conn, source_name: str):
    if not excel_path.exists():
        print(f"  ⚠️ Arquivo não encontrado: {excel_path}")
        return 0
    
    print(f"  📖 Lendo {excel_path.name}...", flush=True)
    df = pd.read_excel(excel_path)
    print(f"  📊 {len(df)} linhas encontradas", flush=True)
    
    if len(df) == 0:
        return 0
    
    # Mapeamento correto baseado nas colunas reais do Excel
    # Excel: ['Mês', 'Ano', 'Data', 'Status', 'Histórico', 'Documento', 'Valor', 'Tipo', 'Fatura']
    inserted = 0
    batch = []
    
    for row in df.to_dict(orient='records'):
        try:
            # Extrai dados da linha
            data = row.get('Data')
            status = row.get('Status') if pd.notna(row.get('Status')) else None
            historico = row.get('Histórico') if pd.notna(row.get('Histórico')) else None
            documento = str(row.get('Documento')) if pd.notna(row.get('Documento')) else None
            valor = float(row.get('Valor')) if pd.notna(row.get('Valor')) else 0.0
            tipo = row.get('Tipo') if pd.notna(row.get('Tipo')) else None
            fatura = row.get('Fatura') if pd.notna(row.get('Fatura')) else None
            
            # Mês e ano
            mes_ref = row.get('Mês')
            ano_ref = int(row.get('Ano')) if pd.notna(row.get('Ano')) else None
            
            # Converte mês texto para número
            mes_map = {'Jan':1,'Fev':2,'Mar':3,'Abr':4,'Mai':5,'Jun':6,
                      'Jul':7,'Ago':8,'Set':9,'Out':10,'Nov':11,'Dez':12}
            mes_num = mes_map.get(mes_ref, None) if isinstance(mes_ref, str) else None
            
            # Converte data
            dt_balancete = None
            if pd.notna(data):
                if hasattr(data, 'strftime'):
                    dt_balancete = data.strftime('%Y-%m-%d')
                else:
                    dt_balancete = str(data)[:10]
            
            # Hash único
            hash_str = f"{dt_balancete}|{documento}|{valor}|{historico}"
            hash_lanc = hashlib.md5(hash_str.encode()).hexdigest()
            
            batch.append((
                status, dt_balancete, historico, documento, valor, tipo, fatura,
                mes_num, ano_ref, hash_lanc, source_name
            ))
            
            if len(batch) >= CHUNK_SIZE:
                conn.executemany("""
                    INSERT OR IGNORE INTO extratos_bb 
                    (status, dt_balancete, historico, documento, valor, tipo, fatura, 
                     mes_referencia, ano_referencia, hash_lancamento, arquivo_origem, data_upload)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                """, batch)
                inserted += len(batch)
                batch.clear()
                print(f"    → {inserted}/{len(df)} processados...", end='\r', flush=True)
                
        except Exception:
            continue
    
    if batch:
        conn.executemany("""
            INSERT OR IGNORE INTO extratos_bb 
            (status, dt_balancete, historico, documento, valor, tipo, fatura, 
             mes_referencia, ano_referencia, hash_lancamento, arquivo_origem, data_upload)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """, batch)
        inserted += len(batch)
    
    conn.commit()
    print(f"    ✅ {inserted} registros importados de {source_name}", flush=True)
    return inserted

def main():
    print("🚀 IMPORTAÇÃO DE DADOS FINANCEIROS VIA EXCEL", flush=True)
    print("=" * 50, flush=True)
    
    if not TURSO_URL or not TURSO_TOKEN:
        print("❌ Configure TURSO no .env")
        sys.exit(1)
    
    # Garante um arquivo local limpo para evitar corrupção
    for suffix in ["", "-wal", "-shm"]:
        local_path = LOCAL_DB.with_name(LOCAL_DB.name + suffix)
        if local_path.exists():
            local_path.unlink()
    
    conn = get_local_conn()
    
    print("\n🧹 Limpando dados antigos...", flush=True)
    try:
        conn.execute("DELETE FROM extratos_bb")
        conn.commit()
    except:
        pass
    
    create_extratos_table(conn)
    
    total = 0
    
    print("\n📦 Importando ATUAL...", flush=True)
    total += import_excel(EXCEL_ATUAL, conn, "excel_atual")
    
    print("\n📦 Importando HISTÓRICO...", flush=True)
    total += import_excel(EXCEL_HISTORICO, conn, "excel_historico")
    
    print("\n" + "=" * 50, flush=True)
    print("📊 VERIFICAÇÃO FINAL", flush=True)
    print("=" * 50, flush=True)
    
    count = conn.execute("SELECT COUNT(*) FROM extratos_bb").fetchone()[0]
    print(f"  extratos_bb: {count} registros", flush=True)
    
    anos = conn.execute("SELECT DISTINCT ano_referencia FROM extratos_bb ORDER BY ano_referencia").fetchall()
    print(f"  Anos: {[a[0] for a in anos if a[0]]}", flush=True)
    
    conn.close()
    
    print("\n🔄 Sincronizando com Turso...", flush=True)
    turso_conn = get_turso_sync_conn()
    turso_conn.sync()
    
    remote_count = turso_conn.execute("SELECT COUNT(*) FROM extratos_bb").fetchone()[0]
    print(f"  Turso extratos_bb: {remote_count} registros", flush=True)
    
    print(f"\n✨ Concluído! Total: {total} registros", flush=True)

if __name__ == "__main__":
    main()
