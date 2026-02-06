#!/usr/bin/env python3
"""
Download the Open Australian Legal Corpus from Hugging Face
and filter for federal in-force legislation.
"""
import json
import logging
from datetime import datetime
from pathlib import Path

from datasets import load_dataset

import config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def download_and_filter_corpus():
    """
    Download the Open Australian Legal Corpus and filter for federal legislation.
    """
    logger.info("Downloading Open Australian Legal Corpus from Hugging Face...")
    logger.info("This may take a while for the first download (~1.4GB)...")

    # Load the dataset (split is 'corpus' not 'train')
    dataset = load_dataset("isaacus/open-australian-legal-corpus", split="corpus")

    logger.info(f"Total documents in corpus: {len(dataset):,}")

    # Examine the structure
    logger.info(f"Columns: {dataset.column_names}")

    # Filter for federal LEGISLATION only (exclude court decisions)
    # The 'source' field should be 'federal_register_of_legislation'
    # The 'type' field should be 'primary_legislation' or 'secondary_legislation'

    logger.info("Filtering for Federal Register of Legislation documents (Acts & Regulations only)...")

    # Only include these document types
    legislation_types = ['primary_legislation', 'secondary_legislation']

    federal_docs = []

    for i, doc in enumerate(dataset):
        # Check source and type
        source = doc.get('source', '')
        doc_type = doc.get('type', '')

        # Include documents from Federal Register of Legislation that are legislation
        is_federal_register = source == 'federal_register_of_legislation'
        is_legislation = doc_type in legislation_types

        if is_federal_register and is_legislation:
            # Get the text content
            text = doc.get('text', '')

            if text and len(text) > 100:  # Skip very short documents
                federal_docs.append({
                    'id': doc.get('version_id', f'doc_{i}'),
                    'title': doc.get('citation', doc.get('version_id', 'Unknown')),
                    'text': text,
                    'text_length': len(text),
                    'type': doc_type,
                    'jurisdiction': doc.get('jurisdiction', 'Unknown'),
                    'source': source,
                    'date': doc.get('date', ''),
                    'url': doc.get('url', ''),
                    'when_scraped': doc.get('when_scraped', ''),
                })

        # Progress update
        if (i + 1) % 25000 == 0:
            logger.info(f"Processed {i+1:,}/{len(dataset):,} documents, found {len(federal_docs):,} legislation docs")

    logger.info(f"Found {len(federal_docs):,} Federal Register of Legislation documents")

    # Categorize by type
    type_counts = {}
    for doc in federal_docs:
        doc_type = doc.get('type', 'Unknown')
        type_counts[doc_type] = type_counts.get(doc_type, 0) + 1

    logger.info("Document types:")
    for doc_type, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        logger.info(f"  {doc_type}: {count:,}")

    # Save to file
    output_path = config.DATA_DIR / 'federal_legislation_corpus.json'

    corpus_data = {
        'downloaded_at': datetime.now().isoformat(),
        'source': 'Open Australian Legal Corpus (Hugging Face)',
        'total_documents': len(federal_docs),
        'type_breakdown': type_counts,
        'documents': federal_docs,
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(corpus_data, f, indent=2, ensure_ascii=False)

    logger.info(f"Saved {len(federal_docs):,} documents to {output_path}")

    # Also save in the format expected by our analysis tools
    regulations_path = config.DATA_DIR / config.DATA_FILENAME

    # Map fields to expected format
    regulations = []
    for doc in federal_docs:
        # Extract department from title/type heuristically
        title = doc.get('title', '')
        department = extract_department(title)

        # Extract year from date or title
        year = extract_year(doc.get('date', ''), title)

        regulations.append({
            'id': doc['id'],
            'register_id': doc['id'],
            'title': title,
            'text': doc['text'],
            'text_length': doc['text_length'],
            'department': department,
            'year': year,
            'collection': doc.get('type', 'unknown'),
            'source': doc.get('source', ''),
            'url': doc.get('url', ''),
            'fetched_at': doc.get('when_scraped', datetime.now().isoformat()),
        })

    regs_data = {
        'scraped_at': datetime.now().isoformat(),
        'source': 'Open Australian Legal Corpus',
        'total_regulations': len(regulations),
        'regulations': regulations,
    }

    with open(regulations_path, 'w', encoding='utf-8') as f:
        json.dump(regs_data, f, indent=2, ensure_ascii=False)

    logger.info(f"Saved {len(regulations):,} regulations to {regulations_path}")

    return regulations


def extract_department(title: str) -> str:
    """Extract department from title using heuristics."""
    title_lower = title.lower()

    department_keywords = {
        'Treasury': ['tax', 'financial', 'banking', 'superannuation', 'revenue', 'treasury', 'customs', 'excise'],
        'Health': ['health', 'therapeutic', 'medical', 'pharmaceutical', 'medicare', 'aged care', 'gene technology'],
        'Education': ['education', 'school', 'university', 'tertiary', 'student', 'higher education'],
        'Defence': ['defence', 'military', 'veteran', 'armed forces', 'navy', 'army', 'air force'],
        'Home Affairs': ['migration', 'citizenship', 'border', 'immigration', 'customs', 'security', 'criminal'],
        'Agriculture': ['agriculture', 'biosecurity', 'fisheries', 'plant', 'animal', 'quarantine', 'primary industries'],
        'Environment': ['environment', 'water', 'biodiversity', 'heritage', 'climate', 'emissions', 'national parks'],
        'Industry': ['industry', 'science', 'innovation', 'research', 'technology', 'intellectual property'],
        'Infrastructure': ['transport', 'infrastructure', 'aviation', 'maritime', 'road', 'rail', 'shipping', 'airports'],
        'Attorney-General': ['criminal', 'legal', 'family law', 'court', 'judicial', 'bankruptcy', 'evidence', 'crimes'],
        'Social Services': ['social', 'disability', 'ndis', 'welfare', 'child support', 'family assistance'],
        'Employment': ['employment', 'workplace', 'fair work', 'workers', 'safety', 'compensation'],
        'Communications': ['broadcasting', 'telecommunications', 'radiocommunications', 'spectrum', 'media'],
        'Foreign Affairs': ['foreign', 'diplomatic', 'consular', 'passport', 'extradition'],
    }

    for dept, keywords in department_keywords.items():
        if any(kw in title_lower for kw in keywords):
            return dept

    return 'Other'


def extract_year(date_str: str, title: str) -> int:
    """Extract year from date string or title."""
    import re

    # Try to extract from date string
    if date_str:
        year_match = re.search(r'(\d{4})', date_str)
        if year_match:
            year = int(year_match.group(1))
            if 1900 <= year <= 2030:
                return year

    # Try to extract from title
    year_match = re.search(r'(\d{4})', title)
    if year_match:
        year = int(year_match.group(1))
        if 1900 <= year <= 2030:
            return year

    return None


if __name__ == "__main__":
    download_and_filter_corpus()
