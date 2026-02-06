#!/usr/bin/env python3
"""
Scheduled API metadata update with retry logic.

This script:
1. Attempts to fetch metadata from the legislation.gov.au API
2. Logs progress to a file
3. Creates a completion marker when done
4. Can be safely re-run (idempotent)

Designed to be run by Windows Task Scheduler.
"""

import json
import logging
import sys
import time
import requests
from datetime import datetime
from pathlib import Path

# Setup paths
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR / 'data'
LOG_FILE = SCRIPT_DIR / 'logs' / 'api_update.log'
COMPLETION_MARKER = DATA_DIR / 'api_update_complete.json'
PROGRESS_FILE = DATA_DIR / 'api_update_progress.json'

LOG_FILE.parent.mkdir(exist_ok=True)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

API_URL = "https://api.prod.legislation.gov.au/v1"

COLLECTION_MAP = {
    'act': 'Act',
    'legislativeinstrument': 'LegislativeInstrument',
}


def check_api_available():
    """Test if the API is responding."""
    try:
        url = f"{API_URL}/Titles?$filter=collection eq 'Act'&$top=1"
        response = requests.get(url, timeout=30, headers={'Accept': 'application/json'})
        return response.status_code == 200
    except Exception as e:
        logger.warning(f"API check failed: {e}")
        return False


def fetch_collection_metadata(collection: str):
    """Fetch all metadata for a collection from the API."""
    api_collection = COLLECTION_MAP.get(collection)
    if not api_collection:
        return []

    all_items = []
    page_size = 100
    skip = 0

    logger.info(f"Fetching {api_collection} metadata...")

    while True:
        url = (
            f"{API_URL}/Titles?"
            f"$filter=collection eq '{api_collection}' and isInForce eq true and isPrincipal eq true"
            f"&$top={page_size}&$skip={skip}"
            f"&$orderby=name"
            f"&$count=true"
        )

        try:
            response = requests.get(url, timeout=60, headers={'Accept': 'application/json'})
            response.raise_for_status()
            data = response.json()

            items = data.get('value', [])
            if not items:
                break

            total_count = data.get('@odata.count', '?')

            for item in items:
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
                    'is_principal': item.get('isPrincipal'),
                })

            logger.info(f"  Fetched {len(all_items)}/{total_count} {api_collection} titles...")
            skip += page_size

            if len(items) < page_size:
                break

            time.sleep(0.5)

        except Exception as e:
            logger.error(f"API error at skip={skip}: {e}")
            raise

    logger.info(f"Total {api_collection}: {len(all_items)}")
    return all_items


def update_metadata_files(api_data):
    """Update metadata files with API data."""
    api_index = {item['register_id']: item for item in api_data}
    metadata_dir = DATA_DIR / 'metadata'

    updated = 0
    for meta_file in metadata_dir.glob('*.json'):
        register_id = meta_file.stem
        if register_id not in api_index:
            continue

        try:
            with open(meta_file, 'r', encoding='utf-8') as f:
                meta = json.load(f)

            api_item = api_index[register_id]
            meta['is_in_force'] = api_item.get('is_in_force')
            meta['making_date'] = api_item.get('making_date')
            meta['commencement_date'] = api_item.get('commencement_date')
            meta['repeal_date'] = api_item.get('repeal_date')
            meta['is_principal'] = api_item.get('is_principal')
            meta['api_updated_at'] = datetime.now().isoformat()

            with open(meta_file, 'w', encoding='utf-8') as f:
                json.dump(meta, f, indent=2, ensure_ascii=False)

            updated += 1

        except Exception as e:
            logger.error(f"Error updating {meta_file}: {e}")

    return updated


def regenerate_combined_json():
    """Regenerate the combined JSON file."""
    metadata_dir = DATA_DIR / 'metadata'
    text_dir = DATA_DIR / 'legislation_text'
    output_path = DATA_DIR / 'scraped_legislation.json'

    results = []
    for meta_file in sorted(metadata_dir.glob('*.json')):
        try:
            with open(meta_file, 'r', encoding='utf-8') as f:
                meta = json.load(f)

            register_id = meta.get('register_id', meta_file.stem)
            text_file = text_dir / f"{register_id}.txt"

            if text_file.exists():
                with open(text_file, 'r', encoding='utf-8') as f:
                    text = f.read()
                result = {**meta, 'text': text, 'text_length': len(text)}
                results.append(result)

        except Exception as e:
            logger.error(f"Error loading {meta_file}: {e}")

    data = {
        'scraped_at': datetime.now().isoformat(),
        'source': 'legislation.gov.au (API + Playwright)',
        'api_metadata_updated': True,
        'total_documents': len(results),
        'regulations': results,
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    logger.info(f"Saved {len(results)} documents to {output_path}")


def main():
    logger.info("=" * 60)
    logger.info("Starting scheduled API metadata update")
    logger.info("=" * 60)

    # Check if already completed
    if COMPLETION_MARKER.exists():
        logger.info("Update already completed. Exiting.")
        return 0

    # Check API availability
    logger.info("Checking API availability...")
    if not check_api_available():
        logger.warning("API not available. Will retry on next scheduled run.")
        return 1

    logger.info("API is available. Starting metadata fetch...")

    try:
        # Fetch metadata for both collections
        all_api_data = []
        for collection in ['act', 'legislativeinstrument']:
            api_data = fetch_collection_metadata(collection)
            all_api_data.extend(api_data)

        logger.info(f"Total API records fetched: {len(all_api_data)}")

        # Update metadata files
        logger.info("Updating metadata files...")
        updated = update_metadata_files(all_api_data)
        logger.info(f"Updated {updated} metadata files")

        # Regenerate combined JSON
        logger.info("Regenerating combined JSON...")
        regenerate_combined_json()

        # Mark as complete
        completion_data = {
            'completed_at': datetime.now().isoformat(),
            'records_fetched': len(all_api_data),
            'files_updated': updated,
        }
        with open(COMPLETION_MARKER, 'w') as f:
            json.dump(completion_data, f, indent=2)

        logger.info("=" * 60)
        logger.info("API metadata update COMPLETED successfully!")
        logger.info("=" * 60)
        return 0

    except Exception as e:
        logger.error(f"Update failed: {e}")
        logger.info("Will retry on next scheduled run.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
