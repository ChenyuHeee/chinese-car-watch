"""
Core scraper for Chinese automotive sales data from xl.16888.com.

Data sources:
  - style.html  → model-level sales ranking
  - ev.html     → EV-only sales ranking
  - brand.html  → brand-level sales ranking
  - factory.html → manufacturer-level sales ranking

Usage:
  python scripts/scrape_sales.py           # scrape all, save to data/
  python scripts/scrape_sales.py --type ev  # EV only
  python scripts/scrape_sales.py --month 202605  # specific month
"""

import argparse
import csv
import logging
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

BASE = "https://xl.16888.com"
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"

# ── page types ──────────────────────────────────────────────
PAGES = {
    "style":   {"url": "/style.html",   "dir": "sales",  "label": "车型销量"},
    "ev":      {"url": "/ev.html",      "dir": "sales",  "label": "电动车销量"},
    "brand":   {"url": "/brand.html",   "dir": "brands", "label": "品牌销量"},
    "factory": {"url": "/factory.html", "dir": "brands", "label": "厂商销量"},
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# proxy support — set via env or CLI
PROXIES: dict = {}
if os.environ.get("HTTP_PROXY"):
    PROXIES["http"] = os.environ["HTTP_PROXY"]
if os.environ.get("HTTPS_PROXY"):
    PROXIES["https"] = os.environ["HTTPS_PROXY"]


def _fetch(url: str, retries: int = 3) -> Optional[str]:
    """Fetch a URL with retries and exponential backoff."""
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=HEADERS, proxies=PROXIES or None, timeout=30)
            resp.raise_for_status()
            resp.encoding = "utf-8"
            return resp.text
        except requests.RequestException as e:
            log.warning("fetch attempt %d/%d for %s: %s", attempt + 1, retries, url, e)
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
    log.error("failed to fetch %s after %d attempts", url, retries)
    return None


def _parse_table(html: str) -> list[dict]:
    """Extract the main ranking table from the page HTML."""
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table", class_="xlsj")
    if table is None:
        # fallback: try any table
        table = soup.find("table")
    if table is None:
        log.warning("no table found in HTML")
        return []

    rows = []
    for tr in table.find_all("tr")[1:]:  # skip header
        cells = [td.get_text(strip=True) for td in tr.find_all("td")]
        if not cells or len(cells) < 3:
            continue
        # common pattern: rank, model, sales, [price range], ...
        row = {
            "rank": cells[0],
            "name": cells[1] if len(cells) > 1 else "",
            "sales": _clean_number(cells[2]) if len(cells) > 2 else "",
        }
        # price is often the last cell with a 万 symbol
        for c in cells:
            if "万" in c and "-" in c:
                row["price_range"] = c
                break
        rows.append(row)
    return rows


def _clean_number(s: str) -> str:
    """Remove commas from numeric strings like '38,751' → '38751'."""
    return s.replace(",", "").strip()


def _detect_month(html: str) -> Optional[str]:
    """Try to extract the reporting month from page text, e.g. '2026年5月'."""
    m = re.search(r"(\d{4})\s*年\s*(\d{1,2})\s*月", html)
    if m:
        return f"{m.group(1)}{int(m.group(2)):02d}"
    return None


def _paginate(page_type: str, base_url: str, html: str) -> list[str]:
    """Given the first page HTML, return URLs for all pages."""
    soup = BeautifulSoup(html, "lxml")
    # find pagination — usually a div with page numbers
    pager = soup.find("div", class_="page")
    if pager is None:
        # try finding links that look like page numbers
        pager = soup.find("div", class_="fenye")
    urls = [base_url]
    if pager is None:
        return urls

    seen = {base_url}
    for a in pager.find_all("a"):
        href = a.get("href", "")
        if re.search(rf"{page_type}(_\d+)?\.html", href):
            full = urljoin(BASE, href)
            if full not in seen:
                urls.append(full)
                seen.add(full)
    return urls


def scrape_page(page_type: str, month: Optional[str] = None) -> list[dict]:
    """Scrape one ranking page type. Returns list of row dicts."""
    info = PAGES[page_type]
    if month:
        # e.g. style-202605.html
        url = f"{BASE}/{page_type}-{month}.html"
    else:
        url = f"{BASE}{info['url']}"

    log.info("scraping %s from %s", info["label"], url)
    html = _fetch(url)
    if html is None:
        return []

    detected_month = _detect_month(html) or month or datetime.now().strftime("%Y%m")
    log.info("detected month: %s", detected_month)

    # first page
    rows = _parse_table(html)

    # subsequent pages
    page_urls = _paginate(page_type, url, html)
    for page_url in page_urls[1:]:
        log.info("  page: %s", page_url)
        page_html = _fetch(page_url)
        if page_html:
            rows.extend(_parse_table(page_html))
        time.sleep(0.5)  # be polite

    # attach metadata
    for r in rows:
        r["month"] = detected_month
        r["type"] = page_type
        r["scraped_at"] = datetime.now().isoformat()

    log.info("  → %d rows total", len(rows))
    return rows


def save_csv(rows: list[dict], page_type: str, month: str) -> Path:
    """Save scraped rows to data/{dir}/{month}_{type}.csv"""
    info = PAGES[page_type]
    out_dir = DATA_DIR / info["dir"] / month[:4]
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{month}_{page_type}.csv"

    if not rows:
        log.warning("no rows to save for %s/%s", page_type, month)
        return out_path

    fieldnames = list(rows[0].keys())
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    log.info("saved %d rows → %s", len(rows), out_path)
    return out_path


# ── CLI ──────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Scrape Chinese auto sales data")
    parser.add_argument("--type", choices=list(PAGES.keys()), default="all",
                        help="page type to scrape (default: all)")
    parser.add_argument("--month", help="month in YYYYMM format (default: latest)")
    args = parser.parse_args()

    if args.type == "all":
        types = list(PAGES.keys())
    else:
        types = [args.type]

    all_rows: dict[str, list[dict]] = {}
    for t in types:
        rows = scrape_page(t, args.month)
        if rows:
            month = rows[0]["month"]
            save_csv(rows, t, month)
            all_rows[t] = rows
        time.sleep(1)

    # quick summary
    print("\n" + "=" * 50)
    print("SCRAPE SUMMARY")
    print("=" * 50)
    for t, rows in all_rows.items():
        print(f"  {PAGES[t]['label']}: {len(rows)} rows")
    print("=" * 50)


if __name__ == "__main__":
    main()
