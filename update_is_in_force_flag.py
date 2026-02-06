#!/usr/bin/env python3
"""
Update all metadata files to add is_in_force=True.

Since our corpus was scraped using the filter `isInForce eq true`,
all documents ARE currently in-force. This script adds that field
explicitly to the metadata for analysis.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

import config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)


def update_metadata_files(metadata_dir: Path):
    """
    Add is_in_force=True to all metadata files.
    """
    meta_files = list(metadata_dir.glob('*.json'))
    logger.info(f"Updating {len(meta_files)} metadata files...")

    updated = 0
    for meta_file in meta_files:
        try:
            with open(meta_file, 'r', encoding='utf-8') as f:
                meta = json.load(f)

            # Add is_in_force flag
            meta['is_in_force'] = True
            meta['in_force_as_of'] = '2026-01-23'  # Scrape date

            with open(meta_file, 'w', encoding='utf-8') as f:
                json.dump(meta, f, indent=2, ensure_ascii=False)

            updated += 1

        except Exception as e:
            logger.error(f"Error updating {meta_file}: {e}")

    logger.info(f"Updated {updated} files")
    return updated


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
        'note': 'All documents queried with isInForce=true, so all are currently in-force',
        'in_force_as_of': '2026-01-23',
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

    # Update metadata files
    update_metadata_files(metadata_dir)

    # Regenerate combined JSON
    logger.info("\nRegenerating combined JSON...")
    regenerate_combined_json(metadata_dir, text_dir, output_path)

    print("\nDone! All documents marked as is_in_force=True")


if __name__ == "__main__":
    main()
