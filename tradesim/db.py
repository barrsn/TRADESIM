"""
db.py — SQLite persistence for trades and session journal.
Schema is intentionally append-only; never UPDATE or DELETE rows.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Dict

import pandas as pd

DB_PATH = Path(__file__).parent / "sim_trainer.db"


def init() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS trades (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                ts_created      TEXT    DEFAULT (datetime('now')),
                symbol          TEXT    NOT NULL,
                interval        TEXT    NOT NULL,
                side            TEXT    NOT NULL,           -- LONG | SHORT
                entry_time      INTEGER NOT NULL,           -- epoch seconds
                exit_time       INTEGER NOT NULL,           -- epoch seconds
                entry           REAL    NOT NULL,
                exit            REAL    NOT NULL,
                stop            REAL    NOT NULL,
                target          REAL    NOT NULL,
                r_multiple      REAL,                       -- NULL if initial_r=0
                exit_reason     TEXT    NOT NULL,           -- STOP | TARGET | MANUAL_EXIT@CLOSE
                setup           TEXT,
                trigger         TEXT,
                emotag          TEXT,
                emo_intensity   INTEGER,
                rule_adherence  INTEGER,                    -- 1 = followed rules, 0 = broke rules
                notes           TEXT
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                ts          TEXT DEFAULT (datetime('now')),
                symbol      TEXT,
                interval    TEXT,
                goal        TEXT,
                reflection  TEXT
            );
            """
        )
        conn.commit()


def insert_trade(row: Dict[str, Any]) -> None:
    cols = ", ".join(row.keys())
    marks = ", ".join(["?"] * len(row))
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(f"INSERT INTO trades ({cols}) VALUES ({marks})", list(row.values()))
        conn.commit()


def read_trades(symbol: str | None = None, interval: str | None = None) -> pd.DataFrame:
    where_clauses, params = [], []
    if symbol:
        where_clauses.append("symbol = ?")
        params.append(symbol)
    if interval:
        where_clauses.append("interval = ?")
        params.append(interval)
    where = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql_query(
            f"SELECT * FROM trades {where} ORDER BY id DESC",
            conn,
            params=params,
        )
    return df


def clear_trades(symbol: str, interval: str) -> None:
    """Delete trades for a given symbol+interval (used by 'Clear History' button)."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "DELETE FROM trades WHERE symbol = ? AND interval = ?",
            (symbol, interval),
        )
        conn.commit()
