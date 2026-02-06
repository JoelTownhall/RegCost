#!/usr/bin/env python3
"""
Update metadata from the legislation.gov.au API.

Fetches isInForce, makingDate, commencementDate, repealDate for all documents
and updates existing metadata files without re-scraping text.
"""

import json
import logging
import time
import requests
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)


API_URL = "https://api.prod.legislation.gov.au/v1"

COLLECTION_MAP = {
    'act': 'Act',
    'legislativeinstrument': 'LegislativeInstrument',
}


def fetch_all_titles_from_api(collection: str) -> List[Dict]:
    """
    Fetch all legislation titles and metadata from the API.
    """
    api_collection = COLLECTION_MAP.get(collection)
    if not api_collection:
        logger.error(f"Unknown collection: {collection}")
        return []

    all_items = []
    page_size = 100
    skip = 0

    logger.info(f"Fetching {api_collection} metadata from API...")

    while True:
        url = (
            f"{API_URL}/Titles?"
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
                    'is_principal': item.get('isPrincipal'),
                })

            logger.info(f"  Fetched {len(all_items)}/{total_count} titles...")
            skip += page_size

            if len(items) < page_size:
                break

            time.sleep(0.5)  # Rate limiting

        except Exception as e:
            logger.error(f"API error at skip={skip}: {e}")
            time.sleep(5)
            continue

    logger.info(f"Total {api_collection} titles: {len(all_items)}")
    return all_items


def update_metadata_files(api_data: List[Dict], metadata_dir: Path) -> Dict:
    """
    Update metadata files with API data.
    """
    # Index by register_id
    api_index = {item['register_id']: item for item in api_data}

    stats = {
        'updated': 0,
        'not_found': 0,
        'no_match': 0,
    }

    meta_files = list(metadata_dir.glob('*.json'))
    logger.info(f"Updating {len(meta_files)} metadata files...")

    for meta_file in meta_files:
        register_id = meta_file.stem

        if register_id not in api_index:
            stats['no_match'] += 1
            continue

        try:
            with open(meta_file, 'r', encoding='utf-8') as f:
                meta = json.load(f)

            # Update with API data
            api_item = api_index[register_id]
            meta['is_in_force'] = api_item.get('is_in_force')
            meta['making_date'] = api_item.get('making_date')
            meta['commencement_date'] = api_item.get('commencement_date')
            meta['repeal_date'] = api_item.get('repeal_date')
            meta['is_principal'] = api_item.get('is_principal')
            meta['api_updated_at'] = datetime.now().isoformat()

            with open(meta_file, 'w', encoding='utf-8') as f:
                json.dump(meta, f, indent=2, ensure_ascii=False)

            stats['updated'] += 1

        except Exception as e:
            logger.error(f"Error updating {meta_file}: {e}")
            stats['not_found'] += 1

    return stats


def regenerate_combined_json(metadata_dir: Path, text_dir: Path, output_path: Path):
    """
    Regenerate the combined JSON from metadata and text files.
    """
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
        'total_documents': len(results),
        'regulations': results,
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    logger.info(f"Saved {len(results)} documents to {output_path}")


def main():
    data_dir = config.DATA_DIR
    metadata_dir = data_dir / 'metadata'
    text_dir = data_dir / 'legislation_text'
    output_path = data_dir / 'scraped_legislation.json'

    # Fetch metadata from API for both collections
    all_api_data = []
    for collection in ['act', 'legislativeinstrument']:
        api_data = fetch_all_titles_from_api(collection)
        all_api_data.extend(api_data)

    logger.info(f"\nTotal API records: {len(all_api_data)}")

    # Check how many have is_in_force=True
    in_force_count = sum(1 for d in all_api_data if d.get('is_in_force') is True)
    logger.info(f"Records with is_in_force=True: {in_force_count}")

    # Update metadata files
    stats = update_metadata_files(all_api_data, metadata_dir)
    logger.info(f"\nUpdate stats: {stats}")

    # Regenerate combined JSON
    logger.info("\nRegenerating combined JSON...")
    regenerate_combined_json(metadata_dir, text_dir, output_path)

    print("\nDone! Updated metadata with is_in_force field.")


if __name__ == "__main__":
    main()
