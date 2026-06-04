"""
LegalShield AI 2026 — Database (Projeto B Enterprise)
SQLite para instalação zero-config.
"""

import os
import sqlite3
from pathlib import Path

from .config import get_enterprise_settings

settings = get_enterprise_settings()


def get_db_path() -> str:
    """Retorna caminho do banco SQLite."""
    path = settings.database_path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return path


def get_connection() -> sqlite3.Connection:
    """Retorna conexão SQLite."""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_enterprise_db():
    """Inicializa o schema do banco Enterprise."""
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS contracts (
            id TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            file_type TEXT NOT NULL,
            file_size_bytes INTEGER NOT NULL,
            sha256_hash TEXT NOT NULL,
            stored_path TEXT NOT NULL,
            page_count INTEGER DEFAULT 1,
            ocr_used INTEGER DEFAULT 0,
            status TEXT DEFAULT 'uploaded',
            created_at TEXT NOT NULL,
            updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS analyses (
            id TEXT PRIMARY KEY,
            contract_id TEXT NOT NULL,
            analysis_mode TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            results_json TEXT,
            resumo_executivo TEXT,
            score_risco INTEGER DEFAULT 0,
            total_achados INTEGER DEFAULT 0,
            model_used TEXT,
            tokens_used INTEGER DEFAULT 0,
            cost_usd REAL DEFAULT 0.0,
            latency_seconds REAL DEFAULT 0.0,
            injection_detected INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            completed_at TEXT,
            FOREIGN KEY (contract_id) REFERENCES contracts(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()
