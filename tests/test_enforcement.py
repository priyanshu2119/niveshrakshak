"""Tests for enforcement history lookup."""

import sqlite3
import time
from pathlib import Path

import pytest

# Ensure server package is importable
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from server.enforcement import lookup, stats, EnforcementResult


@pytest.fixture
def enforcement_db(tmp_path):
    """Create a temporary enforcement database with test data."""
    db_path = tmp_path / "test_enforcement.sqlite"
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE enforcement (
            id INTEGER PRIMARY KEY,
            source TEXT NOT NULL,
            entity_name TEXT NOT NULL,
            entity_name_norm TEXT NOT NULL,
            reg_no TEXT,
            order_date TEXT,
            order_type TEXT,
            violation_summary TEXT,
            penalty_amount TEXT,
            order_url TEXT,
            imported_at INTEGER NOT NULL
        )
    """)
    now = int(time.time())
    test_records = [
        ("sebi_order", "IIFL Capital Services Limited", "IIFL CAPITAL SERVICES",
         "", "2026-10-13", "Adjudication", "Inspection violations", "₹50,00,000",
         "https://sebi.gov.in/order1.pdf", now),
        ("sebi_order", "SMC Global Securities Ltd", "SMC GLOBAL SECURITIES",
         "INZ000001234", "2026-10-01", "Adjudication", "Client fund misuse", "",
         "https://sebi.gov.in/order2.pdf", now),
        ("nse_defaulter", "KARVY STOCK BROKING LTD.", "KARVY STOCK BROKING",
         "", "2020-11-23", "Defaulter", "Misuse of client funds", "",
         "", now),
        ("nse_defaulter", "YES Securities (India) Limited", "YES SECURITIES",
         "", "2026-07-01", "Defaulter", "Shortfall of client funds", "",
         "", now),
        ("sebi_order", "Alankit Assignments Limited", "ALANKIT ASSIGNMENTS",
         "", "2026-09-28", "Settlement", "Disclosure violations", "₹10,00,000",
         "https://sebi.gov.in/order3.pdf", now),
    ]
    conn.executemany(
        "INSERT INTO enforcement (source, entity_name, entity_name_norm, reg_no, "
        "order_date, order_type, violation_summary, penalty_amount, order_url, imported_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        test_records,
    )
    conn.commit()
    conn.close()

    # Monkey-patch db module to use test DB
    import server.db as db_mod
    original_conn = db_mod.conn
    original_db_path = db_mod.DB_PATH
    db_mod.DB_PATH = str(db_path)

    yield db_path

    # Restore
    db_mod.DB_PATH = original_db_path


class TestEnforcementLookup:
    def test_lookup_by_name_exact(self, enforcement_db):
        result = lookup(name="IIFL Capital Services Limited")
        assert result.found
        assert len(result.hits) >= 1
        assert result.hits[0].entity_name == "IIFL Capital Services Limited"
        assert result.hits[0].source == "sebi_order"

    def test_lookup_by_name_fuzzy(self, enforcement_db):
        # Slight variation in name should still match
        result = lookup(name="IIFL Capital Services")
        assert result.found
        assert any("IIFL" in h.entity_name for h in result.hits)

    def test_lookup_by_regno(self, enforcement_db):
        result = lookup(reg_no="INZ000001234")
        assert result.found
        assert result.hits[0].matched_on == "reg_no"
        assert result.hits[0].match_score == 100.0

    def test_lookup_not_found(self, enforcement_db):
        result = lookup(name="Totally Fake Company XYZ")
        assert not result.found
        assert len(result.hits) == 0

    def test_lookup_empty_query(self, enforcement_db):
        result = lookup()
        assert not result.found

    def test_lookup_short_name_ignored(self, enforcement_db):
        result = lookup(name="AB")
        assert not result.found

    def test_multiple_hits_same_entity(self, enforcement_db):
        # YES Securities appears once in our test data
        result = lookup(name="YES Securities India Limited")
        assert result.found

    def test_to_dict_format(self, enforcement_db):
        result = lookup(name="IIFL Capital Services Limited")
        d = result.to_dict()
        assert d["found"] is True
        assert "hits" in d
        assert "hit_count" in d
        assert d["hit_count"] >= 1
        hit = d["hits"][0]
        assert "source" in hit
        assert "entity_name" in hit
        assert "order_date" in hit
        assert "match_score" in hit

    def test_to_dict_not_found(self, enforcement_db):
        result = lookup(name="Nonexistent Entity")
        d = result.to_dict()
        assert d["found"] is False
        assert d["hits"] == []


class TestEnforcementStats:
    def test_stats_returns_counts(self, enforcement_db):
        s = stats()
        assert s["total_records"] == 5
        assert "sebi_order" in s["by_source"]
        assert "nse_defaulter" in s["by_source"]
        assert s["last_import_ts"] > 0
