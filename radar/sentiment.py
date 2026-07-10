"""
Análise de sentimento PT-BR.

Estratégia em duas camadas:
  1. Léxico embutido (offline, sem custo, sem chave) — padrão.
  2. Se ANTHROPIC_API_KEY estiver setada, usa Claude para maior precisão.

Também detecta ALERTAS: termos que sugerem risco reputacional (golpe,
fraude, processo, não paga, etc.) — independentemente do sentimento.
"""
from __future__ import annotations

import json
import re
import unicodedata
from typing import Optional

import config

# --- léxico enxuto porém prático para o domínio (seguros/previdência) ---------
_POS = {
    "otimo", "otima", "excelente", "bom", "boa", "maravilhoso", "recomendo",
    "recomendado", "confiavel", "confianca", "satisfeito", "satisfeita",
    "parabens", "sucesso", "premio", "premiado", "cresce", "crescimento",
    "solidez", "solido", "tradicao", "seguro", "seguranca", "rapido", "agil",
    "atencioso", "gentil", "resolveu", "resolvido", "aprovado", "ajudou",
    "obrigado", "gratidao", "feliz", "amei", "adorei", "top", "eficiente",
    "cumpriu", "honesto", "transparente", "beneficio", "vantagem", "melhor",
}
_NEG = {
    "pessimo", "pessima", "ruim", "horrivel", "terrivel", "fraude",
    "golpe", "enganado", "enganoso", "roubo", "roubado", "ladrao", "descaso",
    "demora", "demorado", "lento", "problema", "reclamacao", "reclamando",
    "insatisfeito", "insatisfeita", "decepcao", "decepcionado", "cancelar",
    "cancelamento", "processo", "processar", "justica", "procon",
    "negado", "negou", "recusou", "abusivo", "abuso",
    "mentira", "mentiroso", "vergonha", "vergonhoso", "pilantra",
    "estelionato", "prejuizo", "prejudicado", "dificil", "burocracia",
    "nao resolve", "nao resolveu", "descumpriu", "irregular", "raiva",
}
_NEGATORS = {"nao", "nunca", "jamais", "nem", "sem"}

# --- termos que disparam ALERTA (risco reputacional / crise) ------------------
_ALERT_TERMS = [
    "golpe", "fraude", "estelionato", "processo", "processar", "justica",
    "procon", "reclame aqui", "nao paga", "nao pagou", "calote", "roubo",
    "pilantra", "denuncia", "denunc", "crime", "liminar", "acao judicial",
    "falencia", "falir", "liquidacao", "susep", "cancelamento em massa",
]


def _strip_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )


def _normalize(text: str) -> str:
    return _strip_accents((text or "").lower())


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text)


def _lexicon_score(text: str) -> tuple[str, float]:
    norm = _normalize(text)
    tokens = _tokenize(norm)
    score = 0
    for i, tok in enumerate(tokens):
        val = 0
        if tok in _POS:
            val = 1
        elif tok in _NEG:
            val = -1
        if val != 0:
            # inversão por negação nas 2 palavras anteriores ("não recomendo")
            window = tokens[max(0, i - 2):i]
            if any(w in _NEGATORS for w in window):
                val = -val
            score += val
    # bigramas negativos ("nao paga", "nao resolveu") reforçam
    for phrase in ("nao paga", "nao pagou", "nao resolve", "nao resolveu"):
        if phrase in norm:
            score -= 1

    if score >= 1:
        label, s = "positivo", min(1.0, score / 3.0)
    elif score <= -1:
        label, s = "negativo", max(-1.0, score / 3.0)
    else:
        label, s = "neutro", 0.0
    return label, round(s, 3)


def detect_alert(text: str) -> bool:
    norm = _normalize(text)
    return any(term in norm for term in _ALERT_TERMS)


