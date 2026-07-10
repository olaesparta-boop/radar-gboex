"""
Collector: redes sociais via Apify (menções de TERCEIROS à marca GBOEX).

Foco: o que o público/clientes/corretores falam sobre o GBOEX no Instagram,
TikTok, X/Twitter, YouTube, Reddit, Facebook — NÃO o que o GBOEX publica.

Como funciona:
  • Para cada plataforma habilitada em config.APIFY_ENABLED_PLATFORMS, roda o
    actor correspondente (config.APIFY_ACTORS) buscando o termo "GBOEX".
  • Cada actor tem input/output próprios; aqui há um builder de input por
    plataforma e um normalizador tolerante (tenta vários nomes de campo).
  • Sem APIFY_TOKEN, o collector é simplesmente pulado (retorna []).

Trocar de actor é só editar config.APIFY_ACTORS — o resto continua valendo,
desde que os campos de saída sejam parecidos (texto, url, autor, data).
"""
from __future__ import annotations

import json
from typing import Any

import requests

import config
from ..models import Mention
from .base import to_iso, domain_of, looks_relevant

RUN_SYNC = ("https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items"
            "?token={token}&timeout=180&memory=1024")

# termo de busca principal para as redes (sem aspas, que alguns actors não aceitam)
_TERM = config.BRAND


def _run_actor(actor_id: str, run_input: dict) -> list[dict]:
    if not config.APIFY_TOKEN:
        return []
    url = RUN_SYNC.format(actor=actor_id.replace("/", "~"), token=config.APIFY_TOKEN)
    try:
        r = requests.post(url, json=run_input, timeout=200)
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else data.get("items", [])
    except (requests.RequestException, json.JSONDecodeError, ValueError):
        return []


# --- inputs por plataforma (ajuste conforme o actor que você usar) ------------
def _input_for(platform: str) -> dict:
    n = config.APIFY_MAX_ITEMS
    if platform == "instagram":
        # instagram-hashtag-scraper: posts das hashtags da marca (com legenda)
        tags = getattr(config, "INSTAGRAM_HASHTAGS", [config.BRAND.lower()])
        return {"hashtags": tags, "resultsType": "posts", "resultsLimit": n}
    if platform == "tiktok":
        return {"searchQueries": [_TERM], "resultsPerPage": n,
                "shouldDownloadVideos": False, "shouldDownloadCovers": False}
    if platform == "twitter":
        return {"searchTerms": [_TERM], "maxItems": n, "sort": "Latest",
                "tweetLanguage": "pt"}
    if platform == "youtube":
        return {"searchQueries": [_TERM], "maxResults": n, "maxResultsShorts": 0}
    if platform == "facebook":
        return {"searchQuery": _TERM, "maxPosts": n}
    if platform == "reddit":
        return {"searches": [_TERM], "searchPosts": True, "searchComments": True,
                "sort": "new", "maxItems": n, "skipComments": False}
    return {"search": _TERM, "maxItems": n}


# --- normalização de saída (tolerante a diferentes actors) --------------------
_TEXT_KEYS = ("text", "caption", "content", "title", "description", "body",
              "fullText", "postText", "message", "snippet")
_URL_KEYS = ("url", "postUrl", "link", "tweetUrl", "videoUrl", "permalink",
             "webVideoUrl")
_AUTHOR_KEYS = ("ownerUsername", "authorName", "author", "username", "userName",
                "channelName", "user", "handle", "ownerFullName")
_DATE_KEYS = ("timestamp", "createdAt", "date", "publishedAt", "createTime",
              "created_utc", "postedAtTimestamp", "time", "uploadDate")


def _first(item: dict, keys: tuple[str, ...]) -> Any:
    for k in keys:
        v = item.get(k)
        if isinstance(v, dict):  # às vezes autor vem aninhado
            v = v.get("name") or v.get("username") or v.get("title")
        if v:
            return v
    return ""


def _normalize(platform: str, item: dict, require_term: bool = True) -> Mention | None:
    text = str(_first(item, _TEXT_KEYS)).strip()
    url = str(_first(item, _URL_KEYS)).strip()
    if not text:                     # sem legenda não é menção útil (descarta)
        return None
    blob = f"{text}"
    # require_term=True: exige a marca no texto (busca por keyword pode trazer lixo).
    # require_term=False: contexto (hashtag/marcação da marca) já garante relevância.
    if require_term:
        if config.BRAND.lower() not in blob.lower():
            return None
        if not looks_relevant(blob):
            return None
    author = str(_first(item, _AUTHOR_KEYS)).strip()
    date = _first(item, _DATE_KEYS)
    title = text[:180] + ("…" if len(text) > 180 else "")
    # conta oficial do GBOEX? então é contexto, não voz de terceiro
    handle = author.lower().lstrip("@").replace(" ", "")
    owned = any(h == handle or h in handle for h in config.OWNED_SOCIAL_HANDLES)
    return Mention(
        source=platform,
        channel="canal_proprio" if owned else "social",
        title=title or f"Menção no {platform}",
        url=url or f"https://{platform}.com",
        text=text,
        author=author,
        domain=domain_of(url),
        published_at=to_iso(date),
        is_owned=owned,
    )


def _collect_instagram_tagged() -> list[Mention]:
    """Posts que MARCAM o perfil oficial (@gboex_oficial) — voz de terceiros
    que cita a marca sem usar a hashtag exata. Contexto garante relevância."""
    cfg = getattr(config, "INSTAGRAM_TAGGED", None)
    if not cfg or not cfg.get("enabled"):
        return []
    items = _run_actor(cfg["actor"], {
        "username": [cfg["profile"]], "resultsLimit": cfg.get("limit", 40)})
    out = []
    for it in items:
        if isinstance(it, dict):
            m = _normalize("instagram", it, require_term=False)
            if m:
                out.append(m)
    return out


def collect() -> list[Mention]:
    if not config.APIFY_TOKEN:
        return []
    out: list[Mention] = []
    for platform in config.APIFY_ENABLED_PLATFORMS:
        actor = config.APIFY_ACTORS.get(platform)
        if not actor:
            continue
        items = _run_actor(actor, _input_for(platform))
        # no Instagram o contexto é hashtag da marca → não exige termo no texto
        req = platform != "instagram"
        for it in items:
            if not isinstance(it, dict):
                continue
            m = _normalize(platform, it, require_term=req)
            if m:
                out.append(m)
    # Instagram: posts que marcam o perfil oficial (além das hashtags)
    try:
        out.extend(_collect_instagram_tagged())
    except Exception:
        pass  # falha na marcação não derruba o resto
    return out


if __name__ == "__main__":
    res = collect()
    print(f"{len(res)} menções sociais via Apify")
    for m in res[:10]:
        print(m.source, "|", m.author, "|", m.title)
