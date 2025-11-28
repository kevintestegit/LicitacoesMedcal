"""
Script de Teste de Performance
Identifica gargalos em operações críticas do sistema
"""

import time
import pandas as pd
import sys
import os
from datetime import datetime
from pathlib import Path

# Adiciona o diretório raiz ao path
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

from modules.database.database import get_session, Licitacao, ItemLicitacao, Produto
from modules.finance.extrato_parser import ExtratoBBParser
from modules.finance import get_finance_session
from modules.finance.bank_models import ExtratoBB


class PerformanceTest:
    """Classe para testes de performance"""

    def __init__(self):
        self.results = []

    def time_test(self, name, func, *args, **kwargs):
        """Executa teste e mede tempo"""
        print(f"\n{'='*60}")
        print(f"Testando: {name}")
        print(f"{'='*60}")

        start = time.time()
        try:
            result = func(*args, **kwargs)
            elapsed = time.time() - start
            status = "[OK]"
            error = None
        except Exception as e:
            elapsed = time.time() - start
            status = "[ERRO]"
            error = str(e)
            result = None

        self.results.append({
            'teste': name,
            'tempo_segundos': round(elapsed, 4),
            'status': status,
            'erro': error
        })

        print(f"Tempo: {elapsed:.4f}s")
        print(f"Status: {status}")
        if error:
            print(f"Erro: {error}")

        return result, elapsed

    # ====== TESTES DE BANCO DE DADOS ======

    def test_query_licitacoes_sem_indice(self):
        """Testa query de licitações sem otimização"""
        session = get_session()
        start = time.time()

        # Query sem índice otimizado
        licitacoes = session.query(Licitacao).filter(
            Licitacao.status == 'Nova'
        ).all()

        elapsed = time.time() - start
        session.close()

        print(f"  - {len(licitacoes)} licitações carregadas")
        return elapsed

    def test_query_com_joins(self):
        """Testa query com joins de itens"""
        session = get_session()
        start = time.time()

        # Query com joins (pode ser lenta)
        licitacoes = session.query(Licitacao).filter(
            Licitacao.status == 'Nova'
        ).all()

        # Força carregamento de itens
        total_itens = 0
        for lic in licitacoes:
            total_itens += len(lic.itens)

        elapsed = time.time() - start
        session.close()

        print(f"  - {len(licitacoes)} licitações com {total_itens} itens carregados")
        return elapsed

    def test_query_extrato_financeiro(self):
        """Testa query de extratos financeiros"""
        session = get_finance_session()
        start = time.time()

        extratos = session.query(ExtratoBB).limit(1000).all()

        elapsed = time.time() - start
        session.close()

        print(f"  - {len(extratos)} extratos carregados")
        return elapsed

    # ====== TESTES DE PANDAS ======

    def test_pandas_iterrows(self, num_rows=1000):
        """Testa performance de iterrows (LENTO)"""
        df = pd.DataFrame({
            'col1': range(num_rows),
            'col2': [f'texto_{i}' for i in range(num_rows)],
            'col3': [float(i) * 1.5 for i in range(num_rows)]
        })

        start = time.time()
        result = []
        for idx, row in df.iterrows():
            result.append(row['col1'] + row['col3'])

        elapsed = time.time() - start
        print(f"  - {num_rows} linhas processadas com iterrows")
        return elapsed

    def test_pandas_apply(self, num_rows=1000):
        """Testa performance de apply (MELHOR)"""
        df = pd.DataFrame({
            'col1': range(num_rows),
            'col2': [f'texto_{i}' for i in range(num_rows)],
            'col3': [float(i) * 1.5 for i in range(num_rows)]
        })

        start = time.time()
        result = df.apply(lambda row: row['col1'] + row['col3'], axis=1)

        elapsed = time.time() - start
        print(f"  - {num_rows} linhas processadas com apply")
        return elapsed

    def test_pandas_vectorized(self, num_rows=1000):
        """Testa performance de operações vetorizadas (RÁPIDO)"""
        df = pd.DataFrame({
            'col1': range(num_rows),
            'col2': [f'texto_{i}' for i in range(num_rows)],
            'col3': [float(i) * 1.5 for i in range(num_rows)]
        })

        start = time.time()
        result = df['col1'] + df['col3']

        elapsed = time.time() - start
        print(f"  - {num_rows} linhas processadas vetorizadamente")
        return elapsed

    # ====== TESTES DE MATCHING ======

    def test_matching_produtos(self):
        """Testa performance de matching de produtos"""
        session = get_session()

        # Busca produtos e itens
        produtos = session.query(Produto).all()
        itens = session.query(ItemLicitacao).limit(100).all()

        if not produtos or not itens:
            print("  - Sem dados para testar matching")
            session.close()
            return 0

        start = time.time()

        # Simula matching (lógica similar ao dashboard)
        from rapidfuzz import fuzz
        import unicodedata

        def normalize_text(texto):
            if not texto:
                return ""
            return unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('ASCII').upper()

        matches = 0
        for item in itens:
            item_norm = normalize_text(item.descricao or "")
            best_score = 0

            for prod in produtos:
                keywords = [k.strip() for k in prod.palavras_chave.split(',') if k.strip()]
                keywords.append(prod.nome)

                for kw in keywords:
                    kw_norm = normalize_text(kw)
                    score = fuzz.token_set_ratio(kw_norm, item_norm)
                    if score > best_score:
                        best_score = score

            if best_score >= 75:
                matches += 1

        elapsed = time.time() - start
        session.close()

        print(f"  - {len(itens)} itens comparados com {len(produtos)} produtos")
        print(f"  - {matches} matches encontrados")
        return elapsed

    # ====== TESTES DE PARSING DE EXCEL ======

    def test_excel_parsing(self):
        """Testa parsing de arquivo Excel (se existir)"""
        # Procura arquivo de teste
        test_files = list(Path(BASE_DIR / 'data').glob('*.xlsx'))

        if not test_files:
            print("  - Nenhum arquivo Excel encontrado para teste")
            return 0

        test_file = test_files[0]
        print(f"  - Testando com: {test_file.name}")

        start = time.time()

        parser = ExtratoBBParser()
        resultado = parser.parse_arquivo(str(test_file))

        elapsed = time.time() - start

        print(f"  - {resultado['total_lancamentos']} lançamentos parseados")
        print(f"  - {len(resultado['erros'])} erros encontrados")
        return elapsed

    # ====== RELATÓRIO ======

    def print_report(self):
        """Imprime relatório consolidado"""
        print("\n\n" + "="*60)
        print("RELATÓRIO DE PERFORMANCE")
        print("="*60)

        df = pd.DataFrame(self.results)

        # Ordena por tempo decrescente
        df = df.sort_values('tempo_segundos', ascending=False)

        print("\nTestes ordenados por tempo (mais lentos primeiro):\n")
        for idx, row in df.iterrows():
            print(f"{row['status']} {row['teste']:<45} {row['tempo_segundos']:>8.4f}s")
            if row['erro']:
                print(f"   Erro: {row['erro']}")

        print("\n" + "="*60)
        print("ANÁLISE E RECOMENDAÇÕES")
        print("="*60)

        # Compara iterrows vs apply vs vectorized
        iterrows_time = df[df['teste'].str.contains('iterrows', na=False)]['tempo_segundos'].values
        apply_time = df[df['teste'].str.contains('apply', na=False)]['tempo_segundos'].values
        vector_time = df[df['teste'].str.contains('vectorized', na=False)]['tempo_segundos'].values

        if len(iterrows_time) > 0 and len(vector_time) > 0:
            speedup_iter = iterrows_time[0] / vector_time[0]
            print(f"\n[COMPARACAO PANDAS - 1000 linhas]:")
            print(f"  - iterrows: {iterrows_time[0]:.4f}s (baseline)")
            if len(apply_time) > 0:
                speedup_apply = iterrows_time[0] / apply_time[0]
                print(f"  - apply: {apply_time[0]:.4f}s ({speedup_apply:.1f}x mais rapido)")
            print(f"  - vectorizado: {vector_time[0]:.4f}s ({speedup_iter:.1f}x mais rapido)")

        # Compara iterrows vs vectorizado para 10k linhas
        iterrows_10k = df[df['teste'].str.contains('10k linhas', na=False) & df['teste'].str.contains('iterrows', na=False)]['tempo_segundos'].values
        vector_10k = df[df['teste'].str.contains('10k linhas', na=False) & df['teste'].str.contains('vectorizado', na=False)]['tempo_segundos'].values

        if len(iterrows_10k) > 0 and len(vector_10k) > 0:
            speedup_10k = iterrows_10k[0] / vector_10k[0]
            print(f"\n[COMPARACAO PANDAS - 10000 linhas]:")
            print(f"  - iterrows: {iterrows_10k[0]:.4f}s")
            print(f"  - vectorizado: {vector_10k[0]:.4f}s ({speedup_10k:.1f}x mais rapido)")
            print(f"\n>>> CONCLUSAO: Operacoes vetorizadas sao {speedup_10k:.0f}x mais rapidas!")
            print(f">>> Se o sistema processa 10.000 linhas com iterrows, esta perdendo {iterrows_10k[0]-vector_10k[0]:.2f}s")

        print("\n[RECOMENDACOES]:")
        print("  1. Substituir .iterrows() por operações vetorizadas")
        print("  2. Adicionar índices nas colunas mais consultadas do BD")
        print("  3. Usar caching para resultados de matching frequentes")
        print("  4. Implementar paginação em tabelas grandes no Streamlit")
        print("  5. Usar lazy loading para dados relacionados (itens, produtos)")


