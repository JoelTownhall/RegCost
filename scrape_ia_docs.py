#!/usr/bin/env python3
"""
Scraper for OIA (Office of Impact Analysis) Impact Analysis documents.

Downloads Word documents (.docx/.doc) from the published impact analyses at:
    https://oia.pmc.gov.au/published-impact-analyses-and-reports/

Only downloads items where Document type = "Impact Analysis (IA)".
Expected ~300-400 documents across ~150 listing pages.

Uses Playwright because the site returns 403 to plain HTTP requests.

Usage:
    python scrape_ia_docs.py
    python scrape_ia_docs.py --resume
    python scrape_ia_docs.py --max-pages 10 --delay 2.0
    python scrape_ia_docs.py --output ./data/ia_docs
    python scrape_ia_docs.py --debug-page 1
"""

import asyncio
import json
import logging
import re
import argparse
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict

import requests
from playwright.async_api import (
    async_playwright, Page, BrowserContext,
    TimeoutError as PlaywrightTimeout,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_URL = "https://oia.pmc.gov.au"
LISTING_URL = f"{BASE_URL}/published-impact-analyses-and-reports"
TARGET_DOC_TYPE = "Impact Analysis (IA)"

# Drupal-style pagination is 0-indexed: ?page=0, ?page=1, …
# Some Drupal sites also use /page/2, /page/3, …
# We try the query-string form first, then fall back to path form.

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)


def setup_logging(log_file: Optional[Path] = None, debug: bool = False):
    level = logging.DEBUG if debug else logging.INFO
    fmt = "%(asctime)s - %(levelname)s - %(message)s"
    handlers: list = [logging.StreamHandler()]
    if log_file:
        handlers.append(logging.FileHandler(log_file))
    logging.basicConfig(level=level, format=fmt, handlers=handlers)


# ---------------------------------------------------------------------------
# Helper: safe filename
# ---------------------------------------------------------------------------

def safe_filename(text: str, max_len: int = 100) -> str:
    """Return a filesystem-safe version of *text*."""
    s = re.sub(r'[^\w\s\-]', '', text)
    s = re.sub(r'\s+', '_', s.strip())
    return s[:max_len]


# ---------------------------------------------------------------------------
# Scraper
# ---------------------------------------------------------------------------

