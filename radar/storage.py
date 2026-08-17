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

-- custo de cada rodada, para saber quanto da verba do ciclo já foi usada
CREATE TABLE IF NOT EXISTS run_costs (
    run_at      TEXT PRIMARY KEY,
    cycle_start TEXT,
    custo_usd   REAL
);
CREATE INDEX IF NOT EXISTS idx_cycle ON run_costs(cycle_start);
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

    # --- verba consumida por ciclo de cobrança --------------------------------
    def record_run_cost(self, run_at: str, cycle_start: str, custo_usd: float) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO run_costs (run_at, cycle_start, custo_usd)"
            " VALUES (?,?,?)", (run_at, cycle_start, float(custo_usd)))
        self._conn.commit()

    def last_run_cost(self) -> float:
        """Custo da última coleta paga medida — referência do painel quando a
        rodada atual foi só de fontes grátis (custo zero)."""
        row = self._conn.execute(
            "SELECT custo_usd FROM run_costs ORDER BY run_at DESC LIMIT 1").fetchone()
        return round(float(row[0]), 2) if row else 0.0

    def cycle_cost(self, cycle_start: str) -> float:
        """Quanto o radar já gastou no ciclo (0.0 se não houver registro)."""
        row = self._conn.execute(
            "SELECT COALESCE(SUM(custo_usd), 0) FROM run_costs WHERE cycle_start = ?",
            (cycle_start,)).fetchone()
        return round(float(row[0]), 2)

    def close(self) -> None:
        self._conn.close()
