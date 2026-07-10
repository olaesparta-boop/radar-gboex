"""
Collector: Reclame Aqui.

O HTML público bloqueia scraping (403/Cloudflare), então usamos a API interna
que o próprio site consome (iosite.reclameaqui.com.br). Ela não é documentada
e pode mudar; por isso o collector é DEFENSIVO: qualquer falha => retorna [].

Traz duas coisas:
  • a nota/score de reputação (uma "menção" sintética do tipo indicador);
  • as reclamações recentes como menções negativas (channel="reclamacao").

Fallback: se a API interna falhar e houver APIFY_TOKEN, o apify_social pode
rodar um actor de Reclame Aqui (configurável). Ver README.
"""
from __future__ import annotations

from datetime import datetime, timezone

import config
from ..models import Mention
from .base import http_get, to_iso

SHORTNAME = "gboex"
IOSITE = "https://iosite.reclameaqui.com.br/raichu-io-site-search-v1"

# headers que o front do RA envia; sem eles a API responde 403
_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://www.reclameaqui.com.br",
    "Referer": "https://www.reclameaqui.com.br/",
}


def _company() -> dict | None:
    resp = http_get(f"{IOSITE}/company/shortname/{SHORTNAME}", headers=_HEADERS)
    if not resp:
        return None
    try:
        return resp.json()
    except Exception:
        return None


def _score_mention(company: dict) -> Mention | None:
    # o payload varia; tentamos os campos mais comuns
    score = (company.get("companyReputation", {}) or {}).get("finalScore") \
        or company.get("finalScore") or company.get("score")
    if score is None:
        return None
    try:
        score = float(score)
    except (TypeError, ValueError):
        return None
    # 0-10: <5 negativo, 5-7 neutro, >7 positivo
    if score >= 7:
        sent, sscore = "positivo", 0.5
    elif score < 5:
        sent, sscore = "negativo", -0.5
    else:
        sent, sscore = "neutro", 0.0
    m = Mention(
        source="reclame_aqui",
        channel="indicador",
        title=f"Reputação no Reclame Aqui: {score:.1f}/10",
        url="https://www.reclameaqui.com.br/empresa/gboex/",
        author="Reclame Aqui",
        domain="reclameaqui.com.br",
        published_at=datetime.now(timezone.utc).isoformat(),
    )
    m.sentiment, m.sentiment_score = sent, sscore
    return m


def _complaints(company_id: str, limit: int = 30) -> list[Mention]:
    params = {"company": company_id, "page": "0", "limit": str(limit),
              "sort": "creationDate", "order": "DESC"}
    resp = http_get(f"{IOSITE}/complains/", headers=_HEADERS, params=params)
    if not resp:
        return []
    try:
        data = resp.json()
    except Exception:
        return []
    items = data.get("complains", data if isinstance(data, list) else [])
    out: list[Mention] = []
    for c in items or []:
        cid = str(c.get("id", ""))
        title = (c.get("title") or "").strip()
        if not title:
            continue
        url = f"https://www.reclameaqui.com.br/empresa/gboex/complaint/{cid}" if cid else \
              "https://www.reclameaqui.com.br/empresa/gboex/"
        out.append(Mention(
            source="reclame_aqui",
            channel="reclamacao",
            title=title,
            url=url,
            text=c.get("description", ""),
            author=c.get("userCity", "cliente"),
            domain="reclameaqui.com.br",
            published_at=to_iso(c.get("created") or c.get("creationDate")),
            raw_id=cid,
        ))
    return out


def _apify_fallback() -> list[Mention]:
    """Se a API direta cair no Cloudflare, roda um actor de RA no Apify."""
    if not config.APIFY_TOKEN:
        return []
    actor = config.APIFY_ACTORS.get("reclame_aqui")
    if not actor:
        return []
    import json
    import requests
    url = ("https://api.apify.com/v2/acts/" + actor.replace("/", "~") +
           "/run-sync-get-dataset-items?token=" + config.APIFY_TOKEN + "&timeout=180")
    payload = {
        "companies": [config.RECLAME_AQUI_SHORTNAME],
        "scrapeComplaints": True,
        "includeInteractions": False,
        "statusFilter": ["LATEST"],
        "maxComplaintsPerCompany": 40,
    }
    try:
        r = requests.post(url, json=payload, timeout=200)
        r.raise_for_status()
        items = r.json()
    except (requests.RequestException, json.JSONDecodeError, ValueError):
        return []
    if not isinstance(items, list):
        return []

    out: list[Mention] = []
    for c in items:
        if not isinstance(c, dict):
            continue
        rtype = c.get("recordType")

        if rtype == "company":
            # registro de reputação -> indicador
            score = c.get("finalScore")
            try:
                score = float(score)
            except (TypeError, ValueError):
                continue
            label = c.get("reputationLabel", "")
            c30 = c.get("complaints30Days")
            if score >= 7:
                sent, sscore = "positivo", 0.5
            elif score < 5:
                sent, sscore = "negativo", -0.5
            else:
                sent, sscore = "neutro", 0.0
            extra = f" · {label}" if label else ""
            if c30 is not None:
                extra += f" · {c30} reclamações/30d"
            m = Mention(
                source="reclame_aqui", channel="indicador",
                title=f"Reputação no Reclame Aqui: {score:.1f}/10{extra}",
                url=c.get("companyUrl", "https://www.reclameaqui.com.br/empresa/gboex/"),
                author="Reclame Aqui", domain="reclameaqui.com.br",
                published_at=to_iso(c.get("scrapedAt")),
            )
            m.sentiment, m.sentiment_score = sent, sscore
            out.append(m)
            continue

        # registro de reclamação
        title = (c.get("title") or "").strip()
        if not title:
            continue
        city = c.get("userCity", "")
        state = c.get("userState", "")
        who = ", ".join(x for x in (city, state) if x) or "cliente"
        status = c.get("statusLabel") or c.get("status") or ""
        text = (c.get("descriptionText") or c.get("description") or "").strip()
        m = Mention(
            source="reclame_aqui", channel="reclamacao",
            title=title[:180],
            url=c.get("url", "https://www.reclameaqui.com.br/empresa/gboex/"),
            text=(f"[{status}] " if status else "") + text,
            author=who, domain="reclameaqui.com.br",
            published_at=to_iso(c.get("created")),
            raw_id=str(c.get("id", "")),
        )
        # reclamação é sinal negativo por natureza; resolvidas suavizam
        if not c.get("solved"):
            m.sentiment, m.sentiment_score = "negativo", -0.5
        out.append(m)
    return out


def collect() -> list[Mention]:
    company = _company()
    if not company:
        # API direta bloqueada (Cloudflare) => tenta Apify
        return _apify_fallback()
    out: list[Mention] = []
    sm = _score_mention(company)
    if sm:
        out.append(sm)
    cid = str(company.get("id", "") or company.get("companyId", ""))
    if cid:
        out.extend(_complaints(cid))
    return out


if __name__ == "__main__":
    res = collect()
    print(f"{len(res)} itens do Reclame Aqui")
    for m in res[:10]:
        print(m.channel, "|", m.title)
