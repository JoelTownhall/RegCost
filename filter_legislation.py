#!/usr/bin/env python3
"""
Filter the downloaded corpus to include only legislation (not court decisions).
Then run the regulatory burden analysis.
"""
import json
import logging
from datetime import datetime
from pathlib import Path

import config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def filter_legislation_only():
    """
    Filter the downloaded corpus to include only legislation documents.
    Exclude court decisions.
    """
    input_path = config.DATA_DIR / 'regulations_data.json'

    logger.info(f"Loading data from {input_path}...")

    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    all_docs = data.get('regulations', [])
    logger.info(f"Total documents: {len(all_docs):,}")

    # Filter for legislation only (exclude court decisions)
    legislation_types = ['primary_legislation', 'secondary_legislation']

    legislation_docs = []
    type_counts = {}

    for doc in all_docs:
        doc_type = doc.get('collection', '').lower()
        type_counts[doc_type] = type_counts.get(doc_type, 0) + 1

        if doc_type in legislation_types:
            legislation_docs.append(doc)

    logger.info("Document type breakdown:")
    for doc_type, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        included = "INCLUDED" if doc_type in legislation_types else "excluded"
        logger.info(f"  {doc_type}: {count:,} ({included})")

    logger.info(f"\nFiltered to {len(legislation_docs):,} legislation documents")

    # Separate into Acts and Regulations
    acts = [d for d in legislation_docs if d.get('collection') == 'primary_legislation']
    regulations = [d for d in legislation_docs if d.get('collection') == 'secondary_legislation']

    logger.info(f"  Primary legislation (Acts): {len(acts):,}")
    logger.info(f"  Secondary legislation (Regulations/Instruments): {len(regulations):,}")

    # Save filtered data
    output_path = config.DATA_DIR / 'legislation_only.json'

    filtered_data = {
        'filtered_at': datetime.now().isoformat(),
        'source': 'Open Australian Legal Corpus (filtered)',
        'total_legislation': len(legislation_docs),
        'acts_count': len(acts),
        'regulations_count': len(regulations),
        'regulations': legislation_docs,
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(filtered_data, f, indent=2, ensure_ascii=False)

    logger.info(f"Saved filtered data to {output_path}")

    return legislation_docs


if __name__ == "__main__":
    filter_legislation_only()
