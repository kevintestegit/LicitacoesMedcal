#!/usr/bin/env python3
"""
Script para fazer backup completo do banco de dados Medcal.
Exporta todos os dados para arquivos JSON que podem ser versionados no Git.

Uso: python scripts/backup_db.py
"""

import sys
import os
import json
from datetime import datetime

# Adiciona o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.database.database import get_session, Produto, Licitacao, ItemLicitacao, Configuracao, init_db

def backup_database():
    """Faz backup de todos os dados do banco para JSON."""

    print("🔄 Iniciando backup do banco de dados...")

    # Inicializa DB e cria sessão
    init_db()
    session = get_session()

    backup_data = {
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "version": "1.0"
        },
        "produtos": [],
        "configuracoes": [],
        "licitacoes": [],
        "itens_licitacao": []
    }

    # Backup de Produtos (catálogo)
    print("📦 Exportando catálogo de produtos...")
    produtos = session.query(Produto).all()
    for p in produtos:
        backup_data["produtos"].append({
            "id": p.id,
            "nome": p.nome,
            "palavras_chave": p.palavras_chave,
            "preco_custo": p.preco_custo,
            "margem_minima": p.margem_minima,
            "preco_referencia": p.preco_referencia,
            "fonte_referencia": p.fonte_referencia
        })

    # Backup de Configurações
    print("⚙️  Exportando configurações...")
    configs = session.query(Configuracao).all()
    for c in configs:
        backup_data["configuracoes"].append({
            "id": c.id,
            "chave": c.chave,
            "valor": c.valor
        })

    # Backup de Licitações (opcional - pode ser muito grande)
    print("📋 Exportando licitações...")
    licitacoes = session.query(Licitacao).all()
    for lic in licitacoes:
        backup_data["licitacoes"].append({
            "id": lic.id,
            "pncp_id": lic.pncp_id,
            "orgao": lic.orgao,
            "uf": lic.uf,
            "modalidade": lic.modalidade,
            "data_sessao": lic.data_sessao.isoformat() if lic.data_sessao else None,
            "data_publicacao": lic.data_publicacao.isoformat() if lic.data_publicacao else None,
            "data_inicio_proposta": lic.data_inicio_proposta.isoformat() if lic.data_inicio_proposta else None,
            "data_encerramento_proposta": lic.data_encerramento_proposta.isoformat() if lic.data_encerramento_proposta else None,
            "objeto": lic.objeto,
            "link": lic.link,
            "status": lic.status,
            "comentarios": lic.comentarios,
            "data_captura": lic.data_captura.isoformat() if lic.data_captura else None
        })

    # Backup de Itens de Licitação
    print("📝 Exportando itens de licitações...")
    itens = session.query(ItemLicitacao).all()
    for item in itens:
        backup_data["itens_licitacao"].append({
            "id": item.id,
            "licitacao_id": item.licitacao_id,
            "numero_item": item.numero_item,
            "descricao": item.descricao,
            "quantidade": item.quantidade,
            "unidade": item.unidade,
            "valor_estimado": item.valor_estimado,
            "valor_unitario": item.valor_unitario,
            "produto_match_id": item.produto_match_id,
            "match_score": item.match_score
        })

    # Salva em arquivo JSON
    backup_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backups')
    os.makedirs(backup_dir, exist_ok=True)

    # Arquivo com timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(backup_dir, f'backup_medcal_{timestamp}.json')

    # Também cria um backup "latest" para facilitar
    latest_file = os.path.join(backup_dir, 'backup_medcal_latest.json')

    with open(backup_file, 'w', encoding='utf-8') as f:
        json.dump(backup_data, f, indent=2, ensure_ascii=False)

    with open(latest_file, 'w', encoding='utf-8') as f:
        json.dump(backup_data, f, indent=2, ensure_ascii=False)

    session.close()

    # Estatísticas
    print("\n" + "=" * 60)
    print("✅ BACKUP CONCLUÍDO COM SUCESSO!")
    print("=" * 60)
    print(f"📦 Produtos: {len(backup_data['produtos'])}")
    print(f"⚙️  Configurações: {len(backup_data['configuracoes'])}")
    print(f"📋 Licitações: {len(backup_data['licitacoes'])}")
    print(f"📝 Itens: {len(backup_data['itens_licitacao'])}")
    print(f"\n📁 Arquivo: {backup_file}")
    print(f"📁 Latest: {latest_file}")
    print("=" * 60)
    print("\n💡 Para restaurar em outra máquina:")
    print("   python scripts/restore_db.py backups/backup_medcal_latest.json")

    return backup_file

if __name__ == "__main__":
    backup_database()
