#!/usr/bin/env python3
"""
Script para importar catálogo de produtos a partir de um arquivo JSON.
Execute: python scripts/import_catalogo_json.py [arquivo.json]

Por padrão, usa: data/catalogo_produtos.json
"""

import sys
import os
import io
import json

# Configura encoding UTF-8 para Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Adiciona o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.database.database import get_session, Produto, init_db

def importar_catalogo_json(arquivo_json, auto_substituir=False):
    """
    Importa catálogo de produtos a partir de um arquivo JSON.

    Args:
        arquivo_json: Caminho para o arquivo JSON
        auto_substituir: Se True, substitui automaticamente sem perguntar
    """

    print(f"📂 Lendo arquivo: {arquivo_json}")

    # Verifica se arquivo existe
    if not os.path.exists(arquivo_json):
        print(f"❌ Arquivo não encontrado: {arquivo_json}")
        return False

    # Carrega o JSON
    try:
        with open(arquivo_json, 'r', encoding='utf-8') as f:
            produtos_json = json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ Erro ao ler JSON: {e}")
        return False

    print(f"📦 Produtos no arquivo: {len(produtos_json)}")

    # Inicializa o banco
    init_db()
    session = get_session()

    # Verifica produtos existentes
    produtos_existentes = session.query(Produto).count()

    if produtos_existentes > 0:
        print(f"⚠️  Existem {produtos_existentes} produtos no banco.")
        if auto_substituir:
            session.query(Produto).delete()
            print("🗑️  Produtos anteriores removidos (modo automático).")
        else:
            try:
                resposta = input("Deseja SUBSTITUIR todos? (s/N): ").strip().lower()
                if resposta == 's':
                    session.query(Produto).delete()
                    print("🗑️  Produtos anteriores removidos.")
                else:
                    print("➕ Adicionando aos produtos existentes...")
            except EOFError:
                print("➕ Adicionando aos produtos existentes (modo não-interativo)...")

    # Adiciona os produtos
    produtos_adicionados = 0
    produtos_com_erro = 0

    for p in produtos_json:
        try:
            produto = Produto(
                nome=p['nome'],
                palavras_chave=p['palavras_chave'],
                preco_custo=p['preco_custo'],
                margem_minima=p['margem_minima'],
                preco_referencia=p.get('preco_referencia', 0.0),
                fonte_referencia=p.get('fonte_referencia', '')
            )
            session.add(produto)
            produtos_adicionados += 1
        except KeyError as e:
            print(f"⚠️  Erro no produto: campo obrigatório ausente: {e}")
            produtos_com_erro += 1
        except Exception as e:
            print(f"⚠️  Erro ao adicionar produto: {e}")
            produtos_com_erro += 1

    # Commit
    try:
        session.commit()
    except Exception as e:
        session.rollback()
        print(f"❌ Erro ao salvar no banco: {e}")
        return False

    # Confirma
    total = session.query(Produto).count()
    print(f"\n✅ Catálogo importado! Total de produtos no banco: {total}")
    print(f"   Adicionados: {produtos_adicionados}")
    if produtos_com_erro > 0:
        print(f"   ⚠️  Com erro: {produtos_com_erro}")

    print("\nProdutos cadastrados:")
    for p in session.query(Produto).all():
        print(f"  • {p.nome}")

    session.close()
    return True

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Importa catálogo de produtos do JSON")
    parser.add_argument("arquivo", nargs='?',
                        default="data/catalogo_produtos.json",
                        help="Arquivo JSON com os produtos (padrão: data/catalogo_produtos.json)")
    parser.add_argument("--substituir", "-s", action="store_true",
                        help="Substitui automaticamente produtos existentes sem perguntar")

    args = parser.parse_args()

    print("=" * 60)
    print("📦 IMPORTAÇÃO DE CATÁLOGO - ARQUIVO JSON")
    print("=" * 60)
    print()

    sucesso = importar_catalogo_json(args.arquivo, auto_substituir=args.substituir)

    print()
    print("=" * 60)

    sys.exit(0 if sucesso else 1)
