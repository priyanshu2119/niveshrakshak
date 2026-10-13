"""
Enforcement history lookup.

Given an entity name (from OCR/extract) or a registration number, check whether
it appears in our enforcement database (SEBI orders + NSE/BSE defaulters).

This is the key differentiator from SEBI Check: we don't just say "registered"
or "not registered" — we show whether the entity has been penalised, suspended,
or declared a defaulter by regulators.
"""

import logging
import re
from dataclasses import dataclass, field

from rapidfuzz import fuzz

from . import db

log = logging.getLogger(__name__)

# Minimum fuzzy match score to consider a hit (0-100).
# 87 avoids most false positives on generic terms while still catching
# legitimate variations (e.g. "YES Securities" vs "YES Securities (India)").
MIN_MATCH_SCORE = 87

# Maximum results to return per lookup
MAX_RESULTS = 10


@dataclass
class EnforcementHit:
    """A single enforcement record match."""
    source: str           # 'sebi_order', 'nse_defaulter', 'bse_defaulter'
    entity_name: str      # original name from enforcement DB
    order_date: str       # ISO date
    order_type: str       # e.g. 'Adjudication', 'Defaulter'
    violation_summary: str
    penalty_amount: str
    order_url: str
    match_score: float    # fuzzy match score (0-100)
    matched_on: str       # 'name' or 'reg_no'


@dataclass
class EnforcementResult:
    """Result of an enforcement history lookup."""
    found: bool = False
    hits: list[EnforcementHit] = field(default_factory=list)
    query_name: str = ""
    query_regno: str = ""

    def to_dict(self) -> dict:
        if not self.found:
            return {"found": False, "hits": [], "query_name": self.query_name}
        return {
            "found": True,
            "query_name": self.query_name,
            "hit_count": len(self.hits),
            "hits": [
                {
                    "source": h.source,
                    "entity_name": h.entity_name,
                    "order_date": h.order_date,
                    "order_type": h.order_type,
                    "violation_summary": h.violation_summary[:200] if h.violation_summary else "",
                    "penalty_amount": h.penalty_amount,
                    "order_url": h.order_url,
                    "match_score": round(h.match_score, 1),
                    "matched_on": h.matched_on,
                }
                for h in self.hits
            ],
        }


def lookup(name: str = "", reg_no: str = "") -> EnforcementResult:
    """
    Look up enforcement history by entity name and/or registration number.

    Returns EnforcementResult with any matching enforcement records.
    Uses exact match on reg_no first, then fuzzy match on normalised name.
    """
    result = EnforcementResult(query_name=name, query_regno=reg_no)
    hits: list[EnforcementHit] = []

    # 1. Exact match on registration number (highest confidence)
    if reg_no:
        reg_hits = _lookup_by_regno(reg_no)
        hits.extend(reg_hits)

    # 2. Fuzzy match on normalised name
    if name:
        name_hits = _lookup_by_name(name)
        # Deduplicate against reg_no hits
        seen_keys = {(h.source, h.entity_name, h.order_date) for h in hits}
        for h in name_hits:
            key = (h.source, h.entity_name, h.order_date)
            if key not in seen_keys:
                hits.append(h)
                seen_keys.add(key)

    # Sort by date descending (most recent first), then by match score
    hits.sort(key=lambda h: (h.order_date or "", h.match_score), reverse=True)
    result.hits = hits[:MAX_RESULTS]
    result.found = len(result.hits) > 0

    if result.found:
        log.info(
            "Enforcement lookup: %s/%s → %d hits",
            name[:30], reg_no, len(result.hits),
        )
    return result


def _lookup_by_regno(reg_no: str) -> list[EnforcementHit]:
    """Exact match on registration number."""
    rows = db.conn().execute(
        "SELECT source, entity_name, order_date, order_type, "
        "violation_summary, penalty_amount, order_url "
        "FROM enforcement WHERE reg_no = ? LIMIT ?",
        (reg_no, MAX_RESULTS),
    ).fetchall()

    return [
        EnforcementHit(
            source=r[0], entity_name=r[1], order_date=r[2] or "",
            order_type=r[3] or "", violation_summary=r[4] or "",
            penalty_amount=r[5] or "", order_url=r[6] or "",
            match_score=100.0, matched_on="reg_no",
        )
        for r in rows
    ]


