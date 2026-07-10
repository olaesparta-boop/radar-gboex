"""
Collector: site/blog do GBOEX (WordPress RSS).

Estas são publicações do PRÓPRIO GBOEX. Servem de CONTEXTO: ajudam a
entender a que uma menção externa está reagindo (ex.: campanha, aniversário).
São marcadas como canal_proprio (is_owned=True) e não contam como "voz de
terceiros" nas métricas de reputação.
"""
from __future__ import annotations

import feedparser

from ..models import Mention
from .base import http_get, domain_of, to_iso

FEED = "https://www.gboex.com.br/feed/"


def collect() -> list[Mention]:
    resp = http_get(FEED)
    if not resp:
        return []
    feed = feedparser.parse(resp.content)
    out: list[Mention] = []
    for e in feed.entries:
        link = e.get("link", "")
        if not link:
            continue
        out.append(Mention(
            source="gboex_site",
            channel="canal_proprio",
            title=e.get("title", "").strip(),
            url=link,
            text=e.get("summary", ""),
            author="GBOEX (oficial)",
            domain=domain_of(link),
            published_at=to_iso(e.get("published")),
            is_owned=True,
        ))
    return out


if __name__ == "__main__":
    for m in collect():
        print(m.published_at, "|", m.title)
