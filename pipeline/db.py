"""
Database layer for AutoInsight.
SQLite wrapper with simple CRUD operations.
"""

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "autoinsight.db"
SCHEMA_PATH = PROJECT_ROOT / "pipeline" / "schema.sql"


class DB:
    """SQLite database wrapper."""

    def __init__(self, path: Optional[Path] = None):
        self.path = path or DB_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _init_schema(self):
        with sqlite3.connect(str(self.path)) as conn:
            schema = SCHEMA_PATH.read_text(encoding="utf-8")
            conn.executescript(schema)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    # ── Generic ops ──────────────────────────────────────

    def execute(self, sql: str, params: tuple = ()):
        with self._connect() as conn:
            conn.execute(sql, params)

    def query(self, sql: str, params: tuple = ()) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]

    def query_one(self, sql: str, params: tuple = ()) -> Optional[dict]:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    # ── Upserts ──────────────────────────────────────────

    def upsert_sales(self, model_name: str, brand_name: str, month: str,
                     sales_volume: int, rank: int, price_range: str = "",
                     is_nev: int = 0):
        self.execute("""
            INSERT INTO sales_monthly (model_name, brand_name, month, sales_volume, rank, price_range, is_nev)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(model_name, month) DO UPDATE SET
                sales_volume=excluded.sales_volume,
                rank=excluded.rank,
                price_range=excluded.price_range,
                is_nev=excluded.is_nev,
                scraped_at=datetime('now')
        """, (model_name, brand_name, month, sales_volume, rank, price_range, is_nev))

    def upsert_news(self, title: str, source: str, url: str,
                    published_at: str = "", summary: str = "",
                    related_brands: Optional[list] = None,
                    sentiment: str = "neutral"):
        brands_json = json.dumps(related_brands, ensure_ascii=False) if related_brands else "[]"
        self.execute("""
            INSERT INTO news_articles (title, source, url, published_at, summary, related_brands, sentiment)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(url) DO NOTHING
        """, (title, source, url, published_at, summary, brands_json, sentiment))

    def upsert_sentiment(self, brand_name: str, period: str, platform: str,
                         positive_ratio: float, negative_ratio: float,
                         neutral_ratio: float, total_mentions: int,
                         top_keywords: Optional[list] = None):
        kw_json = json.dumps(top_keywords, ensure_ascii=False) if top_keywords else "[]"
        self.execute("""
            INSERT INTO social_sentiment (brand_name, period, platform, positive_ratio, negative_ratio, neutral_ratio, total_mentions, top_keywords)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(brand_name, period, platform) DO UPDATE SET
                positive_ratio=excluded.positive_ratio,
                negative_ratio=excluded.negative_ratio,
                neutral_ratio=excluded.neutral_ratio,
                total_mentions=excluded.total_mentions,
                top_keywords=excluded.top_keywords,
                scraped_at=datetime('now')
        """, (brand_name, period, platform, positive_ratio, negative_ratio, neutral_ratio, total_mentions, kw_json))

    def save_agent_result(self, product: str, target_name: str, run_date: str,
                          score: float, score_label: str, details: dict,
                          report_md: str = "", agent_config: str = "",
                          tokens_used: int = 0, cost_estimate: float = 0.0):
        self.execute("""
            INSERT INTO agent_results (product, target_name, run_date, score, score_label, details, report_md, agent_config, tokens_used, cost_estimate)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (product, target_name, run_date, score, score_label,
              json.dumps(details, ensure_ascii=False), report_md,
              agent_config, tokens_used, cost_estimate))

    # ── Query helpers ────────────────────────────────────

    def get_latest_sales(self, month: Optional[str] = None) -> list[dict]:
        if month:
            return self.query("SELECT * FROM sales_monthly WHERE month=? ORDER BY rank", (month,))
        latest = self.query_one("SELECT month FROM sales_monthly ORDER BY month DESC LIMIT 1")
        if not latest:
            return []
        return self.query("SELECT * FROM sales_monthly WHERE month=? ORDER BY rank", (latest["month"],))

    def get_brand_sales_trend(self, brand_name: str, months: int = 12) -> list[dict]:
        return self.query("""
            SELECT month, SUM(sales_volume) as total_sales
            FROM sales_monthly WHERE brand_name=?
            GROUP BY month ORDER BY month DESC LIMIT ?
        """, (brand_name, months))

    def get_news_for_brand(self, brand_name: str, limit: int = 20) -> list[dict]:
        return self.query("""
            SELECT * FROM news_articles WHERE related_brands LIKE ?
            ORDER BY published_at DESC LIMIT ?
        """, (f"%{brand_name}%", limit))

    def get_latest_sentiment(self, brand_name: str, limit: int = 4) -> list[dict]:
        return self.query("""
            SELECT * FROM social_sentiment WHERE brand_name=?
            ORDER BY period DESC LIMIT ?
        """, (brand_name, limit))

    def get_supplier_dependencies(self, brand_name: str) -> list[dict]:
        return self.query("SELECT * FROM supplier_relations WHERE brand_name=?", (brand_name,))

    def get_supplier_brands(self, supplier_name: str) -> list[dict]:
        return self.query("SELECT * FROM supplier_relations WHERE supplier_name=?", (supplier_name,))

    def get_latest_agent_result(self, product: str, target_name: str) -> Optional[dict]:
        return self.query_one("""
            SELECT * FROM agent_results WHERE product=? AND target_name=?
            ORDER BY run_date DESC LIMIT 1
        """, (product, target_name))


# Singleton
_db: Optional[DB] = None


def get_db() -> DB:
    global _db
    if _db is None:
        _db = DB()
    return _db
