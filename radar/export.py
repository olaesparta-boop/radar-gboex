"""
Gera o data.json que alimenta o dashboard.

Faz as agregações que o painel precisa: totais, série temporal, distribuição
por canal e por sentimento, principais veículos e lista de menções.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import config


def _day(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).astimezone(timezone.utc).strftime("%Y-%m-%d")
    except Exception:
        return iso[:10]


def _clean_social(external: list[dict]) -> list[dict]:
    """Higieniza a voz de terceiros das redes: descarta posts sem texto e limita
    o nº de posts por autor em channel='social' (evita flooding de corretor/loja).
    Notícias e Reclame Aqui não são limitados."""
    cap = getattr(config, "SOCIAL_MAX_PER_AUTHOR", 3)

    def _empty_placeholder(r):
        # posts sociais sem texto E com título-placeholder ("Menção no instagram")
        # não são menção útil; avaliações ("Avaliação: Recomenda") são preservadas
        if r["channel"] != "social" or (r.get("text") or "").strip():
            return False
        t = (r.get("title") or "").strip().lower()
        return not t or t.startswith("menção no") or t.startswith("mencao no")

    external = [r for r in external if not _empty_placeholder(r)]
    # cap por autor só no social; mais recentes primeiro
    external.sort(key=lambda r: r.get("published_at") or "", reverse=True)
    seen: dict[tuple, int] = {}
    kept = []
    for r in external:
        if r["channel"] != "social":
            kept.append(r); continue
        author = (r.get("author") or "").strip().lower()
        if not author:
            kept.append(r); continue
        key = (r["source"], author)
        seen[key] = seen.get(key, 0) + 1
        if seen[key] <= cap:
            kept.append(r)
    return kept


def build_payload(rows: list[dict], apify: dict | None = None) -> dict:
    # apenas voz de terceiros conta para reputação; canais próprios ficam de fora
    external = _clean_social(
        [r for r in rows if not r["is_owned"] and r["channel"] != "indicador"])
    # ids que sobreviveram à higienização (p/ filtrar a lista de menções também)
    ext_ids = {r["id"] for r in external}

    by_channel = Counter(r["channel"] for r in external)
    by_sentiment = Counter(r["sentiment"] for r in external)
    by_source = Counter((r["author"] or r["domain"] or r["source"]) for r in external)

    # separação POR FONTE (campo source): cada fonte com volume e sentimento
    by_source_detail: dict[str, dict] = {}
    for r in external:
        s = r["source"]
        d = by_source_detail.setdefault(
            s, {"total": 0, "positivo": 0, "neutro": 0, "negativo": 0})
        d["total"] += 1
        d[r["sentiment"]] = d.get(r["sentiment"], 0) + 1
    # ordena por volume
    by_source_detail = dict(
        sorted(by_source_detail.items(), key=lambda kv: kv[1]["total"], reverse=True))

    # série temporal (últimos 30 dias) com volume e sentimento
    daily = defaultdict(lambda: {"total": 0, "positivo": 0, "neutro": 0, "negativo": 0})
    for r in external:
        d = daily[_day(r["published_at"])]
        d["total"] += 1
        d[r["sentiment"]] = d.get(r["sentiment"], 0) + 1
    timeline = [{"date": k, **v} for k, v in sorted(daily.items())]

    # score de reputação, se o Reclame Aqui trouxe
    ra_score = next((r for r in rows if r["channel"] == "indicador"), None)

    total = len(external)
    neg = by_sentiment.get("negativo", 0)
    pos = by_sentiment.get("positivo", 0)
    # índice de sentimento líquido (-100 a +100)
    net = round(((pos - neg) / total) * 100, 1) if total else 0.0

    # tabela: terceiros que sobreviveram à higienização + canais próprios/indicador
    kept_rows = [r for r in rows
                 if r["id"] in ext_ids or r["is_owned"] or r["channel"] == "indicador"]
    recent = sorted(kept_rows, key=lambda r: r["published_at"], reverse=True)[:500]

    return {
        "brand": config.BRAND,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "lookback_days": config.LOOKBACK_DAYS,
        "kpis": {
            "total_mentions": total,
            "positivo": pos,
            "neutro": by_sentiment.get("neutro", 0),
            "negativo": neg,
            "net_sentiment": net,
            "sources": len(by_source),
            "ra_score": ra_score["title"] if ra_score else None,
        },
        "by_channel": dict(by_channel),
        "by_sentiment": dict(by_sentiment),
        "by_source_detail": by_source_detail,
        "top_sources": by_source.most_common(12),
        "timeline": timeline,
        "mentions": recent,
        # consumo do crédito Apify (None quando não há token): alimenta o
        # medidor no painel. Ver radar/apify_usage.py
        "apify": apify,
    }


def write(rows: list[dict], path: Path | None = None,
          apify: dict | None = None) -> Path:
    path = path or config.DATA_JSON
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    # quem regenera o data.json sem consultar o Apify (ex.: reclassify_sentiment)
    # não deve apagar o medidor: mantém a última leitura conhecida
    if apify is None and Path(path).exists():
        try:
            apify = json.loads(Path(path).read_text(encoding="utf-8")).get("apify")
        except Exception:
            apify = None
    payload = build_payload(rows, apify=apify)
    Path(path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return Path(path)
