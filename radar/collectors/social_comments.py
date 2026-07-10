"""
Collector: comentários em Instagram e YouTube (voz de terceiros).

Mesma estratégia do facebook.py, generalizada: para cada rede com perfil oficial
do GBOEX, pega os posts/vídeos recentes e depois os COMENTÁRIOS neles. Cada
comentário de um terceiro vira uma menção (channel="social") com sentimento.

É onde está o volume real: para marca nichada, comentário no perfil oficial rende
muito mais que busca por hashtag/keyword.

Config em config.SOCIAL_COMMENTS. Não aplica o filtro REQUIRE_TERMS: o contexto
(perfil oficial do GBOEX) já garante relevância; um "péssimo atendimento" sem a
palavra "GBOEX" é justamente o que queremos.
"""
from __future__ import annotations

import json

import requests

import config
from ..models import Mention
from .base import to_iso, domain_of

RUN = ("https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items"
       "?token={token}&timeout=230&memory=1024")

_TEXT_KEYS = ("text", "comment", "commentText", "content", "message")
_AUTHOR_KEYS = ("ownerUsername", "author", "authorName", "username", "userName",
                "name", "user", "channelName")
_URL_KEYS = ("commentUrl", "url", "postUrl", "videoUrl", "permalink")
_DATE_KEYS = ("timestamp", "date", "commentedDate", "publishedTimeText",
              "createTime", "createdAt", "time")


def _run(actor: str, run_input: dict) -> list[dict]:
    if not config.APIFY_TOKEN:
        return []
    url = RUN.format(actor=actor.replace("/", "~"), token=config.APIFY_TOKEN)
    try:
        r = requests.post(url, json=run_input, timeout=250)
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else data.get("items", [])
    except (requests.RequestException, json.JSONDecodeError, ValueError):
        return []


def _first(item: dict, keys) -> str:
    for k in keys:
        v = item.get(k)
        if isinstance(v, dict):
            v = v.get("name") or v.get("text") or v.get("title") or v.get("url")
        if v:
            return str(v)
    return ""


def _is_brand(author: str) -> bool:
    h = author.lower().lstrip("@").replace(" ", "")
    return any(x == h or x in h for x in config.OWNED_SOCIAL_HANDLES)


def _comment_to_mention(platform: str, c: dict) -> Mention | None:
    text = _first(c, _TEXT_KEYS).strip()
    if not text:
        return None
    author = _first(c, _AUTHOR_KEYS).strip()
    if _is_brand(author):            # marca respondendo != terceiro
        return None
    url = _first(c, _URL_KEYS)
    return Mention(
        source=platform, channel="social",
        title=text[:180] + ("…" if len(text) > 180 else ""),
        text=text, author=author or f"usuário do {platform}",
        url=url or f"https://{platform}.com",
        domain=domain_of(url) or f"{platform}.com",
        published_at=to_iso(_first(c, _DATE_KEYS)),
    )


def _collect_instagram(cfg: dict) -> list[Mention]:
    # 1) posts do perfil oficial
    posts = _run(cfg["posts_actor"], {
        "directUrls": [cfg["profile_url"]],
        "resultsType": "posts",
        "resultsLimit": cfg["posts_limit"],
    })
    post_urls = [p.get("url") for p in posts
                 if isinstance(p, dict) and p.get("url")]
    if not post_urls:
        return []
    # 2) comentários nesses posts
    comments = _run(cfg["comments_actor"], {
        "directUrls": post_urls,
        "resultsLimit": cfg["comments_limit"],
    })
    out = []
    for c in comments:
        if isinstance(c, dict):
            m = _comment_to_mention("instagram", c)
            if m:
                out.append(m)
    return out


def _collect_youtube(cfg: dict) -> list[Mention]:
    # 1) vídeos da marca (mantém os do canal oficial GBOEX)
    videos = _run(cfg["posts_actor"], {
        "searchQueries": [cfg["search"]],
        "maxResults": cfg["posts_limit"],
        "maxResultsShorts": 0,
    })
    video_urls = []
    for v in videos:
        if not isinstance(v, dict):
            continue
        ch = str(v.get("channelName") or v.get("channelTitle") or "")
        url = v.get("url") or v.get("videoUrl")
        if url and _is_brand(ch):     # só vídeos do canal oficial
            video_urls.append(url)
    if not video_urls:
        # fallback: qualquer vídeo sobre a marca
        video_urls = [v.get("url") for v in videos
                      if isinstance(v, dict) and v.get("url")][:cfg["posts_limit"]]
    if not video_urls:
        return []
    # 2) comentários nesses vídeos
    comments = _run(cfg["comments_actor"], {
        "startUrls": [{"url": u} for u in video_urls],
        "maxComments": cfg["comments_limit"],
        "sortCommentsBy": "NEWEST_FIRST",
    })
    out = []
    for c in comments:
        if isinstance(c, dict):
            m = _comment_to_mention("youtube", c)
            if m:
                out.append(m)
    return out


_HANDLERS = {
    "instagram": _collect_instagram,
    "youtube": _collect_youtube,
}


def collect() -> list[Mention]:
    if not config.APIFY_TOKEN:
        return []
    out: list[Mention] = []
    for platform, cfg in config.SOCIAL_COMMENTS.items():
        if not cfg.get("enabled"):
            continue
        handler = _HANDLERS.get(platform)
        if not handler:
            continue
        try:
            out.extend(handler(cfg))
        except Exception:
            pass  # uma rede falhar não derruba as outras
    return out


if __name__ == "__main__":
    res = collect()
    print(f"{len(res)} comentários (terceiros) coletados")
    for m in res[:12]:
        print(m.source, "|", (m.author or "?")[:18], "|", m.title[:54])
