#!/usr/bin/env python3
"""
Refresh SEBI enforcement orders and NSE defaulter/expelled members into SQLite.

Data sources:
  1. SEBI Orders of Adjudicating Officer (smid=6) — most relevant for fraud/penalty
  2. SEBI Settlement Orders (smid=3) — entities that settled violations
  3. SEBI ED/CGM Quasi-Judicial Orders (smid=133) — serious enforcement
  4. NSE Defaulter/Expelled Members — static HTML table, no pagination

SEBI order pages use server-side pagination with ?start=X&limit=Y parameters.
Each page renders ~20 order rows in a <table class="listingTable">.

Usage:
    python tools/refresh_enforcement.py          # full refresh
    python tools/refresh_enforcement.py --sebi-only   # skip NSE
    python tools/refresh_enforcement.py --nse-only    # skip SEBI
"""

import argparse
import html
import logging
import re
import sqlite3
import sys
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "nr.sqlite"

# --- SEBI configuration -----------------------------------------------------

SEBI_BASE = "https://www.sebi.gov.in"
SEBI_ORDER_CATEGORIES = {
    "adjudication": "/sebiweb/home/HomeAction.do?doListing=yes&sid=2&ssid=9&smid=6",
    "settlement": "/sebiweb/home/HomeAction.do?doListing=yes&sid=2&ssid=9&smid=3",
    "ed_cgm": "/sebiweb/home/HomeAction.do?doListing=yes&sid=2&ssid=9&smid=133",
}
SEBI_PAGE_SIZE = 25   # SEBI server returns max 25 rows per request (no server-side pagination)
SEBI_MAX_PAGES = 1    # Client-side DataTables only; server always returns latest 25
SEBI_DELAY = 1.5     # polite delay between requests (seconds)

# --- NSE configuration ------------------------------------------------------

NSE_DEFAULTER_URL = "https://www.nseindia.com/static/complaints/defaulter-expelled-members"

# --- Shared -----------------------------------------------------------------

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0 Safari/537.36"
    ),
    "Accept-Language": "en-IN,en;q=0.9",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def normalize_name(name: str) -> str:
    """Normalize entity name for fuzzy matching against registry."""
    if not name:
        return ""
    s = name.upper().strip()
    # Remove common legal suffixes
    for suffix in [
        " PRIVATE LIMITED", " PVT LTD", " PVT. LTD.", " PVT.LTD.",
        " LIMITED", " LTD.", " LTD",
        " PROPRIETORSHIP", " PARTNERSHIP",
        " (INDIA)", "(INDIA)",
    ]:
        if s.endswith(suffix):
            s = s[: -len(suffix)].strip()
    # Collapse whitespace
    s = re.sub(r"\s+", " ", s).strip()
    return s


def parse_date(raw: str) -> str:
    """Best-effort date parsing to ISO format."""
    if not raw:
        return ""
    raw = raw.strip()

    MONTHS = {
        "jan": "01", "feb": "02", "mar": "03", "apr": "04",
        "may": "05", "jun": "06", "jul": "07", "aug": "08",
        "sep": "09", "oct": "10", "nov": "11", "dec": "12",
        "january": "01", "february": "02", "march": "03", "april": "04",
        "june": "06", "july": "07", "august": "08",
        "september": "09", "october": "10", "november": "11", "december": "12",
    }

    # Try Mon DD, YYYY or Month DD, YYYY (e.g. "Oct 13, 2026", "September 5, 2024")
    m = re.match(r"(\w+)\s+(\d{1,2}),?\s+(\d{4})", raw)
    if m:
        mon, day, year = m.groups()
        mm = MONTHS.get(mon.lower(), "")
        if mm:
            return f"{year}-{mm}-{int(day):02d}"

    # Try DD-Mon-YYYY or DD-Month-YYYY or DD-Mon-YY (e.g. "08-Jul-26", "18-July-2022")
    m = re.match(r"(\d{1,2})[-\s](\w+)[-\s](\d{2,4})", raw)
    if m:
        day, mon, year = m.groups()
        mm = MONTHS.get(mon.lower(), "")
        if mm:
            yy = year if len(year) == 4 else f"20{year}"
            return f"{yy}-{mm}-{int(day):02d}"

    # Try DD-MM-YYYY with dashes (e.g. "26-03-2021")
    m = re.match(r"(\d{1,2})-(\d{1,2})-(\d{4})", raw)
    if m:
        d, mo, y = m.groups()
        return f"{y}-{int(mo):02d}-{int(d):02d}"

    # Try DD/MM/YYYY
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", raw)
    if m:
        d, mo, y = m.groups()
        return f"{y}-{int(mo):02d}-{int(d):02d}"

    # Try YYYY-MM-DD already
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", raw)
    if m:
        return raw

    return raw  # return as-is if unparseable


