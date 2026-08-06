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

import config
from radar import pipeline, export
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

    store = Storage(config.DB_PATH)
    novas, repetidas = store.upsert_many(all_mentions)
    total_db = store.count()
    rows = store.all_rows()
    store.close()
    print(f"  {novas} novas | {repetidas} já existiam | {total_db} no total (banco)")

    out = export.write(rows)
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
