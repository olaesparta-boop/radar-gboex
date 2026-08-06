"""Armazenamento em SQLite. Simples, sem servidor, versionável, portátil."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable

from .models import Mention

_SCHEMA = """
CREATE TABLE IF NOT EXISTS mentions (
    id              TEXT PRIMARY KEY,
    source          TEXT,
    channel         TEXT,
    title           TEXT,
    url             TEXT,
    text            TEXT,
    author          TEXT,
    domain          TEXT,
    language        TEXT,
    published_at    TEXT,
    sentiment       TEXT,
    sentiment_score REAL,
    is_owned        INTEGER,
    collected_at    TEXT,
    raw_id          TEXT
);
CREATE INDEX IF NOT EXISTS idx_published ON mentions(published_at);
CREATE INDEX IF NOT EXISTS idx_channel   ON mentions(channel);
CREATE INDEX IF NOT EXISTS idx_sentiment ON mentions(sentiment);
"""


class Storage:
    def __init__(self, db_path: Path):
        self.db_path = str(db_path)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def upsert_many(self, mentions: Iterable[Mention]) -> tuple[int, int]:
        """
        Insere as menções novas. Retorna (novas, ja_existentes).
        Usa INSERT OR IGNORE pela PK (id derivado da URL) => dedup automático.
        """
        novas = 0
        total = 0
        cur = self._conn.cursor()
        for m in mentions:
            total += 1
            d = m.to_dict()
            cur.execute(
                """INSERT OR IGNORE INTO mentions
                   (id, source, channel, title, url, text, author, domain,
                    language, published_at, sentiment, sentiment_score,
                    is_owned, collected_at, raw_id)
                   VALUES (:id,:source,:channel,:title,:url,:text,:author,:domain,
                    :language,:published_at,:sentiment,:sentiment_score,
                    :is_owned,:collected_at,:raw_id)""",
                {**d, "is_owned": int(d["is_owned"])},
            )
            novas += cur.rowcount
        self._conn.commit()
        return novas, total - novas

    def all_rows(self) -> list[dict]:
        cur = self._conn.execute(
            "SELECT * FROM mentions ORDER BY published_at DESC"
        )
        return [dict(r) for r in cur.fetchall()]

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM mentions").fetchone()[0]

    def close(self) -> None:
        self._conn.close()
