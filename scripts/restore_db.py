#!/usr/bin/env python3
"""
Script para restaurar backup do banco de dados Medcal.
Importa dados de um arquivo JSON criado pelo backup_db.py

Uso: python scripts/restore_db.py [caminho_do_backup.json]
"""

import sys
import os
import json
from datetime import datetime

# Adiciona o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.database.database import get_session, Produto, Licitacao, ItemLicitacao, Configuracao, init_db

def restore_database(backup_file, modo='substituir'):
    """
    Restaura o banco de dados a partir de um arquivo JSON.

    Args:
        backup_file: Caminho para o arquivo de backup JSON
        modo: 'substituir' (limpa antes) ou 'adicionar' (mantém dados existentes)
    """

    print(f"🔄 Restaurando backup de: {backup_file}")

    # Verifica se arquivo existe
    if not os.path.exists(backup_file):
        print(f"❌ Arquivo não encontrado: {backup_file}")
        return False

    # Carrega o backup
    with open(backup_file, 'r', encoding='utf-8') as f:
        backup_data = json.load(f)

    print(f"📅 Data do backup: {backup_data['metadata']['timestamp']}")
    print(f"📦 Produtos no backup: {len(backup_data['produtos'])}")
    print(f"⚙️  Configurações no backup: {len(backup_data['configuracoes'])}")
    print(f"📋 Licitações no backup: {len(backup_data['licitacoes'])}")
    print(f"📝 Itens no backup: {len(backup_data['itens_licitacao'])}")

    # Confirmação
    if modo == 'substituir':
        resposta = input("\n⚠️  Isso irá SUBSTITUIR todos os dados atuais. Continuar? (s/N): ").strip().lower()
        if resposta != 's':
            print("❌ Operação cancelada.")
            return False

    # Inicializa DB e cria sessão
    init_db()
    session = get_session()

    try:
        # 1. Produtos
        if modo == 'substituir':
            print("\n🗑️  Limpando produtos existentes...")
            session.query(Produto).delete()

        print("📦 Importando produtos...")
        for p in backup_data['produtos']:
            produto = Produto(
                nome=p['nome'],
                palavras_chave=p['palavras_chave'],
                preco_custo=p['preco_custo'],
                margem_minima=p['margem_minima'],
                preco_referencia=p.get('preco_referencia', 0.0),
                fonte_referencia=p.get('fonte_referencia', '')
            )
            session.add(produto)

        # 2. Configurações
        if modo == 'substituir':
            print("🗑️  Limpando configurações existentes...")
            session.query(Configuracao).delete()

        print("⚙️  Importando configurações...")
        for c in backup_data['configuracoes']:
            config = Configuracao(
                chave=c['chave'],
                valor=c['valor']
            )
            session.add(config)

        # 3. Licitações
        if modo == 'substituir' and len(backup_data['licitacoes']) > 0:
            print("🗑️  Limpando licitações existentes...")
            session.query(Licitacao).delete()

        if len(backup_data['licitacoes']) > 0:
            print("📋 Importando licitações...")
            id_map = {}  # Mapeia IDs antigos para novos

            for lic in backup_data['licitacoes']:
                licitacao = Licitacao(
                    pncp_id=lic['pncp_id'],
                    orgao=lic['orgao'],
                    uf=lic['uf'],
                    modalidade=lic['modalidade'],
                    data_sessao=datetime.fromisoformat(lic['data_sessao']) if lic['data_sessao'] else None,
                    data_publicacao=datetime.fromisoformat(lic['data_publicacao']) if lic['data_publicacao'] else None,
                    data_inicio_proposta=datetime.fromisoformat(lic['data_inicio_proposta']) if lic['data_inicio_proposta'] else None,
                    data_encerramento_proposta=datetime.fromisoformat(lic['data_encerramento_proposta']) if lic['data_encerramento_proposta'] else None,
                    objeto=lic['objeto'],
                    link=lic['link'],
                    status=lic['status'],
                    comentarios=lic['comentarios'],
                    data_captura=datetime.fromisoformat(lic['data_captura']) if lic['data_captura'] else None
                )
                session.add(licitacao)
                session.flush()  # Para obter o ID
                id_map[lic['id']] = licitacao.id

            # 4. Itens de Licitação
            if modo == 'substituir':
                print("🗑️  Limpando itens de licitações existentes...")
                session.query(ItemLicitacao).delete()

            print("📝 Importando itens de licitações...")
            for item in backup_data['itens_licitacao']:
                novo_item = ItemLicitacao(
                    licitacao_id=id_map.get(item['licitacao_id'], item['licitacao_id']),
                    numero_item=item['numero_item'],
                    descricao=item['descricao'],
                    quantidade=item['quantidade'],
                    unidade=item['unidade'],
                    valor_estimado=item['valor_estimado'],
                    valor_unitario=item['valor_unitario'],
                    produto_match_id=item['produto_match_id'],
                    match_score=item['match_score']
                )
                session.add(novo_item)

        # Commit final
        session.commit()

        # Confirmação
        print("\n" + "=" * 60)
        print("✅ RESTAURAÇÃO CONCLUÍDA COM SUCESSO!")
        print("=" * 60)
        print(f"📦 Produtos no banco: {session.query(Produto).count()}")
        print(f"⚙️  Configurações no banco: {session.query(Configuracao).count()}")
        print(f"📋 Licitações no banco: {session.query(Licitacao).count()}")
        print(f"📝 Itens no banco: {session.query(ItemLicitacao).count()}")
        print("=" * 60)

        return True

    except Exception as e:
        session.rollback()
        print(f"\n❌ Erro durante a restauração: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        session.close()

if __name__ == "__main__":
    # Verifica argumentos
    if len(sys.argv) > 1:
        backup_file = sys.argv[1]
    else:
        # Usa o último backup por padrão
        backup_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backups')
        backup_file = os.path.join(backup_dir, 'backup_medcal_latest.json')

    print("=" * 60)
    print("🔄 RESTAURAÇÃO DO BANCO DE DADOS MEDCAL")
    print("=" * 60)
    print()

    restore_database(backup_file, modo='substituir')