def _normalize_enforcement_name(name: str) -> str:
    """Normalize entity name specifically for enforcement matching.
    Strips legal suffixes, parenthetical additions, titles, etc."""
    if not name:
        return ""
    s = name.upper().strip()
    # Remove common prefixes
    for prefix in ["M/S ", "M/S. ", "MR. ", "MS. ", "MRS. ", "SHRI ", "SMT. "]:
        if s.startswith(prefix):
            s = s[len(prefix):]
    # Remove parenthetical suffixes like "(AND ITS CONSTITUENT PARTNERS)"
    s = re.sub(r"\s*\([^)]*\)\s*$", "", s)
    # Remove legal suffixes
    for suffix in [
        " PRIVATE LIMITED", " PVT LTD", " PVT. LTD.", " PVT.LTD.",
        " LIMITED", " LTD.", " LTD",
        " PROPRIETORSHIP", " PARTNERSHIP",
        " (INDIA)", "(INDIA)",
    ]:
        if s.endswith(suffix):
            s = s[: -len(suffix)].strip()
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _lookup_by_name(name: str) -> list[EnforcementHit]:
    """Fuzzy match on normalised entity name."""
    norm_query = _normalize_enforcement_name(name)
    if not norm_query or len(norm_query) < 3:
        return []

    # Pre-filter with SQL LIKE to avoid scanning all 14K+ records.
    # Extract first significant word (3+ chars) for the LIKE filter.
    words = [w for w in norm_query.split() if len(w) >= 3]
    if not words:
        return []
    like_pattern = f"%{words[0]}%"

    rows = db.conn().execute(
        "SELECT DISTINCT entity_name, entity_name_norm FROM enforcement "
        "WHERE entity_name_norm LIKE ? OR entity_name LIKE ?",
        (like_pattern, like_pattern),
    ).fetchall()

    if not rows:
        return []

    # Score each candidate using multiple fuzzy metrics
    candidates: list[tuple[str, str, float]] = []
    for entity_name, entity_norm in rows:
        if not entity_norm:
            continue
        # Normalize the DB entity name the same way for fair comparison
        db_norm = _normalize_enforcement_name(entity_name)
        # Use weighted combination: token_sort is more reliable for entity names,
        # partial_ratio helps with substring matches (e.g. "YES Securities" matching
        # "YES Securities (India) Limited"). Weight token_sort 70%, partial 30%.
        tsr = fuzz.token_sort_ratio(norm_query, db_norm)
        pr = fuzz.partial_ratio(norm_query, db_norm)
        score = 0.7 * tsr + 0.3 * pr
        if score >= MIN_MATCH_SCORE:
            candidates.append((entity_name, entity_norm, score))

    # Sort by score descending
    candidates.sort(key=lambda c: c[2], reverse=True)

    # Fetch full records for top matches
    hits: list[EnforcementHit] = []
    seen_entities = set()
    for entity_name, _, score in candidates[:5]:  # top 5 entities
        if entity_name in seen_entities:
            continue
        seen_entities.add(entity_name)

        records = db.conn().execute(
            "SELECT source, entity_name, order_date, order_type, "
            "violation_summary, penalty_amount, order_url "
            "FROM enforcement WHERE entity_name = ? "
            "ORDER BY order_date DESC LIMIT ?",
            (entity_name, MAX_RESULTS),
        ).fetchall()

        for r in records:
            hits.append(EnforcementHit(
                source=r[0], entity_name=r[1], order_date=r[2] or "",
                order_type=r[3] or "", violation_summary=r[4] or "",
                penalty_amount=r[5] or "", order_url=r[6] or "",
                match_score=score, matched_on="name",
            ))

    return hits


def stats() -> dict:
    """Return enforcement database statistics."""
    conn = db.conn()
    total = conn.execute("SELECT count(*) FROM enforcement").fetchone()[0]
    by_source = conn.execute(
        "SELECT source, count(*) FROM enforcement GROUP BY source"
    ).fetchall()
    latest = conn.execute(
        "SELECT max(imported_at) FROM enforcement"
    ).fetchone()[0]
    return {
        "total_records": total,
        "by_source": {r[0]: r[1] for r in by_source},
        "last_import_ts": latest,
    }
