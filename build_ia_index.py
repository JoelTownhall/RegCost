#!/usr/bin/env python3
"""
One-shot scraper to build reference_docs/ia_index.json from the OIA website.
Scrapes all listing pages + detail pages to extract title, department, date,
href, and OIA assessment rating for every published Impact Analysis.

Run once locally, then commit the resulting ia_index.json.

Usage:
    python build_ia_index.py
"""
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://oia.pmc.gov.au"
LISTING_URL = f"{BASE_URL}/published-impact-analyses-and-reports"
OUTPUT = Path("reference_docs/ia_index.json")
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; OIA-index-builder/1.0)"}
MAX_WORKERS = 10
REQUEST_TIMEOUT = 20

RATING_MAP = {
    "exemplary": "Exemplary",
    "good practice": "Good Practice",
    "adequate": "Adequate",
    "insufficient": "Insufficient",
}


def get(url: str, retries: int = 3) -> requests.Response | None:
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()
            return r
        except Exception as e:
            if attempt == retries - 1:
                print(f"  FAILED {url}: {e}")
            else:
                time.sleep(1)
    return None


def scrape_listing_page(page_num: int) -> list[dict]:
    """Return list of IA items from one listing page (0-indexed)."""
    url = LISTING_URL if page_num == 0 else f"{LISTING_URL}?page={page_num}"
    r = get(url)
    if not r:
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    items = []
    for row in soup.select(".views-row"):
        # Skip non-IA document types
        cats = [c.get_text(strip=True) for c in row.select(".ris-cat")]
        if not any("Impact Analysis" in c for c in cats):
            continue
        title_el = row.select_one(".views-field-title a")
        if not title_el:
            continue
        title = title_el.get_text(strip=True)
        href = title_el.get("href", "")
        if href and not href.startswith("http"):
            href = BASE_URL + href
        date_el = row.select_one("time")
        date = date_el.get("datetime", "")[:10] if date_el else ""
        dept = next((c for c in cats if c not in ("Aust Gov", "Impact Analysis (IA)", "")), "")
        items.append({"title": title, "href": href, "date": date, "department": dept})
    return items


def scrape_detail_page(item: dict) -> dict:
    """Fetch the detail page and add rating + filename info."""
    if not item.get("href"):
        return {**item, "rating": "Unknown", "filename": ""}
    r = get(item["href"])
    if not r:
        return {**item, "rating": "Unknown", "filename": ""}
    soup = BeautifulSoup(r.text, "html.parser")

    # Rating: find the active option in the assessment field
    rating = "Unknown"
    rating_el = soup.select_one(".field--name-field-assessment-of-the-ris .og-option.active")
    if rating_el:
        raw = rating_el.get_text(strip=True).lower()
        rating = RATING_MAP.get(raw, raw.title())

    # Document link (Word or PDF)
    filename = ""
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        if re.search(r"\.(docx?|pdf)(\?|$)", href, re.I):
            filename = href.split("/")[-1].split("?")[0]
            break

    year = (item.get("date") or "")[:4]
    return {**item, "rating": rating, "filename": filename, "year": year}


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    # --- Phase 1: scrape all listing pages ---
    print("Phase 1: scraping listing pages...")
    # Detect last page number
    r = get(LISTING_URL)
    last_page = 0
    if r:
        soup = BeautifulSoup(r.text, "html.parser")
        last_link = soup.select_one(".pager__item--last a, a.lastpage")
        if last_link:
            m = re.search(r"page=(\d+)", last_link.get("href", ""))
            if m:
                last_page = int(m.group(1))
    print(f"  Total listing pages: {last_page + 1}")

    all_items = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(scrape_listing_page, p): p for p in range(last_page + 1)}
        for i, fut in enumerate(as_completed(futures), 1):
            page_items = fut.result()
            all_items.extend(page_items)
            print(f"  Listing pages done: {i}/{last_page + 1}  ({len(all_items)} IAs so far)", end="\r")
    print(f"\n  Found {len(all_items)} Impact Analysis items total.")

    # --- Phase 2: fetch detail pages for ratings ---
    print("Phase 2: fetching detail pages for ratings...")
    enriched = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(scrape_detail_page, item): item for item in all_items}
        for i, fut in enumerate(as_completed(futures), 1):
            enriched.append(fut.result())
            print(f"  Detail pages done: {i}/{len(all_items)}", end="\r")
    print(f"\n  Done. Ratings found: {sum(1 for e in enriched if e['rating'] != 'Unknown')}/{len(enriched)}")

    # Sort by date descending
    enriched.sort(key=lambda x: x.get("date", ""), reverse=True)

    OUTPUT.write_text(json.dumps(enriched, indent=2, ensure_ascii=False))
    print(f"\nSaved {len(enriched)} entries to {OUTPUT}")

    # Rating summary
    from collections import Counter
    counts = Counter(e["rating"] for e in enriched)
    for rating, count in sorted(counts.items()):
        print(f"  {rating}: {count}")


if __name__ == "__main__":
    main()
