import sys
import json
import os
import time
from collections import Counter
from datetime import datetime
import argparse

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from modules.scrapers.pncp_client import PNCPClient


def main():
    client = PNCPClient()
    parser = argparse.ArgumentParser()
    parser.add_argument("--dias", type=int, default=60)
    parser.add_argument("--estados", type=str, default="RN,PB,PE,AL")
    parser.add_argument("--max-por-combo", type=int, default=50)
    parser.add_argument("--max-paginas-por-combo", type=int, default=10)
    parser.add_argument("--page-workers", type=int, default=2)
    args = parser.parse_args()

    estados = [s.strip().upper() for s in args.estados.split(",") if s.strip()]
    dias_busca = int(args.dias)
    max_por_combo = int(args.max_por_combo)
    max_paginas_por_combo = int(args.max_paginas_por_combo)
    page_workers = int(args.page_workers)

    print("PNCP diagnóstico")
    print("MAX_PAGINAS:", client.MAX_PAGINAS)
    print("dias_busca:", dias_busca)
    print("estados:", estados)
    print("max_por_combo:", max_por_combo)
    print("max_paginas_por_combo:", max_paginas_por_combo)
    print("page_workers:", page_workers)
    print("positivos:", len(client.TERMOS_POSITIVOS_PADRAO))
    print("negativos:", len(client.TERMOS_NEGATIVOS_PADRAO))
    print("prioritarios:", len(client.TERMOS_PRIORITARIOS))

    started = time.time()
    resultados = client.buscar_oportunidades(
        dias_busca=dias_busca,
        estados=estados,
        termos_positivos=client.TERMOS_POSITIVOS_PADRAO,
        termos_negativos=None,
        apenas_abertas=True,
        max_por_combo=max_por_combo,
        max_paginas_por_combo=max_paginas_por_combo,
        page_workers=page_workers,
    )
    elapsed = time.time() - started

    by_uf = Counter(r.get("uf") for r in resultados)
    by_mod = Counter(r.get("modalidade") for r in resultados)
    by_motivo = Counter(r.get("motivo_aprovacao") for r in resultados)

    print("\n=== RESULTADO ===")
    print("Aprovadas:", len(resultados))
    print("Tempo (s):", round(elapsed, 1))
    print("Por UF:", dict(by_uf))
    print("Por modalidade:", dict(by_mod))
    print("Top motivos:", by_motivo.most_common(10))

    print("\nAmostra (até 15):")
    for r in resultados[:15]:
        print(
            "-",
            r.get("pncp_id"),
            r.get("uf"),
            r.get("modalidade"),
            "dias_restantes=",
            r.get("dias_restantes"),
            "|",
            (r.get("objeto") or "")[:120],
        )

    out_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    out_dir = os.path.abspath(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"diagnostico_pncp_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    payload = {
        "generated_at": datetime.now().isoformat(),
        "dias_busca": dias_busca,
        "estados": estados,
        "max_paginas": client.MAX_PAGINAS,
        "count": len(resultados),
        "by_uf": dict(by_uf),
        "by_modalidade": dict(by_mod),
        "top_motivos": by_motivo.most_common(50),
        "results": resultados,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print("\nJSON salvo em:", out_path)


if __name__ == "__main__":
    main()
