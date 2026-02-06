#!/usr/bin/env python3
"""
Playwright-based scraper for Australian Federal Register of Legislation.

Uses the legislation.gov.au API to list all legislation items, then Playwright
to extract full text from each item's rendered page (via the epub viewer iframe).

Usage:
    python playwright_scraper.py --collection act --max 100
    python playwright_scraper.py --collection all
    python playwright_scraper.py --resume
"""

import asyncio
import json
import logging
import re
import argparse
import requests
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict

from playwright.async_api import async_playwright, Page, Browser, TimeoutError as PlaywrightTimeout

import config

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(config.LOGS_DIR / 'playwright_scraper.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class LegislationPlaywrightScraper:
    """
    Scraper for Australian Federal Register of Legislation.

    Phase 1: Uses the OData API to list all in-force legislation.
    Phase 2: Uses Playwright to extract full text from each item's /latest/text page.
    """

    BASE_URL = "https://www.legislation.gov.au"
    API_URL = "https://api.prod.legislation.gov.au/v1"

    COLLECTION_MAP = {
        'act': 'Act',
        'legislativeinstrument': 'LegislativeInstrument',
        'notifiableinstrument': 'NotifiableInstrument',
    }

    def __init__(self, output_dir: Optional[Path] = None, delay: float = 1.5):
        self.output_dir = output_dir or config.DATA_DIR
        self.delay = delay
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None

        # Setup directories
        self.dirs = {
            'text': self.output_dir / 'legislation_text',
            'metadata': self.output_dir / 'metadata',
        }
        for d in self.dirs.values():
            d.mkdir(parents=True, exist_ok=True)

        # Progress tracking
        self.progress_file = self.output_dir / 'scraper_progress.json'
        self.progress = self._load_progress()

    def _load_progress(self) -> Dict:
        if self.progress_file.exists():
            with open(self.progress_file, encoding='utf-8') as f:
                data = json.load(f)
                return {
                    'completed': set(data.get('completed', [])),
                    'failed': set(data.get('failed', [])),
                }
        return {'completed': set(), 'failed': set()}

    def _save_progress(self):
        data = {
            'completed': list(self.progress['completed']),
            'failed': list(self.progress['failed']),
            'updated_at': datetime.now().isoformat(),
        }
        with open(self.progress_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    # -------------------------------------------------------------------------
    # Phase 1: Use API to list all legislation
    # -------------------------------------------------------------------------

    def get_all_titles(self, collection: str) -> List[Dict]:
        """
        Get all in-force principal legislation IDs and names from the API.
        Uses OData pagination ($top/$skip).
        """
        api_collection = self.COLLECTION_MAP.get(collection)
        if not api_collection:
            logger.error(f"Unknown collection: {collection}")
            return []

        all_items = []
        page_size = 100
        skip = 0

        logger.info(f"Fetching {api_collection} titles from API...")

        while True:
            # Note: Don't use $select - API returns statusHistory which has dates
            url = (
                f"{self.API_URL}/Titles?"
                f"$filter=collection eq '{api_collection}' and isInForce eq true and isPrincipal eq true"
                f"&$top={page_size}&$skip={skip}"
                f"&$orderby=name"
                f"&$count=true"
            )

            try:
                response = requests.get(url, timeout=30)
                response.raise_for_status()
                data = response.json()

                items = data.get('value', [])
                if not items:
                    break

                total_count = data.get('@odata.count', '?')

                for item in items:
                    # Extract dates from statusHistory
                    status_history = item.get('statusHistory', [])
                    commencement_date = None
                    repeal_date = None
                    for status in status_history:
                        if status.get('status') == 'InForce':
                            commencement_date = status.get('start')
                        elif status.get('status') == 'Repealed':
                            repeal_date = status.get('start')

                    all_items.append({
                        'register_id': item['id'],
                        'title': item['name'],
                        'collection': collection,
                        'making_date': item.get('makingDate'),
                        'commencement_date': commencement_date,
                        'repeal_date': repeal_date,
                        'is_in_force': item.get('isInForce'),
                    })

                logger.info(f"  Fetched {len(all_items)}/{total_count} titles...")
                skip += page_size

                if len(items) < page_size:
                    break

            except Exception as e:
                logger.error(f"API error at skip={skip}: {e}")
                # Retry once after a pause
                import time
                time.sleep(5)
                try:
                    response = requests.get(url, timeout=30)
                    response.raise_for_status()
                    data = response.json()
                    items = data.get('value', [])
                    for item in items:
                        # Extract dates from statusHistory
                        status_history = item.get('statusHistory', [])
                        commencement_date = None
                        repeal_date = None
                        for status in status_history:
                            if status.get('status') == 'InForce':
                                commencement_date = status.get('start')
                            elif status.get('status') == 'Repealed':
                                repeal_date = status.get('start')

                        all_items.append({
                            'register_id': item['id'],
                            'title': item['name'],
                            'collection': collection,
                            'making_date': item.get('makingDate'),
                            'commencement_date': commencement_date,
                            'repeal_date': repeal_date,
                            'is_in_force': item.get('isInForce'),
                        })
                    skip += page_size
                    if len(items) < page_size:
                        break
                except Exception as e2:
                    logger.error(f"API retry also failed: {e2}")
                    break

        logger.info(f"Total {api_collection} titles: {len(all_items)}")
        return all_items

    # -------------------------------------------------------------------------
    # Phase 2: Use Playwright to extract text
    # -------------------------------------------------------------------------

    async def init_browser(self):
        """Initialize Playwright browser."""
        self._playwright = await async_playwright().start()
        self.browser = await self._playwright.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled']
        )
        self.page = await self.browser.new_page()
        await self.page.set_extra_http_headers({
            'Accept-Language': 'en-AU,en;q=0.9',
        })
        logger.info("Browser initialized")

    async def close_browser(self):
        """Close Playwright browser."""
        if self.browser:
            await self.browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("Browser closed")

    async def get_legislation_text(self, register_id: str) -> Optional[str]:
        """
        Get the text content of a legislation document.

        The legislation.gov.au site loads the full text in an iframe with a blob URL
        inside the frl-epub-viewer component on the /latest/text page.
        """
        text_url = f"{self.BASE_URL}/{register_id}/latest/text"

        try:
            response = await self.page.goto(text_url, wait_until='networkidle', timeout=60000)

            if not response or response.status != 200:
                logger.warning(f"HTTP {response.status if response else 'None'} for {register_id}")
                return None

            # Wait for the epub viewer iframe to load
            await asyncio.sleep(2)

            # Try to find the iframe with legislation text
            for attempt in range(3):
                iframe = await self.page.query_selector('frl-epub-viewer iframe, iframe[src^="blob:"]')

                if iframe:
                    try:
                        frame = await iframe.content_frame()
                        if frame:
                            text = await frame.evaluate('() => document.body.innerText')
                            text = text.strip()

                            if text and len(text) > 200:
                                return text
                    except Exception as e:
                        logger.debug(f"Error extracting from iframe (attempt {attempt+1}): {e}")

                # Wait a bit more for the iframe to appear
                await asyncio.sleep(2)

            logger.warning(f"Could not extract text for {register_id}")
            return None

        except PlaywrightTimeout:
            logger.warning(f"Timeout for {register_id}")
            return None
        except Exception as e:
            logger.warning(f"Error for {register_id}: {e}")
            return None

    async def process_item(self, item: Dict) -> Optional[Dict]:
        """
        Process a single legislation item - fetch text and save.
        """
        register_id = item['register_id']

        # Skip if already completed
        if register_id in self.progress['completed']:
            return None

        # Skip if previously failed (can retry with --retry-failed flag)
        if register_id in self.progress['failed']:
            return None

        logger.info(f"Processing: {item.get('title', register_id)[:70]}...")

        # Get text
        text = await self.get_legislation_text(register_id)

        if not text:
            self.progress['failed'].add(register_id)
            self._save_progress()
            return None

        # Build result
        result = {
            'id': register_id,
            'register_id': register_id,
            'title': item.get('title', ''),
            'collection': item.get('collection', ''),
            'making_date': item.get('making_date'),
            'commencement_date': item.get('commencement_date'),
            'repeal_date': item.get('repeal_date'),
            'is_in_force': item.get('is_in_force'),
            'url': f"{self.BASE_URL}/{register_id}/latest/text",
            'text': text,
            'text_length': len(text),
            'fetched_at': datetime.now().isoformat(),
        }

        # Save text to file
        text_path = self.dirs['text'] / f"{register_id}.txt"
        with open(text_path, 'w', encoding='utf-8') as f:
            f.write(text)

        # Save metadata
        meta_path = self.dirs['metadata'] / f"{register_id}.json"
        meta = {k: v for k, v in result.items() if k != 'text'}
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)

        # Update progress
        self.progress['completed'].add(register_id)
        self._save_progress()

        return result

    async def scrape_collection(self, collection: str, max_items: Optional[int] = None,
                                 retry_failed: bool = False) -> List[Dict]:
        """
        Scrape all items from a collection.
        """
        # Phase 1: Get all titles from API
        items = self.get_all_titles(collection)
        if not items:
            return []

        if retry_failed:
            # Reset failed items so they get retried
            self.progress['failed'] = set()
            self._save_progress()

        # Count how many are already done
        already_done = sum(1 for item in items if item['register_id'] in self.progress['completed'])
        to_process = len(items) - already_done
        logger.info(f"{collection}: {len(items)} total, {already_done} already done, {to_process} to process")

        if max_items:
            items = [i for i in items if i['register_id'] not in self.progress['completed']][:max_items]
            items += [i for _ in [] for i in []]  # no-op to keep type

        # Phase 2: Extract text for each item
        results = []
        items_collected = 0
        items_attempted = 0

        for i, item in enumerate(items):
            if max_items and items_collected >= max_items:
                break

            if item['register_id'] in self.progress['completed']:
                continue
            if item['register_id'] in self.progress['failed'] and not retry_failed:
                continue

            result = await self.process_item(item)
            items_attempted += 1

            if result:
                results.append(result)
                items_collected += 1

            # Progress update every 50 items
            if items_attempted % 50 == 0:
                logger.info(f"Progress: {items_attempted} attempted, {items_collected} collected, "
                           f"{len(self.progress['completed'])} total completed")

            # Rate limiting
            await asyncio.sleep(self.delay)

        logger.info(f"Completed {collection}: {items_collected} new items collected")
        return results

    async def scrape_all(self, collections: Optional[List[str]] = None,
                          max_items: Optional[int] = None,
                          retry_failed: bool = False) -> List[Dict]:
        """
        Scrape all specified collections.
        """
        if collections is None:
            collections = ['act', 'legislativeinstrument']

        await self.init_browser()

        try:
            all_results = []

            for collection in collections:
                results = await self.scrape_collection(
                    collection, max_items, retry_failed
                )
                all_results.extend(results)

            return all_results

        finally:
            await self.close_browser()

    def save_combined_data(self, results: Optional[List[Dict]] = None,
                            filepath: Optional[Path] = None):
        """
        Save all results to a combined JSON file.
        If results is None, loads from metadata files.
        """
        filepath = filepath or (config.DATA_DIR / 'scraped_legislation.json')

        if results is None:
            results = self.load_from_metadata()

        data = {
            'scraped_at': datetime.now().isoformat(),
            'source': 'legislation.gov.au (API + Playwright)',
            'total_documents': len(results),
            'regulations': results,
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved {len(results)} documents to {filepath}")

    def load_from_metadata(self) -> List[Dict]:
        """Load all scraped data from text + metadata files."""
        results = []

        for meta_file in sorted(self.dirs['metadata'].glob('*.json')):
            try:
                with open(meta_file, encoding='utf-8') as f:
                    meta = json.load(f)

                register_id = meta.get('register_id', meta_file.stem)
                text_file = self.dirs['text'] / f"{register_id}.txt"

                if text_file.exists():
                    with open(text_file, encoding='utf-8') as f:
                        text = f.read()

                    result = {**meta, 'text': text, 'text_length': len(text)}
                    results.append(result)

            except Exception as e:
                logger.error(f"Error loading {meta_file}: {e}")

        logger.info(f"Loaded {len(results)} documents from metadata files")
        return results


async def main():
    parser = argparse.ArgumentParser(
        description='Scrape Australian Federal Legislation using API + Playwright'
    )
    parser.add_argument('--collection', '-c',
                       choices=['act', 'legislativeinstrument', 'notifiableinstrument', 'all'],
                       default='all', help='Collection to scrape')
    parser.add_argument('--max', '-m', type=int, default=None,
                       help='Maximum items to scrape per collection (default: all)')
    parser.add_argument('--delay', '-d', type=float, default=1.5,
                       help='Delay between requests in seconds')
    parser.add_argument('--resume', action='store_true',
                       help='Resume from last progress (skips completed items)')
    parser.add_argument('--retry-failed', action='store_true',
                       help='Retry previously failed items')
    parser.add_argument('--output', '-o', type=str, default=None,
                       help='Output directory')
    parser.add_argument('--save-combined', action='store_true',
                       help='Save combined JSON from existing metadata files')

    args = parser.parse_args()

    output_dir = Path(args.output) if args.output else config.DATA_DIR
    scraper = LegislationPlaywrightScraper(output_dir=output_dir, delay=args.delay)

    # If just saving combined data from existing files
    if args.save_combined:
        scraper.save_combined_data()
        return

    collections = None if args.collection == 'all' else [args.collection]

    # If not resuming, clear previous progress to start fresh
    if not args.resume:
        scraper.progress = {'completed': set(), 'failed': set()}
        scraper._save_progress()

    try:
        results = await scraper.scrape_all(
            collections=collections,
            max_items=args.max,
            retry_failed=args.retry_failed
        )

        # Save combined JSON from all metadata files (includes previous runs)
        scraper.save_combined_data()

        total = len(scraper.progress['completed'])
        failed = len(scraper.progress['failed'])
        print(f"\nScrape complete: {total} documents collected, {failed} failed")

    except KeyboardInterrupt:
        print("\nInterrupted. Progress saved.")
        scraper.save_combined_data()
        total = len(scraper.progress['completed'])
        print(f"Saved {total} documents from partial scrape")


if __name__ == "__main__":
    asyncio.run(main())
