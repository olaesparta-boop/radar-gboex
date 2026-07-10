"""
Collector: LinkedIn — posts de terceiros que mencionam o GBOEX.

Ao contrário de Facebook/Instagram, a página oficial do GBOEX no LinkedIn quase
não recebe comentários (testado jul/2026: ~3 comentários em 15 posts). A voz de
terceiros no LinkedIn está em POSTS de outras pessoas/empresas que citam a marca:
funcionários ("completei 1 ano no GBOEX"), parceiros, ex-alunos, agências, etc.

Por isso a estratégia aqui é BUSCA por keyword ("GBOEX"), não comentários. Cada
resultado vira uma menção (source="linkedin"). Posts da própria conta oficial são
marcados como canal_proprio (contexto); o resto é voz de terceiros (channel=social).

Config em config.LINKEDIN. Actor sem cookie (harvestapi~linkedin-post-search).
Não aplica REQUIRE_TERMS: a própria busca por "GBOEX" já garante a relevância
(um "completei 1 ano nessa empresa" citando o GBOEX é o que queremos capturar).
"""
from __future__ import annotations

import json

import requests

import config
from ..models import Mention
from .base import to_iso, domain_of, _norm

RUN = ("https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items"
       "?token={token}&timeout=280&memory=1024")

_TEXT_KEYS = ("content", "text", "commentary", "message", "description")
_AUTHOR_KEYS = ("author", "authorName", "actorName", "name", "username")
_URL_KEYS = ("linkedinUrl", "shareLinkedinUrl", "url", "postUrl", "permalink", "link")
_DATE_KEYS = ("postedAt", "createdAt", "publishedAt", "date", "time", "timestamp")


def _run(actor: str, run_input: dict) -> list[dict]:
    if not config.APIFY_TOKEN:
        return []
    url = RUN.format(actor=actor.replace("/", "~"), token=config.APIFY_TOKEN)
    try:
        r = requests.post(url, json=run_input, timeout=300)
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else data.get("items", [])
    except (requests.RequestException, json.JSONDecodeError, ValueError):
        return []


def _first(item: dict, keys) -> str:
    """Primeiro valor não-vazio; se for dict, tenta chaves usuais (nome/data/url)."""
    for k in keys:
        v = item.get(k)
        if isinstance(v, dict):
            v = (v.get("name") or v.get("text") or v.get("title")
                 or v.get("url") or v.get("date") or v.get("timestamp"))
        if v:
            return str(v)
    return ""


def _is_brand(author: str) -> bool:
    h = author.lower().lstrip("@").replace(" ", "")
    return any(x == h or x in h for x in config.OWNED_SOCIAL_HANDLES) or "gboex" in h


def _post_to_mention(p: dict) -> Mention | None:
    text = _first(p, _TEXT_KEYS).strip()
    if not text:
        return None
    author = _first(p, _AUTHOR_KEYS).strip()
    owned = _is_brand(author)
    # a busca por "GBOEX" já garante relevância; só barramos ruído explícito
    # (NEGATIVE_FILTERS) — não exigimos "gboex" literal no texto, pois muitos
    # posts de terceiros citam a marca via marcação da empresa, não no corpo.
    blob = _norm(text + " " + author)
    if any(_norm(bad) in blob for bad in config.NEGATIVE_FILTERS):
        return None
    url = _first(p, _URL_KEYS)
    return Mention(
        source="linkedin",
        channel="canal_proprio" if owned else "social",
        is_owned=owned,
        title=text[:180] + ("…" if len(text) > 180 else ""),
        text=text,
        author="GBOEX (oficial)" if owned else (author or "usuário do LinkedIn"),
        url=url or config.LINKEDIN["company_url"],
        domain=domain_of(url) or "linkedin.com",
        published_at=to_iso(_first(p, _DATE_KEYS)),
    )


def collect() -> list[Mention]:
    cfg = config.LINKEDIN
    if not config.APIFY_TOKEN or not cfg.get("enabled"):
        return []
    posts = _run(cfg["search_actor"], {
        "searchQueries": [cfg["search"]],
        "maxPosts": cfg["posts_limit"],
        "sortBy": "date",
    })
    out: list[Mention] = []
    for p in posts:
        if isinstance(p, dict):
            m = _post_to_mention(p)
            if m:
                out.append(m)
    return out


if __name__ == "__main__":
    res = collect()
    ext = [m for m in res if not m.is_owned]
    print(f"{len(res)} posts LinkedIn ({len(ext)} de terceiros, "
          f"{len(res) - len(ext)} da conta oficial)")
    for m in res[:15]:
        tag = "oficial" if m.is_owned else "terceiro"
        print(f"  [{tag}] {(m.author or '?')[:24]:24} | {m.title[:52]}")