# --- camada opcional com Claude ----------------------------------------------
def _llm_score(text: str) -> Optional[tuple[str, float]]:
    if not config.ANTHROPIC_API_KEY:
        return None
    try:
        import requests
        prompt = (
            "Classifique o sentimento do texto abaixo em relação à marca GBOEX. "
            "Responda APENAS um JSON: {\"sentimento\":\"positivo|neutro|negativo\","
            "\"score\":número entre -1 e 1}. Texto:\n\n" + text[:1500]
        )
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": config.ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": config.SENTIMENT_MODEL,
                "max_tokens": 60,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=config.REQUEST_TIMEOUT,
        )
        r.raise_for_status()
        content = r.json()["content"][0]["text"]
        data = json.loads(re.search(r"\{.*\}", content, re.S).group(0))
        label = data.get("sentimento", "neutro")
        score = float(data.get("score", 0.0))
        if label not in ("positivo", "neutro", "negativo"):
            label = "neutro"
        return label, round(max(-1.0, min(1.0, score)), 3)
    except Exception:
        return None  # qualquer falha cai no léxico


def analyze(text: str) -> tuple[str, float, bool]:
    """Retorna (sentimento, score, is_alert)."""
    alert = detect_alert(text)
    result = _llm_score(text) or _lexicon_score(text)
    label, score = result
    return label, score, alert


# --- classificação em LOTE com Claude (rápida e barata) -----------------------
_BATCH = 20  # textos por chamada à API


def _llm_score_batch(texts: list[str]) -> Optional[list[Optional[tuple[str, float]]]]:
    """Classifica vários textos numa só chamada. Retorna lista alinhada aos
    textos (cada item (label,score) ou None p/ cair no léxico). None se sem chave/erro."""
    if not config.ANTHROPIC_API_KEY:
        return None
    try:
        import requests
        itens = "\n".join(f"{i + 1}) {(t or '').strip()[:500]}" for i, t in enumerate(texts))
        prompt = (
            "Você classifica o sentimento de menções sobre a marca GBOEX "
            "(previdência/pecúlio/seguros) do ponto de vista reputacional. "
            "Para CADA texto numerado, retorne o sentimento EM RELAÇÃO ao GBOEX: "
            "'positivo', 'neutro' ou 'negativo', e um score de -1 a 1. "
            "Considere IRONIA e sarcasmo; trate reclamação de cobrança indevida, "
            "dificuldade de cancelamento, descaso e falta de retorno como NEGATIVO; "
            "elogio, gratidão e recomendação como POSITIVO; informativo/institucional "
            "sem opinião como NEUTRO. Responda APENAS um array JSON, um objeto por texto, "
            'no formato [{"i":1,"sentimento":"negativo","score":-0.7}, ...], na ordem dos textos.'
            "\n\nTextos:\n" + itens
        )
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": config.ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": config.SENTIMENT_MODEL,
                "max_tokens": 40 * len(texts) + 200,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=60,
        )
        r.raise_for_status()
        content = r.json()["content"][0]["text"]
        arr = json.loads(re.search(r"\[.*\]", content, re.S).group(0))
        by_i: dict[int, tuple[str, float]] = {}
        for o in arr:
            idx = int(o.get("i", 0)) - 1
            label = o.get("sentimento", "neutro")
            if label not in ("positivo", "neutro", "negativo"):
                label = "neutro"
            score = round(max(-1.0, min(1.0, float(o.get("score", 0.0)))), 3)
            by_i[idx] = (label, score)
        return [by_i.get(i) for i in range(len(texts))]
    except Exception:
        return None


def analyze_batch(texts: list[str]) -> list[tuple[str, float, bool]]:
    """(sentimento, score, is_alert) para cada texto. Usa Claude em lote quando
    há chave; cai no léxico item a item quando não há ou em qualquer falha."""
    out: list[tuple[str, float, bool]] = [("neutro", 0.0, False)] * len(texts)
    for start in range(0, len(texts), _BATCH):
        chunk = texts[start:start + _BATCH]
        llm = _llm_score_batch(chunk)
        for j, t in enumerate(chunk):
            res = (llm[j] if llm and llm[j] else None) or _lexicon_score(t)
            out[start + j] = (res[0], res[1], detect_alert(t))
    return out
