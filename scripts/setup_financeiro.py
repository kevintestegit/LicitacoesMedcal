"""
Script de configuração inicial do módulo financeiro
Cria as tabelas e adiciona dados de exemplo (opcional)
"""

import sys
import os
import io

# Configura encoding UTF-8 para Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Adiciona o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.database.database import init_db, get_session, ContaBancaria, Fatura, ExtratoBancario
from datetime import datetime, timedelta

def setup_financeiro(criar_exemplos=False):
    """
    Configura o módulo financeiro

    Args:
        criar_exemplos: Se True, cria dados de exemplo para teste
    """
    print("🚀 Iniciando setup do módulo financeiro...")

    # 1. Criar tabelas
    print("📊 Criando tabelas no banco de dados...")
    init_db()
    print("✅ Tabelas criadas com sucesso!")

    if criar_exemplos:
        print("\n📝 Criando dados de exemplo...")
        session = get_session()

        try:
            # Verifica se já existem dados
            if session.query(ContaBancaria).first():
                print("⚠️ Já existem dados no sistema. Pulando criação de exemplos.")
                return

            # 1. Criar conta de exemplo
            print("   → Criando conta bancária de exemplo...")
            conta = ContaBancaria(
                banco="Banco do Brasil",
                agencia="1234-5",
                conta="98765-4",
                tipo_conta="Corrente",
                nome_conta="Conta Principal",
                saldo_atual=25000.00
            )
            session.add(conta)
            session.flush()

            # 2. Criar faturas de exemplo
            print("   → Criando faturas de exemplo...")
            hoje = datetime.now().date()

            faturas_exemplo = [
                {
                    "tipo": "PAGAR",
                    "fornecedor_cliente": "ABC Materiais Médicos Ltda",
                    "descricao": "Nota Fiscal 1234 - Materiais hospitalares",
                    "numero_nota": "NF-1234",
                    "valor_original": 1500.00,
                    "data_emissao": hoje - timedelta(days=10),
                    "data_vencimento": hoje - timedelta(days=2),
                    "forma_pagamento": "TED"
                },
                {
                    "tipo": "PAGAR",
                    "fornecedor_cliente": "Energia Elétrica S.A.",
                    "descricao": "Conta de luz - Janeiro",
                    "numero_nota": "BOL-789",
                    "valor_original": 580.00,
                    "data_emissao": hoje - timedelta(days=5),
                    "data_vencimento": hoje + timedelta(days=3),
                    "forma_pagamento": "Boleto"
                },
                {
                    "tipo": "PAGAR",
                    "fornecedor_cliente": "GHI Medical Equipment",
                    "descricao": "Equipamentos médicos - Pedido 5678",
                    "numero_nota": "NF-5678",
                    "valor_original": 3400.00,
                    "data_emissao": hoje - timedelta(days=15),
                    "data_vencimento": hoje - timedelta(days=8),
                    "forma_pagamento": "PIX"
                },
                {
                    "tipo": "RECEBER",
                    "fornecedor_cliente": "Secretaria Municipal de Saúde",
                    "descricao": "Licitação PE 2024 - Materiais",
                    "numero_nota": "NE-9999",
                    "valor_original": 15000.00,
                    "data_emissao": hoje - timedelta(days=20),
                    "data_vencimento": hoje + timedelta(days=15),
                    "forma_pagamento": "TED"
                }
            ]

            for fat_data in faturas_exemplo:
                fatura = Fatura(**fat_data)
                session.add(fatura)

            session.commit()
            print("✅ Dados de exemplo criados com sucesso!")

            print("\n" + "="*60)
            print("📊 RESUMO DO SETUP:")
            print("="*60)
            print(f"✅ 1 Conta bancária criada")
            print(f"✅ {len(faturas_exemplo)} Faturas de exemplo criadas")
            print(f"✅ Sistema pronto para uso!")
            print("="*60)
            print("\n💡 PRÓXIMOS PASSOS:")
            print("1. Execute o dashboard: streamlit run dashboard.py")
            print("2. Vá em '💰 Gestão Financeira'")
            print("3. Importe um extrato na aba '📤 Extratos'")
            print("4. Execute a conciliação automática!")
            print("\n📁 Arquivo de exemplo: data/exemplo_extrato.csv")

        except Exception as e:
            session.rollback()
            print(f"❌ Erro ao criar dados de exemplo: {e}")
            raise
        finally:
            session.close()
    else:
        print("\n✅ Setup concluído! Sistema pronto para uso.")
        print("\n💡 Para criar dados de exemplo, execute:")
        print("   python scripts/setup_financeiro.py --exemplos")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Setup do módulo financeiro")
    parser.add_argument("--exemplos", action="store_true",
                        help="Criar dados de exemplo para teste")

    args = parser.parse_args()

    setup_financeiro(criar_exemplos=args.exemplos)
