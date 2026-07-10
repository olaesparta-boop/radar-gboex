"""
Collector: Google News (via RSS de busca).

Grátis, sem chave. Cobre imprensa, portais, blogs e boa parte da web
noticiosa em PT-BR. É a espinha dorsal do radar de notícias.
"""
from __future__ import annotations

from urllib.parse import quote_plus

import feedparser

import config
from ..models import Mention
from .base import http_get, domain_of, is_owned, to_iso, looks_relevant

RSS = "https://news.google.com/rss/search?q={q}&hl=pt-BR&gl=BR&ceid=BR:pt-419"


def collect() -> list[Mention]:
    out: list[Mention] = []
    seen: set[str] = set()
    for query in config.QUERIES:
        url = RSS.format(q=quote_plus(query))
        resp = http_get(url)
        if not resp:
            continue
        feed = feedparser.parse(resp.content)
        for e in feed.entries:
            link = e.get("link", "")
            if not link or link in seen:
                continue
            seen.add(link)
            title = e.get("title", "").strip()
            summary = e.get("summary", "")
            if not looks_relevant(f"{title} {summary}"):
                continue
            # Google News costuma trazer "Título - Veículo"
            source_name = ""
            if hasattr(e, "source") and getattr(e.source, "title", ""):
                source_name = e.source.title
            elif " - " in title:
                source_name = title.rsplit(" - ", 1)[-1]

            out.append(Mention(
                source="google_news",
                channel="noticia",
                title=title,
                url=link,
                text=summary,
                author=source_name,
                domain=domain_of(link),
                published_at=to_iso(e.get("published")),
                is_owned=is_owned(link),
            ))
    return out


if __name__ == "__main__":
    for m in collect()[:10]:
        print(m.published_at, "|", m.author, "|", m.title)
