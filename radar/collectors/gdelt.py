"""
Collector: GDELT DOC 2.0 API.

Grátis, sem chave. Base global de notícias em 100+ idiomas. Para uma marca
nichada brasileira a cobertura é menor que o Google News, mas pega veículos
que o Google não indexa e serve de fonte secundária/redundante.
"""
from __future__ import annotations

import json

import config
from ..models import Mention
from .base import http_get, domain_of, is_owned, to_iso, looks_relevant

API = "https://api.gdeltproject.org/api/v2/doc/doc"


def collect() -> list[Mention]:
    out: list[Mention] = []
    seen: set[str] = set()
    # GDELT tem cobertura fraca para marcas nichadas BR e sofre rate-limit;
    # usamos só a query principal para manter a coleta rápida.
    for query in config.QUERIES[:1]:
        params = {
            "query": query.replace('"', ""),  # GDELT trata frase por proximidade
            "mode": "artlist",
            "format": "json",
            "maxrecords": "75",
            "sort": "datedesc",
            "timespan": f"{config.LOOKBACK_DAYS}d",
        }
        # GDELT sofre rate-limit agressivo; não insistimos (retries=1) para não
        # travar a coleta 70s+ numa fonte que é apenas secundária.
        resp = http_get(API, params=params, retries=1)
        if not resp:
            continue
        try:
            data = resp.json()
        except (json.JSONDecodeError, ValueError):
            continue
        for art in data.get("articles", []) or []:
            link = art.get("url", "")
            if not link or link in seen:
                continue
            seen.add(link)
            title = (art.get("title") or "").strip()
            if not looks_relevant(title):
                continue
            out.append(Mention(
                source="gdelt",
                channel="noticia",
                title=title,
                url=link,
                author=art.get("domain", ""),
                domain=domain_of(link) or art.get("domain", ""),
                language=art.get("language", "pt")[:2].lower() or "pt",
                published_at=to_iso(art.get("seendate")),
                is_owned=is_owned(link),
            ))
    return out


if __name__ == "__main__":
    for m in collect()[:10]:
        print(m.published_at, "|", m.domain, "|", m.title)
