"""
Reclassifica o sentimento de TODAS as menções já no banco usando o analisador
atual (Claude em lote, se ANTHROPIC_API_KEY estiver setada; senão léxico) e
regenera o data.json. Use depois de ativar a chave para aplicar a IA ao histórico.

Uso:  python reclassify_sentiment.py
"""
from __future__ import annotations

import sqlite3

import config
from radar import sentiment, export


def main() -> int:
    usando_ia = bool(config.ANTHROPIC_API_KEY)
    print(f"Reclassificando sentimento — modo: {'IA (Claude)' if usando_ia else 'LÉXICO (sem chave)'}")
    if not usando_ia:
        print("  ⚠️  ANTHROPIC_API_KEY vazia — sem IA não há ganho. Preencha o .env primeiro.")

    conn = sqlite3.connect(str(config.DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute("SELECT id, title, text FROM mentions")]
    print(f"  {len(rows)} menções no banco…")

    blobs = [f"{r['title']}. {r.get('text') or ''}".strip() for r in rows]
    results = sentiment.analyze_batch(blobs)

    cur = conn.cursor()
    mudou = 0
    for r, (label, score) in zip(rows, results):
        cur.execute(
            "UPDATE mentions SET sentiment=?, sentiment_score=? WHERE id=?",
            (label, score, r["id"]),
        )
        mudou += 1
    conn.commit()

    all_rows = [dict(x) for x in conn.execute(
        "SELECT * FROM mentions ORDER BY published_at DESC")]
    conn.close()
    out = export.write(all_rows)
    print(f"  {mudou} menções reclassificadas · data.json regenerado: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
