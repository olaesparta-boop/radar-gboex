"""
Collector: Facebook (voz de terceiros na página oficial do GBOEX).

O FB não permite busca pública por palavra-chave (o actor de busca volta vazio).
A conversa real de terceiros sobre o GBOEX no Facebook está em dois lugares, ambos
na página oficial (facebook.com/GBOEXoficial):

  1. COMENTÁRIOS nos posts da página  -> elogios, reclamações, dúvidas
  2. AVALIAÇÕES/recomendações da página

Fluxo (3 actors Apify, em cadeia):
  posts da página  ──►  URLs dos posts  ──►  comentários (terceiros)
  página           ──►  avaliações (terceiros)

Importante: aqui NÃO exigimos a palavra "GBOEX" no texto — o contexto (é a página
do GBOEX) já garante relevância. Um comentário "péssimo atendimento" é justamente
o que queremos capturar. Só descartamos falas da própria marca respondendo.
"""
from __future__ import annotations

import json

import requests

import config
from ..models import Mention
from .base import to_iso

RUN = ("https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items"
       "?token={token}&timeout=230&memory=1024")

_TEXT_KEYS = ("text", "message", "commentText", "reviewText", "content")
_AUTHOR_KEYS = ("profileName", "name", "authorName", "userName", "user", "author")
_URL_KEYS = ("commentUrl", "url", "facebookUrl", "profileUrl")
_DATE_KEYS = ("date", "time", "createdTime", "timestamp", "publishedTime")


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
            v = v.get("name") or v.get("text") or v.get("url")
        if v:
            return str(v)
    return ""


def _is_brand(author: str) -> bool:
    h = author.lower().lstrip("@").replace(" ", "")
    return any(x in h for x in config.OWNED_SOCIAL_HANDLES)


def collect() -> list[Mention]:
    if not config.APIFY_TOKEN or not getattr(config, "FACEBOOK_ENABLED", False):
        return []

    out: list[Mention] = []
    A = config.FACEBOOK_ACTORS

    # 1) posts da página oficial (contexto) + coleta URLs
    posts = _run(A["posts"], {
        "startUrls": [{"url": config.FACEBOOK_PAGE_URL}],
        "resultsLimit": config.FACEBOOK_POSTS_LIMIT,
        "captionText": True,
    })
    post_urls: list[str] = []
    for p in posts:
        if not isinstance(p, dict):
            continue
        u = p.get("url") or p.get("topLevelUrl")
        if u:
            post_urls.append(u)
        txt = (p.get("text") or "").strip()
        if txt:
            out.append(Mention(
                source="facebook", channel="canal_proprio", is_owned=True,
                title=txt[:180], text=txt, author="GBOEX (oficial)",
                url=u or config.FACEBOOK_PAGE_URL, domain="facebook.com",
                published_at=to_iso(p.get("time")),
            ))

    # 2) comentários nesses posts (voz de terceiros)
    if post_urls:
        comments = _run(A["comments"], {
            "startUrls": [{"url": u} for u in post_urls],
            "resultsLimit": config.FACEBOOK_COMMENTS_LIMIT,
            "includeNestedComments": True,
            "viewOption": "RANKED_UNFILTERED",
        })
        for c in comments:
            if not isinstance(c, dict):
                continue
            text = _first(c, _TEXT_KEYS).strip()
            if not text:
                continue
            author = _first(c, _AUTHOR_KEYS).strip()
            if _is_brand(author):      # marca respondendo != voz de terceiro
                continue
            out.append(Mention(
                source="facebook", channel="social",
                title=text[:180] + ("…" if len(text) > 180 else ""),
                text=text, author=author or "usuário do Facebook",
                url=_first(c, _URL_KEYS) or config.FACEBOOK_PAGE_URL,
                domain="facebook.com",
                published_at=to_iso(_first(c, _DATE_KEYS)),
            ))

    # 3) avaliações da página (voz de terceiros)
    reviews = _run(A["reviews"], {
        "startUrls": [{"url": config.FACEBOOK_PAGE_URL}],
        "resultsLimit": config.FACEBOOK_REVIEWS_LIMIT,
    })
    for rv in reviews:
        if not isinstance(rv, dict):
            continue
        text = _first(rv, _TEXT_KEYS).strip()
        author = _first(rv, _AUTHOR_KEYS).strip()
        if not text and not author:
            continue
        # muitas avaliações trazem recomendação (positiva/negativa)
        rec = rv.get("isRecommended")
        m = Mention(
            source="facebook", channel="social",
            title=("Avaliação: " + (text[:160] if text else
                   ("Recomenda" if rec else "Não recomenda"))),
            text=text, author=author or "avaliação Facebook",
            url=_first(rv, _URL_KEYS) or config.FACEBOOK_PAGE_URL,
            domain="facebook.com",
            published_at=to_iso(_first(rv, _DATE_KEYS)),
        )
        if rec is True:
            m.sentiment, m.sentiment_score = "positivo", 0.6
        elif rec is False:
            m.sentiment, m.sentiment_score = "negativo", -0.6
        out.append(m)

    return out


if __name__ == "__main__":
    res = collect()
    print(f"{len(res)} itens do Facebook")
    for m in res[:12]:
        print(m.channel, "|", (m.author or "?")[:18], "|", m.title[:60])
