"""
Radar GBOEX — orquestrador.

Fluxo: coleta (todas as fontes) → enriquece (sentimento) →
grava no SQLite (dedup) → exporta data.json para o dashboard.

Uso:
    python main.py                 # roda tudo
    python main.py --only google_news,reclame_aqui
    python main.py --no-apify      # pula redes sociais (sem custo Apify)
"""
from __future__ import annotations

import argparse
import sys
import time
import traceback
from datetime import datetime, timezone

import config
from radar import pipeline, export, apify_usage
from radar.storage import Storage
from radar.collectors import (
    google_news, gdelt, gboex_site, reclame_aqui, apify_social, facebook,
    social_comments, linkedin,
)

COLLECTORS = {
    "google_news": google_news,
    "gdelt": gdelt,
    "gboex_site": gboex_site,
    "reclame_aqui": reclame_aqui,
    "apify_social": apify_social,
    "facebook": facebook,
    "social_comments": social_comments,
    "linkedin": linkedin,
}


def run(only: list[str] | None = None, no_apify: bool = False) -> int:
    names = only or list(COLLECTORS)
    if no_apify and "apify_social" in names:
        names.remove("apify_social")

    all_mentions = []
    # foto do consumo antes da coleta: a diferença no fim diz quanto esta
    # rodada custou (é o que alimenta o mapa de consumo do painel)
    consumo_antes = apify_usage.snapshot()
    ciclo = (consumo_antes or {}).get("ciclo_inicio")

    store = Storage(config.DB_PATH)
    gasto_ciclo = store.cycle_cost(ciclo) if ciclo else 0.0

    # verba do ciclo estourada => roda só o que é grátis até o ciclo virar
    freado = False
    if ciclo and config.BUDGET_ENFORCE and gasto_ciclo >= config.RADAR_BUDGET_USD:
        pagos = [n for n in names if n in config.PAID_COLLECTORS]
        if pagos:
            freado = True
            names = [n for n in names if n not in config.PAID_COLLECTORS]
            print(f"\n[verba] US$ {gasto_ciclo:.2f} de {config.RADAR_BUDGET_USD:.2f} "
                  f"já usados neste ciclo — pulando fontes pagas: {', '.join(pagos)}")

    print(f"\n== Radar {config.BRAND} — coleta iniciada ==\n")
    for name in names:
        mod = COLLECTORS.get(name)
        if not mod:
            print(f"  [!] collector desconhecido: {name}")
            continue
        t0 = time.time()
        try:
            got = mod.collect()
            all_mentions.extend(got)
            print(f"  [ok] {name:<14} {len(got):>4} menções  ({time.time()-t0:.1f}s)")
        except Exception:
            print(f"  [ERRO] {name}:")
            traceback.print_exc()

    if not all_mentions:
        print("\nNenhuma menção coletada. Verifique conexão/chaves.\n")

    print(f"\n== Enriquecendo {len(all_mentions)} menções (sentimento) ==")
    pipeline.enrich(all_mentions)

    novas, repetidas = store.upsert_many(all_mentions)
    total_db = store.count()
    print(f"  {novas} novas | {repetidas} já existiam | {total_db} no total (banco)")

    custo = apify_usage.custo_da_rodada(consumo_antes, apify_usage.snapshot())
    if ciclo and custo > 0:
        store.record_run_cost(
            datetime.now(timezone.utc).isoformat(), ciclo, custo)
        gasto_ciclo = store.cycle_cost(ciclo)

    # numa rodada só de fontes grátis o custo é zero: a referência do painel
    # passa a ser a última coleta paga que já foi medida
    referencia = custo if custo > 0 else store.last_run_cost()

    rows = store.all_rows()
    store.close()

    consumo = None
    if consumo_antes:
        consumo = apify_usage.painel(
            gasto_ciclo, (consumo_antes or {}).get("ciclo_fim"),
            custo_coleta_usd=referencia, freado=freado)
        print(f"  verba do ciclo: US$ {consumo['gasto_usd']:.2f} de "
              f"{consumo['orcamento_usd']:.2f} usados"
              + (f" | esta coleta: US$ {custo:.2f}" if custo else ""))

    out = export.write(rows, consumo=consumo)
    print(f"\n== data.json gerado: {out} ==")
    print("   abra o dashboard com:  python serve.py\n")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Radar GBOEX")
    ap.add_argument("--only", help="lista separada por vírgula de collectors")
    ap.add_argument("--no-apify", action="store_true", help="pula redes sociais (Apify)")
    args = ap.parse_args()
    only = [s.strip() for s in args.only.split(",")] if args.only else None
    return run(only=only, no_apify=args.no_apify)


if __name__ == "__main__":
    sys.exit(main())
