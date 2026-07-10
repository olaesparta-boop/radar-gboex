"""Infra compartilhada pelos collectors: HTTP com headers, retry e helpers."""
from __future__ import annotations

import time
import unicodedata
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

import requests
from dateutil import parser as dateparser

import config


def http_get(url: str, *, headers: Optional[dict] = None,
             params: Optional[dict] = None, retries: int = 3) -> Optional[requests.Response]:
    """GET com User-Agent de navegador e retry simples com backoff."""
    hdrs = {"User-Agent": config.USER_AGENT,
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8"}
    if headers:
        hdrs.update(headers)
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=hdrs, params=params,
                                timeout=config.REQUEST_TIMEOUT)
            if resp.status_code == 429:
                time.sleep(2 * (attempt + 1))
                continue
            resp.raise_for_status()
            return resp
        except requests.RequestException:
            if attempt == retries - 1:
                return None
            time.sleep(1.5 * (attempt + 1))
    return None


def domain_of(url: str) -> str:
    try:
        net = urlparse(url).netloc.lower()
        return net[4:] if net.startswith("www.") else net
    except Exception:
        return ""


def is_owned(url: str) -> bool:
    dom = domain_of(url)
    return any(dom == d or dom.endswith("." + d) for d in config.OWNED_DOMAINS)


def to_iso(value) -> str:
    """Converte data em vários formatos para ISO-8601 UTC. Cai em 'agora' se falhar."""
    if not value:
        return datetime.now(timezone.utc).isoformat()
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()
        dt = dateparser.parse(str(value))
        if dt is None:
            raise ValueError
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except Exception:
        return datetime.now(timezone.utc).isoformat()


def _norm(text: str) -> str:
    text = "".join(
        c for c in unicodedata.normalize("NFD", text or "")
        if unicodedata.category(c) != "Mn"
    )
    return text.lower()


def mentions_brand(text: str) -> bool:
    """
    True só se o texto realmente cita a marca (algum termo de REQUIRE_TERMS).
    É o filtro que barra falso-positivo tipo notícias 'parecidas' que o buscador
    devolve mas que não falam do GBOEX.
    """
    low = _norm(text)
    return any(term in low for term in config.REQUIRE_TERMS)


def looks_relevant(text: str) -> bool:
    """Aceita a menção: cita a marca E não bate em NEGATIVE_FILTERS."""
    low = _norm(text)
    if any(_norm(bad) in low for bad in config.NEGATIVE_FILTERS):
        return False
    return mentions_brand(text)