# =============================================================================
# SEBI Orders Scraper
# =============================================================================

def scrape_sebi_category(category: str, path: str) -> list[dict]:
    """Scrape one SEBI order category with pagination."""
    records = []
    base_url = urljoin(SEBI_BASE, path)

    for page in range(SEBI_MAX_PAGES):
        start = page * SEBI_PAGE_SIZE
        url = f"{base_url}&start={start}&limit={SEBI_PAGE_SIZE}"
        log.info("SEBI %s page %d: %s", category, page + 1, url)

        try:
            resp = SESSION.get(url, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as e:
            log.warning("SEBI request failed (page %d): %s", page + 1, e)
            break

        soup = BeautifulSoup(resp.text, "html.parser")

        # SEBI uses a dataTable with class 'dataTable' — 2 columns: Date | Title
        found_rows = False
        for table in soup.find_all("table", class_="dataTable"):
            rows = table.find_all("tr")
            for row in rows:
                cells = row.find_all(["td", "th"])
                if len(cells) < 2:
                    continue
                # Skip header
                if row.find("th"):
                    continue

                date_cell = cells[0]
                title_cell = cells[1]

                date_raw = date_cell.get_text(strip=True)
                title_text = title_cell.get_text(strip=True)
                
                # Get link from title cell
                link_tag = title_cell.find("a")
                order_url = ""
                if link_tag and link_tag.get("href"):
                    order_url = link_tag["href"]
                    if not order_url.startswith("http"):
                        order_url = urljoin(SEBI_BASE, order_url)

                record = _parse_sebi_row(date_raw, title_text, order_url, category)
                if record and record["entity_name"]:
                    records.append(record)
                    found_rows = True

        if not found_rows:
            log.info("No more rows found for %s at page %d", category, page + 1)
            break

        time.sleep(SEBI_DELAY)

    log.info("SEBI %s: scraped %d records", category, len(records))
    return records


def _parse_sebi_row(date_raw: str, title: str, order_url: str, category: str) -> dict | None:
    """Parse a single SEBI order row into a record dict."""
    if not title or len(title) < 5:
        return None

    # Extract entity name from title patterns like:
    # "Adjudication Order in the matter of inspection of IIFL Capital..."
    # "Settlement Order in the matter of M/s XYZ Securities..."
    # "Order in the matter of ABC Ltd."
    entity_name = title
    
    # Remove common prefixes
    for prefix in [
        r"^(?:Adjudication|Settlement|Final|Interim|Ex[- ]parte|Corrigendum|Addendum)\s+Order\s*",
        r"^Order\s+(?:of\s+)?(?:ED|CGM|AO|Chairperson|Member)\s*",
        r"^In\s+the\s+matter\s+of\s+",
        r"^Re:\s*",
        r"^(?:inspection|investigation|inquiry|proceedings?)\s+(?:of|into|in)\s+",
        r"^(?:suspected\s+)?insider\s+trading\s+in\s+the\s+scrip(?:s|p)?\s+of\s+",
        r"^(?:alleged\s+)?(?:fraudulent|unfair|manipulative)\s+(?:trade|trading|practice)s?\s+(?:by|in|of)\s+",
        r"^(?:non-compliance|violation|contravention)\s+(?:of|by)\s+",
        r"^(?:in\s+the\s+matter\s+of\s+)?(?:m/s\.?|mr\.?|ms\.?|mrs\.?)\s+",
    ]:
        entity_name = re.sub(prefix, "", entity_name, flags=re.I).strip()

    # Remove trailing descriptors
    for suffix in [
        r"\s*[-–—]\s*(?:Adjudication|Settlement|Enforcement|Inspection|Investigation).*",
        r"\s*[-–—]\s*(?:Research\s+Analyst|Trading\s+Member|Broker|Depository\s+Participant).*",
        r"\s+and\s+(?:its|their)\s+(?:proprietorship|partnership|firm|company).*",
        r"\s*\.\.\.$",
        r"^in\s+respect\s+of\s+",
    ]:
        entity_name = re.sub(suffix, "", entity_name, flags=re.I).strip()

    if not entity_name or len(entity_name) < 3:
        return None

    return {
        "source": "sebi_order",
        "entity_name": entity_name,
        "entity_name_norm": normalize_name(entity_name),
        "reg_no": "",
        "order_date": parse_date(date_raw),
        "order_type": category.replace("_", " ").title(),
        "violation_summary": "",
        "penalty_amount": "",
        "order_url": order_url,
    }


# =============================================================================
# NSE Defaulter Scraper
# =============================================================================

def scrape_nse_defaulters() -> list[dict]:
    """Scrape NSE defaulter/expelled members from their static HTML page."""
    log.info("Fetching NSE defaulter page...")
    records = []

    try:
        resp = SESSION.get(NSE_DEFAULTER_URL, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        log.error("NSE request failed: %s", e)
        return records

    soup = BeautifulSoup(resp.text, "html.parser")

    # NSE uses clean HTML tables with headers:
    # DATE OF DECLARATION | DEFAULTER MEMBERS | REASONS | DIRECTORS/PARTNERS | COPY OF ORDER
    for table in soup.find_all("table"):
        headers = [th.get_text(strip=True).upper() for th in table.find_all("th")]
        if not any("DEFAULTER" in h or "MEMBER" in h for h in headers):
            continue

        for row in table.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 2:
                continue

            date_raw = cells[0].get_text(strip=True)
            member_name = cells[1].get_text(strip=True)
            reasons = cells[2].get_text(strip=True) if len(cells) > 2 else ""
            directors = cells[3].get_text(strip=True) if len(cells) > 3 else ""

            # Get PDF link if available
            order_url = ""
            if len(cells) > 4:
                pdf_link = cells[4].find("a")
                if pdf_link and pdf_link.get("href"):
                    order_url = urljoin(NSE_DEFAULTER_URL, pdf_link["href"])

            if not member_name or len(member_name) < 3:
                continue

            # Truncate reasons to keep DB manageable
            violation_summary = reasons[:500] if reasons else ""

            records.append({
                "source": "nse_defaulter",
                "entity_name": member_name,
                "entity_name_norm": normalize_name(member_name),
                "reg_no": "",
                "order_date": parse_date(date_raw),
                "order_type": "Defaulter",
                "violation_summary": violation_summary,
                "penalty_amount": "",
                "order_url": order_url,
            })

    log.info("NSE defaulters: scraped %d records", len(records))
    return records


# =============================================================================
# Database operations
# =============================================================================

def save_records(records: list[dict]) -> int:
    """Insert enforcement records, replacing existing ones by source."""
    if not records:
        return 0

    now = int(time.time())
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    # Ensure table exists
    cur.execute("""
        CREATE TABLE IF NOT EXISTS enforcement (
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

    inserted = 0
    seen = set()  # deduplicate by (source, entity_name_norm, order_url or order_date)
    for r in records:
        # Use order_url as part of dedup key if available (most unique identifier)
        dedup_id = r.get("order_url") or r.get("order_date", "")
        dedup_key = (r["source"], r["entity_name_norm"], dedup_id)
        if dedup_key in seen:
            continue
        seen.add(dedup_key)
        try:
            cur.execute("""
                INSERT INTO enforcement
                    (source, entity_name, entity_name_norm, reg_no,
                     order_date, order_type, violation_summary,
                     penalty_amount, order_url, imported_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                r["source"], r["entity_name"], r["entity_name_norm"],
                r.get("reg_no", ""), r.get("order_date", ""),
                r.get("order_type", ""), r.get("violation_summary", ""),
                r.get("penalty_amount", ""), r.get("order_url", ""),
                now,
            ))
            inserted += 1
        except sqlite3.Error as e:
            log.warning("Failed to insert record: %s — %s", r.get("entity_name"), e)

    conn.commit()
    conn.close()
    log.info("Saved %d enforcement records to %s", inserted, DB_PATH)
    return inserted


def ensure_table():
    """Create enforcement table if it doesn't exist."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS enforcement (
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
    conn.execute("CREATE INDEX IF NOT EXISTS idx_enforcement_name_norm ON enforcement(entity_name_norm)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_enforcement_regno ON enforcement(reg_no)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_enforcement_source ON enforcement(source)")
    conn.commit()
    conn.close()


def clear_source(source: str) -> int:
    """Remove all records for a given source before re-importing."""
    ensure_table()
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.execute("DELETE FROM enforcement WHERE source=?", (source,))
    deleted = cur.rowcount
    conn.commit()
    conn.close()
    if deleted:
        log.info("Cleared %d existing %s records", deleted, source)
    return deleted


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Refresh enforcement history data")
    parser.add_argument("--sebi-only", action="store_true", help="Only scrape SEBI orders")
    parser.add_argument("--nse-only", action="store_true", help="Only scrape NSE defaulters")
    args = parser.parse_args()

    all_records = []

    if not args.nse_only:
        clear_source("sebi_order")
        for cat, path in SEBI_ORDER_CATEGORIES.items():
            records = scrape_sebi_category(cat, path)
            all_records.extend(records)

    if not args.sebi_only:
        clear_source("nse_defaulter")
        records = scrape_nse_defaulters()
        all_records.extend(records)

    total = save_records(all_records)
    log.info("=== Enforcement refresh complete: %d total records ===", total)


if __name__ == "__main__":
    main()
