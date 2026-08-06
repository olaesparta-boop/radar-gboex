"""Processamento pós-coleta: enriquece cada menção com o sentimento."""
from __future__ import annotations

from .models import Mention
from . import sentiment


def enrich(mentions: list[Mention]) -> list[Mention]:
    # classificação em lote (Claude quando há chave; senão léxico) — bem mais rápida
    blobs = [f"{m.title}. {m.text}".strip() for m in mentions]
    results = sentiment.analyze_batch(blobs)
    for m, (label, score) in zip(mentions, results):
        # não sobrescreve sentimento já definido pela fonte (ex.: avaliação FB, score RA)
        if m.sentiment == "neutro" and m.sentiment_score == 0.0:
            m.sentiment = label
            m.sentiment_score = score
    return mentions