def main():
    """Executa bateria de testes"""
    tester = PerformanceTest()

    print("TESTE DE PERFORMANCE - SISTEMA DE LICITAÇÕES")
    print(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Testes de Banco de Dados
    tester.time_test(
        "Query Licitações (sem otimização)",
        tester.test_query_licitacoes_sem_indice
    )

    tester.time_test(
        "Query Licitações com Itens (joins)",
        tester.test_query_com_joins
    )

    tester.time_test(
        "Query Extratos Financeiros",
        tester.test_query_extrato_financeiro
    )

    # Testes de Pandas
    print("\n\nCOMPARANDO MÉTODOS PANDAS (1000 linhas):")

    tester.time_test(
        "Pandas iterrows() - LENTO",
        tester.test_pandas_iterrows,
        1000
    )

    tester.time_test(
        "Pandas apply() - MÉDIO",
        tester.test_pandas_apply,
        1000
    )

    tester.time_test(
        "Pandas vetorizado - RÁPIDO",
        tester.test_pandas_vectorized,
        1000
    )

    # Testes com mais dados
    print("\n\nCOMPARANDO MÉTODOS PANDAS (10000 linhas):")

    tester.time_test(
        "Pandas iterrows() - 10k linhas",
        tester.test_pandas_iterrows,
        10000
    )

    tester.time_test(
        "Pandas vetorizado - 10k linhas",
        tester.test_pandas_vectorized,
        10000
    )

    # Testes de Matching
    tester.time_test(
        "Matching de Produtos (100 itens)",
        tester.test_matching_produtos
    )

    # Testes de Excel
    tester.time_test(
        "Parsing de Arquivo Excel",
        tester.test_excel_parsing
    )

    # Relatório final
    tester.print_report()


if __name__ == '__main__':
    main()
