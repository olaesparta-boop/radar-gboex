"""Modelo de dados unificado para uma menção, venha de onde vier."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Mention:
    """
    Uma menção normalizada. Todo collector converte o formato bruto da sua
    fonte para este mesmo objeto, para o resto do sistema tratar tudo igual.
    """
    source: str                 # "google_news", "gdelt", "reclame_aqui", "instagram", ...
    channel: str                # categoria macro: "noticia", "reclamacao", "social", "canal_proprio"
    title: str                  # título / trecho principal
    url: str                    # link para a menção original
    published_at: str           # ISO-8601 (data da publicação da menção)
    text: str = ""              # corpo/descrição, quando houver
    author: str = ""            # autor/veículo/perfil
    domain: str = ""            # domínio da fonte (para notícias)
    language: str = "pt"
    # preenchidos no processamento:
    sentiment: str = "neutro"   # "positivo" | "neutro" | "negativo"
    sentiment_score: float = 0.0  # -1.0 .. +1.0
    is_owned: bool = False      # True se veio de canal oficial do GBOEX
    # metadados
    collected_at: str = field(default_factory=_now_iso)
    raw_id: str = ""            # id no sistema de origem, se houver

    @property
    def id(self) -> str:
        """ID estável baseado na URL (ou título+fonte) para deduplicação."""
        basis = (self.url or f"{self.source}:{self.title}").strip().lower()
        return hashlib.sha1(basis.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict:
        d = asdict(self)
        d["id"] = self.id
        return d