class OIAIAScraper:
    """
    Two-phase scraper for OIA Impact Analysis documents.

    Phase 1  – Walk all listing pages, collect metadata for every item whose
               Document type contains "Impact Analysis (IA)".
    Phase 2  – Visit each item's detail page, find the Word document link,
               and download it.
    """

    def __init__(self, output_dir: Path, delay: float = 2.0,
                 headless: bool = True):
        self.output_dir = output_dir
        self.delay = delay
        self.headless = headless

        self.docs_dir = output_dir / "documents"
        self.meta_dir = output_dir / "metadata"
        self.progress_file = output_dir / "progress.json"
        self.index_file = output_dir / "index.json"
        self.log_file = output_dir / "scraper.log"

        for d in (self.docs_dir, self.meta_dir):
            d.mkdir(parents=True, exist_ok=True)

        self.progress = self._load_progress()
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    # ------------------------------------------------------------------
    # Progress persistence
    # ------------------------------------------------------------------

    def _load_progress(self) -> Dict:
        if self.progress_file.exists():
            with open(self.progress_file, encoding="utf-8") as f:
                raw = json.load(f)
            return {
                "pages_done": set(raw.get("pages_done", [])),
                "completed": set(raw.get("completed", [])),
                "failed": set(raw.get("failed", [])),
                "items": raw.get("items", []),
            }
        return {
            "pages_done": set(),
            "completed": set(),
            "failed": set(),
            "items": [],
        }

    def _save_progress(self):
        data = {
            "pages_done": sorted(self.progress["pages_done"]),
            "completed": sorted(self.progress["completed"]),
            "failed": sorted(self.progress["failed"]),
            "items": self.progress["items"],
            "updated_at": datetime.now().isoformat(),
        }
        with open(self.progress_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    # ------------------------------------------------------------------
    # Browser helpers
    # ------------------------------------------------------------------

    async def _init_browser(self):
        self._pw = await async_playwright().start()
        browser = await self._pw.chromium.launch(
            headless=self.headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        self._context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            extra_http_headers={"Accept-Language": "en-AU,en;q=0.9"},
            accept_downloads=True,
        )
        self._page = await self._context.new_page()
        self._browser = browser
        logger.info("Browser ready (headless=%s)", self.headless)

    async def _close_browser(self):
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()
        logger.info("Browser closed")

    async def _goto(self, url: str, timeout: int = 30_000) -> bool:
        """Navigate to *url*, return True on success."""
        try:
            resp = await self._page.goto(url, wait_until="domcontentloaded",
                                         timeout=timeout)
            if resp and resp.status < 400:
                return True
            logger.warning("HTTP %s for %s", resp.status if resp else "?", url)
            return False
        except PlaywrightTimeout:
            logger.warning("Timeout navigating to %s", url)
            return False

    # ------------------------------------------------------------------
    # Phase 1 helpers
    # ------------------------------------------------------------------

    def _listing_url(self, page_num: int) -> str:
        """Return the URL for listing page *page_num* (1-based)."""
        if page_num == 1:
            return LISTING_URL
        # Drupal's Views pagination uses 0-based ?page= parameter
        return f"{LISTING_URL}?page={page_num - 1}"

    async def _detect_total_pages(self) -> int:
        """
        Try to read total page count from pagination on the first listing page.
        Falls back to 150 (user-provided estimate).
        """
        ok = await self._goto(self._listing_url(1))
        if not ok:
            return 150

        await asyncio.sleep(1)

        total = await self._page.evaluate(r"""() => {
            // Drupal pager: look for "last page" link
            const lastSelectors = [
                'a[title="Go to last page"]',
                '.pager__item--last a',
                'li.last a',
                'a.last',
            ];
            for (const sel of lastSelectors) {
                const el = document.querySelector(sel);
                if (el && el.href) {
                    const m = el.href.match(/[?&]page=(\d+)/);
                    if (m) return parseInt(m[1]) + 1;   // 0-indexed → 1-based count
                    const m2 = el.href.match(/\/page\/(\d+)/);
                    if (m2) return parseInt(m2[1]);
                }
            }
            // Scan all pager links for the highest page number
            let max = 0;
            document.querySelectorAll('a[href]').forEach(a => {
                let m = a.href.match(/[?&]page=(\d+)/);
                if (m) max = Math.max(max, parseInt(m[1]));
                m = a.href.match(/\/page\/(\d+)/);
                if (m) max = Math.max(max, parseInt(m[1]));
            });
            if (max > 0) return max + 1;   // 0-indexed last page → count
            // "Page X of Y" text
            const bodyText = document.body.innerText;
            const m2 = bodyText.match(/page\s+\d+\s+of\s+(\d+)/i);
            if (m2) return parseInt(m2[1]);
            return null;
        }""")

        if total and isinstance(total, int) and total > 0:
            logger.info("Detected %d listing pages", total)
            return total

        logger.info("Could not detect page count; defaulting to 150")
        return 150

    async def _scrape_listing_page(self, page_num: int) -> List[Dict]:
        """
        Scrape one listing page and return items where doc type is IA.
        Each returned dict has keys: title, href, doc_type, date, portfolio,
        raw_text (truncated).
        """
        url = self._listing_url(page_num)
        logger.info("Listing page %d: %s", page_num, url)

        ok = await self._goto(url)
        if not ok:
            return []

        await asyncio.sleep(0.8)

        # Dump raw HTML on first page (helps debug selector issues)
        if page_num == 1:
            html = await self._page.content()
            debug_path = self.output_dir / "debug_page1.html"
            debug_path.write_text(html, encoding="utf-8")
            logger.debug("Saved first-page HTML to %s", debug_path)

        items = await self._page.evaluate(r"""() => {
            // -------------------------------------------------------
            // Strategy: look for rows/cards that each represent one IA
            // item.  Government Drupal sites typically use one of:
            //   - <article class="node--type-...">
            //   - <div class="views-row">
            //   - <li> inside a <ul class="item-list"> or .view-content
            //   - <tr> in a table
            // -------------------------------------------------------

            function extractItems(containerEl) {
                const results = [];
                const text = containerEl.innerText || '';
                if (!text.trim()) return results;

                // Title / link
                const titleEl = containerEl.querySelector(
                    'h2 a, h3 a, h4 a, .title a, a.title, ' +
                    '.field--name-title a, .node__title a'
                );
                const title = titleEl ? titleEl.innerText.trim() : '';
                const href  = titleEl ? titleEl.href : '';

                // Document type
                let docType = '';
                // Look for a labelled field first (Drupal field pattern)
                containerEl.querySelectorAll(
                    '.field--name-field-document-type, ' +
                    '[class*="document-type"], ' +
                    '[class*="doc-type"]'
                ).forEach(el => {
                    const v = el.innerText.trim();
                    if (v) docType = v;
                });
                if (!docType) {
                    const m = text.match(/Document\s+type[\s:]+([^\n\r|]+)/i);
                    if (m) docType = m[1].trim();
                }

                // Date
                let date = '';
                containerEl.querySelectorAll(
                    '.field--name-field-date, time, [class*="date"]'
                ).forEach(el => {
                    const v = el.getAttribute('datetime') || el.innerText.trim();
                    if (v && !date) date = v;
                });
                if (!date) {
                    const m = text.match(
                        /(?:Date|Published)[:\s]+(\d{1,2}\s+\w+\s+\d{4}|\d{4}-\d{2}-\d{2}|\w+\s+\d{4})/i
                    );
                    if (m) date = m[1].trim();
                }

                // Portfolio / Department
                let portfolio = '';
                containerEl.querySelectorAll(
                    '.field--name-field-portfolio, ' +
                    '[class*="portfolio"], ' +
                    '[class*="department"]'
                ).forEach(el => {
                    const v = el.innerText.trim();
                    if (v && !portfolio) portfolio = v;
                });
                if (!portfolio) {
                    const m = text.match(
                        /(?:Portfolio|Department|Agency|Proponent)[\s:]+([^\n\r|]+)/i
                    );
                    if (m) portfolio = m[1].trim();
                }

                results.push({
                    title,
                    href,
                    docType,
                    date,
                    portfolio,
                    rawText: text.substring(0, 600),
                });
                return results;
            }

            // Try container selectors from most-specific to most-generic
            const containerSelectors = [
                'article',
                '.views-row',
                '.view-content > div',
                '.view-content li',
                '.item-list li',
                'tbody tr',
            ];

            let rows = [];
            for (const sel of containerSelectors) {
                const found = document.querySelectorAll(sel);
                if (found.length >= 2) {
                    rows = Array.from(found);
                    break;
                }
            }

            // Last-resort: any element containing "Document type" text
            // that isn't a descendant of another such element
            if (rows.length === 0) {
                const candidates = Array.from(document.querySelectorAll('*'))
                    .filter(el => {
                        const t = el.innerText || '';
                        return t.includes('Document type') && t.length < 3000
                            && el.children.length > 0 && el.children.length < 30;
                    });
                // Keep only the deepest (most specific) matches
                rows = candidates.filter(c =>
                    !candidates.some(p => p !== c && p.contains(c))
                );
            }

            const all = [];
            rows.forEach(row => all.push(...extractItems(row)));
            return all;
        }""")

        if not items:
            logger.warning(
                "Page %d: no items found. "
                "Check debug_page1.html to inspect the HTML structure.",
                page_num,
            )
            return []

        # Filter to Impact Analysis (IA) only
        ia = [
            it for it in items
            if "impact analysis" in it.get("docType", "").lower()
        ]
        logger.info(
            "Page %d: %d total items, %d are Impact Analysis (IA)",
            page_num, len(items), len(ia),
        )
        return ia

    # ------------------------------------------------------------------
    # Phase 2 helpers
    # ------------------------------------------------------------------

    async def _find_word_doc_url(self, detail_url: str) -> Optional[str]:
        """
        Navigate to the item's detail page and return the URL of the first
        Word document (.docx / .doc) found.
        """
        ok = await self._goto(detail_url)
        if not ok:
            return None

        await asyncio.sleep(0.5)

        url = await self._page.evaluate(r"""() => {
            const links = Array.from(document.querySelectorAll('a[href]'));

            // 1. Direct .docx / .doc extension
            for (const a of links) {
                if (/\.(docx?)\b/i.test(a.href)) return a.href;
            }

            // 2. Link whose visible text mentions "Word" or "DOCX"
            for (const a of links) {
                const txt = (a.innerText || a.title || '').toLowerCase();
                if ((txt.includes('word') || txt.includes('docx') || txt.includes('.doc'))
                    && a.href) {
                    return a.href;
                }
            }

            // 3. Any download link that might be a Word file
            for (const a of links) {
                const txt = (a.innerText || '').toLowerCase();
                if ((txt.includes('download') || txt.includes('file')) && a.href
                    && !a.href.endsWith('.pdf')) {
                    return a.href;
                }
            }

            return null;
        }""")

        if url:
            logger.debug("  Word doc URL: %s", url)
        else:
            logger.warning("  No Word doc link found at %s", detail_url)

        return url

    async def _download_file(self, url: str, dest: Path) -> bool:
        """
        Download *url* to *dest*.

        Tries three strategies in order:
          1. Playwright's built-in download capture (handles redirects / auth).
          2. Direct HTTP with session cookies copied from the browser.
          3. Plain requests (no cookies).
        """
        if dest.exists() and dest.stat().st_size > 0:
            logger.info("  Already exists: %s", dest.name)
            return True

        # Strategy 1 – Playwright download
        try:
            async with self._page.expect_download(timeout=60_000) as dl_info:
                await self._page.evaluate(
                    "url => { window.location.href = url; }", url
                )
            dl = await dl_info.value
            await dl.save_as(dest)
            size_kb = dest.stat().st_size / 1024
            logger.info("  Downloaded (playwright): %s  (%.1f KB)", dest.name, size_kb)
            return True
        except Exception as e:
            logger.debug("  Playwright download failed (%s), trying requests…", e)

        # Strategy 2 – requests with browser cookies
        try:
            cookies = await self._context.cookies()
            sess = requests.Session()
            for c in cookies:
                sess.cookies.set(c["name"], c["value"],
                                 domain=c.get("domain", ""))
            sess.headers.update({
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Referer": BASE_URL,
            })
            resp = sess.get(url, timeout=60, stream=True)
            resp.raise_for_status()
            with open(dest, "wb") as fh:
                for chunk in resp.iter_content(chunk_size=8192):
                    fh.write(chunk)
            size_kb = dest.stat().st_size / 1024
            logger.info("  Downloaded (requests+cookies): %s  (%.1f KB)",
                        dest.name, size_kb)
            return True
        except Exception as e:
            logger.debug("  requests+cookies failed (%s), trying plain…", e)

        # Strategy 3 – plain requests
        try:
            resp = requests.get(
                url, timeout=60, stream=True,
                headers={"User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )},
            )
            resp.raise_for_status()
            with open(dest, "wb") as fh:
                for chunk in resp.iter_content(chunk_size=8192):
                    fh.write(chunk)
            size_kb = dest.stat().st_size / 1024
            logger.info("  Downloaded (plain): %s  (%.1f KB)", dest.name, size_kb)
            return True
        except Exception as e:
            logger.error("  All download strategies failed for %s: %s", url, e)
            return False

    # ------------------------------------------------------------------
    # Main run loop
    # ------------------------------------------------------------------

    async def run(self, max_pages: Optional[int] = None,
                  resume: bool = False, debug_page: Optional[int] = None):
        """
        Entry point.

        If *debug_page* is given, scrape only that page and print results
        without downloading anything (useful for inspecting the site structure).
        """
        await self._init_browser()

        try:
            # ---- Debug mode ------------------------------------------------
            if debug_page is not None:
                await self._debug_single_page(debug_page)
                return

            # ---- Phase 1: collect IA items ---------------------------------
            total_pages = await self._detect_total_pages()
            if max_pages:
                total_pages = min(total_pages, max_pages)
            logger.info("Scanning %d listing pages …", total_pages)

            all_items: List[Dict] = list(self.progress["items"])

            for page_num in range(1, total_pages + 1):
                if resume and page_num in self.progress["pages_done"]:
                    logger.debug("Skip page %d (already done)", page_num)
                    continue

                page_items = await self._scrape_listing_page(page_num)
                all_items.extend(page_items)
                self.progress["pages_done"].add(page_num)
                self.progress["items"] = all_items
                self._save_progress()
                await asyncio.sleep(self.delay)

            logger.info(
                "Phase 1 complete. %d Impact Analysis (IA) items found.",
                len(all_items),
            )

            # ---- Phase 2: download documents --------------------------------
            logger.info("Downloading Word documents …")
            downloaded = skipped = failed = 0

            for idx, item in enumerate(all_items, start=1):
                item_id = item.get("href") or f"item_{idx}"

                if resume and item_id in self.progress["completed"]:
                    skipped += 1
                    continue
                if resume and item_id in self.progress["failed"]:
                    # Retry previously failed items
                    self.progress["failed"].discard(item_id)

                title_short = (item.get("title") or "Unknown")[:70]
                logger.info("[%d/%d] %s", idx, len(all_items), title_short)

                href = item.get("href", "")
                if not href:
                    logger.warning("  No detail URL – skipping")
                    self.progress["failed"].add(item_id)
                    failed += 1
                    self._save_progress()
                    continue

                # Find Word document URL on the detail page
                word_url = await self._find_word_doc_url(href)
                await asyncio.sleep(0.5)

                if not word_url:
                    self.progress["failed"].add(item_id)
                    failed += 1
                    self._save_progress()
                    await asyncio.sleep(self.delay)
                    continue

                # Build destination filename
                title_safe = safe_filename(item.get("title") or f"document_{idx}")
                date_safe = safe_filename(item.get("date") or "")
                ext = ".docx" if ".docx" in word_url.lower() else ".doc"
                if date_safe:
                    filename = f"{title_safe}_{date_safe}{ext}"
                else:
                    filename = f"{title_safe}{ext}"
                dest = self.docs_dir / filename

                success = await self._download_file(word_url, dest)

                if success:
                    item.update({
                        "downloaded_file": filename,
                        "download_url": word_url,
                        "downloaded_at": datetime.now().isoformat(),
                    })
                    self.progress["completed"].add(item_id)
                    downloaded += 1

                    # Per-item metadata
                    meta_path = self.meta_dir / f"{title_safe}.json"
                    with open(meta_path, "w", encoding="utf-8") as f:
                        json.dump(item, f, indent=2, ensure_ascii=False)
                else:
                    self.progress["failed"].add(item_id)
                    failed += 1

                self._save_progress()
                await asyncio.sleep(self.delay)

            # ---- Final index -----------------------------------------------
            index = {
                "scraped_at": datetime.now().isoformat(),
                "source": LISTING_URL,
                "total_ia_items": len(all_items),
                "downloaded": downloaded,
                "skipped": skipped,
                "failed": failed,
                "items": all_items,
            }
            with open(self.index_file, "w", encoding="utf-8") as f:
                json.dump(index, f, indent=2, ensure_ascii=False)

            logger.info("=" * 60)
            logger.info("Done.")
            logger.info("  IA items found : %d", len(all_items))
            logger.info("  Downloaded     : %d", downloaded)
            logger.info("  Skipped (done) : %d", skipped)
            logger.info("  Failed         : %d", failed)
            logger.info("  Output dir     : %s", self.docs_dir)

        except KeyboardInterrupt:
            logger.info("\nInterrupted by user. Progress saved.")
            self._save_progress()
        finally:
            await self._close_browser()

    # ------------------------------------------------------------------
    # Debug helper
    # ------------------------------------------------------------------

    async def _debug_single_page(self, page_num: int):
        """
        Scrape one listing page and print what was found, then save the
        raw HTML.  Used to verify selectors before a full run.
        """
        logger.info("=== DEBUG MODE: page %d ===", page_num)
        items = await self._scrape_listing_page(page_num)
        if not items:
            print("\nNo items found. Check debug_page1.html in the output dir.")
            return

        print(f"\nFound {len(items)} Impact Analysis (IA) items on page {page_num}:\n")
        for i, it in enumerate(items, 1):
            print(f"  [{i}] {it.get('title', '(no title)')}")
            print(f"       href      : {it.get('href', '')}")
            print(f"       doc_type  : {it.get('docType', '')}")
            print(f"       date      : {it.get('date', '')}")
            print(f"       portfolio : {it.get('portfolio', '')}")
            print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Download Impact Analysis (IA) Word documents from "
            "https://oia.pmc.gov.au/published-impact-analyses-and-reports/"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full run (all ~150 pages):
  python scrape_ia_docs.py

  # Resume a previous run:
  python scrape_ia_docs.py --resume

  # Test with first 3 pages only:
  python scrape_ia_docs.py --max-pages 3

  # Inspect page structure without downloading:
  python scrape_ia_docs.py --debug-page 1

  # Custom output directory:
  python scrape_ia_docs.py --output ./data/oia_ia_docs
""",
    )
    parser.add_argument(
        "--output", "-o", default="./data/oia_impact_analyses",
        help="Output directory (default: ./data/oia_impact_analyses)",
    )
    parser.add_argument(
        "--max-pages", "-m", type=int, default=None,
        help="Max listing pages to scrape (default: all, ~150)",
    )
    parser.add_argument(
        "--delay", "-d", type=float, default=2.0,
        help="Seconds between requests (default: 2.0)",
    )
    parser.add_argument(
        "--resume", "-r", action="store_true",
        help="Resume from saved progress (skip already-done pages/items)",
    )
    parser.add_argument(
        "--debug-page", type=int, default=None, metavar="N",
        help="Scrape only page N and print results (no downloads). "
             "Useful for inspecting site structure.",
    )
    parser.add_argument(
        "--no-headless", action="store_true",
        help="Show browser window (useful for debugging)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Enable debug logging",
    )

    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    setup_logging(
        log_file=output_dir / "scraper.log",
        debug=args.verbose,
    )

    scraper = OIAIAScraper(
        output_dir=output_dir,
        delay=args.delay,
        headless=not args.no_headless,
    )

    asyncio.run(
        scraper.run(
            max_pages=args.max_pages,
            resume=args.resume,
            debug_page=args.debug_page,
        )
    )


if __name__ == "__main__":
    main()
