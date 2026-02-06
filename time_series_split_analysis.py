#!/usr/bin/env python3
"""
Time Series Analysis - Split by Primary vs Secondary Legislation.

Primary Legislation = Acts
Secondary Legislation = Legislative Instruments
"""

import json
import re
import requests
import logging
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Optional
from collections import defaultdict

import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

API_URL = "https://api.prod.legislation.gov.au/v1"


def fetch_all_titles() -> List[Dict]:
    """Fetch all principal titles from the API with status history."""
    all_items = []
    page_size = 100
    skip = 0

    logger.info("Fetching all titles from API...")

    while True:
        url = f"{API_URL}/Titles?$top={page_size}&$skip={skip}&$count=true"

        try:
            response = requests.get(url, timeout=60)
            response.raise_for_status()
            data = response.json()

            items = data.get('value', [])
            if not items:
                break

            total_count = data.get('@odata.count', '?')

            for item in items:
                if not item.get('isPrincipal', False):
                    continue

                # Parse statusHistory for dates
                status_history = item.get('statusHistory', [])
                commencement_date = None
                repeal_date = None

                for status in status_history:
                    if status.get('status') == 'InForce':
                        commencement_date = status.get('start')
                    elif status.get('status') == 'Repealed':
                        repeal_date = status.get('start')

                if not commencement_date:
                    commencement_date = item.get('makingDate')

                collection = item.get('collection', '').lower()
                # Normalize collection names
                if collection == 'act':
                    leg_type = 'primary'
                else:
                    leg_type = 'secondary'

                all_items.append({
                    'register_id': item['id'],
                    'title': item['name'],
                    'collection': collection,
                    'legislation_type': leg_type,
                    'commencement_date': commencement_date,
                    'repeal_date': repeal_date,
                    'is_in_force': item.get('isInForce', False),
                })

            if len(all_items) % 5000 == 0:
                logger.info(f"  Fetched {len(all_items)}/{total_count} principal titles...")
            skip += page_size

            if len(items) < page_size:
                break

        except Exception as e:
            logger.error(f"API error at skip={skip}: {e}")
            import time
            time.sleep(5)
            continue

    logger.info(f"Total principal titles: {len(all_items)}")
    return all_items


def parse_date(date_str: Optional[str]) -> Optional[date]:
    """Parse ISO date string to date object."""
    if not date_str:
        return None
    try:
        if 'T' in date_str:
            return datetime.fromisoformat(date_str.replace('Z', '+00:00')).date()
        return datetime.strptime(date_str[:10], '%Y-%m-%d').date()
    except:
        return None


def is_in_force_at(doc: Dict, check_date: date) -> bool:
    """Check if document was in force at a specific date."""
    commencement = parse_date(doc.get('commencement_date'))
    repeal = parse_date(doc.get('repeal_date'))

    if not commencement:
        match = re.search(r'[CF](\d{4})', doc.get('register_id', ''))
        if match:
            year = int(match.group(1))
            commencement = date(year, 1, 1)
        else:
            return False

    if commencement > check_date:
        return False

    if repeal and repeal <= check_date:
        return False

    return True


def count_bc_requirements(text: str) -> int:
    """Count BC methodology binding requirements."""
    if not text:
        return 0

    text_lower = text.lower()
    # Mask negations
    text_lower = re.sub(r'\bmust\s+not\b', '__NEG__', text_lower)
    text_lower = re.sub(r'\bshall\s+not\b', '__NEG__', text_lower)

    count = 0
    for word in ['must', 'shall', 'required']:
        count += len(re.findall(r'\b' + word + r'\b', text_lower))
    return count


def count_regdata_restrictions(text: str) -> int:
    """Count RegData methodology restrictions."""
    if not text:
        return 0

    text_lower = text.lower()
    count = 0

    # Multi-word first
    count += len(re.findall(r'\bmay not\b', text_lower))
    text_lower = re.sub(r'\bmay not\b', '__COUNTED__', text_lower)

    for word in ['shall', 'must', 'required', 'prohibited']:
        count += len(re.findall(r'\b' + word + r'\b', text_lower))
    return count


def load_text_corpus(data_dir: Path) -> Dict[str, str]:
    """Load all text files."""
    text_dir = data_dir / 'legislation_text'
    corpus = {}

    for text_file in text_dir.glob('*.txt'):
        register_id = text_file.stem
        try:
            with open(text_file, 'r', encoding='utf-8') as f:
                corpus[register_id] = f.read()
        except:
            pass

    logger.info(f"Loaded {len(corpus)} text files")
    return corpus


def run_analysis(titles: List[Dict], corpus: Dict[str, str], time_points: List[date]) -> Dict:
    """Run the split analysis."""
    results = {}

    for check_date in time_points:
        logger.info(f"Analyzing {check_date}...")

        # Filter to in-force documents
        in_force = [doc for doc in titles if is_in_force_at(doc, check_date)]

        # Split by legislation type
        stats = {
            'primary': {'count': 0, 'with_text': 0, 'bc': 0, 'regdata': 0},
            'secondary': {'count': 0, 'with_text': 0, 'bc': 0, 'regdata': 0},
        }

        for doc in in_force:
            leg_type = doc['legislation_type']
            stats[leg_type]['count'] += 1

            text = corpus.get(doc['register_id'], '')
            if text:
                stats[leg_type]['with_text'] += 1
                stats[leg_type]['bc'] += count_bc_requirements(text)
                stats[leg_type]['regdata'] += count_regdata_restrictions(text)

        results[str(check_date)] = {
            'date': str(check_date),
            'primary': stats['primary'],
            'secondary': stats['secondary'],
            'total_count': stats['primary']['count'] + stats['secondary']['count'],
            'total_bc': stats['primary']['bc'] + stats['secondary']['bc'],
            'total_regdata': stats['primary']['regdata'] + stats['secondary']['regdata'],
        }

        logger.info(f"  {check_date}: Primary={stats['primary']['count']}, Secondary={stats['secondary']['count']}")

    return results


def create_requirements_chart(results: Dict, output_path: str):
    """Create stacked bar chart of requirements split by legislation type."""
    dates = sorted(results.keys())
    labels = [d[:4] for d in dates]

    primary_bc = [results[d]['primary']['bc'] for d in dates]
    secondary_bc = [results[d]['secondary']['bc'] for d in dates]
    primary_regdata = [results[d]['primary']['regdata'] for d in dates]
    secondary_regdata = [results[d]['secondary']['regdata'] for d in dates]

    x = range(len(dates))
    width = 0.35

    fig, ax = plt.subplots(figsize=(12, 8))

    # BC stacked bars
    bars1 = ax.bar([i - width/2 for i in x], primary_bc, width, label='BC - Primary (Acts)', color='#1a5276')
    bars2 = ax.bar([i - width/2 for i in x], secondary_bc, width, bottom=primary_bc,
                   label='BC - Secondary (Instruments)', color='#5dade2')

    # RegData stacked bars
    bars3 = ax.bar([i + width/2 for i in x], primary_regdata, width, label='RegData - Primary (Acts)', color='#7b241c')
    bars4 = ax.bar([i + width/2 for i in x], secondary_regdata, width, bottom=primary_regdata,
                   label='RegData - Secondary (Instruments)', color='#f1948a')

    ax.set_xlabel('Year (as of July 1)', fontsize=12)
    ax.set_ylabel('Regulatory Requirements', fontsize=12)
    ax.set_title('Australian Federal Regulatory Requirements\nPrimary vs Secondary Legislation',
                fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.legend(loc='upper left')

    # Add totals on top of bars
    for i, d in enumerate(dates):
        bc_total = results[d]['total_bc']
        regdata_total = results[d]['total_regdata']
        ax.text(i - width/2, bc_total + 2000, f'{bc_total:,}', ha='center', fontsize=9)
        ax.text(i + width/2, regdata_total + 2000, f'{regdata_total:,}', ha='center', fontsize=9)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    logger.info(f"Requirements chart saved to {output_path}")


def create_document_count_chart(results: Dict, output_path: str):
    """Create stacked bar chart of document counts split by legislation type."""
    dates = sorted(results.keys())
    labels = [d[:4] for d in dates]

    primary_counts = [results[d]['primary']['count'] for d in dates]
    secondary_counts = [results[d]['secondary']['count'] for d in dates]

    x = range(len(dates))
    width = 0.6

    fig, ax = plt.subplots(figsize=(10, 7))

    bars1 = ax.bar(x, primary_counts, width, label='Primary Legislation (Acts)', color='#2E86AB')
    bars2 = ax.bar(x, secondary_counts, width, bottom=primary_counts,
                   label='Secondary Legislation (Instruments)', color='#A23B72')

    ax.set_xlabel('Year (as of July 1)', fontsize=12)
    ax.set_ylabel('Number of Documents in Force', fontsize=12)
    ax.set_title('Growth of Australian Federal Legislation\nPrimary vs Secondary',
                fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.legend(loc='upper left')

    # Add labels
    for i, d in enumerate(dates):
        total = results[d]['total_count']
        primary = results[d]['primary']['count']
        secondary = results[d]['secondary']['count']

        # Label on primary section
        ax.text(i, primary/2, f'{primary:,}', ha='center', va='center', fontsize=10, color='white', fontweight='bold')
        # Label on secondary section
        ax.text(i, primary + secondary/2, f'{secondary:,}', ha='center', va='center', fontsize=10, color='white', fontweight='bold')
        # Total on top
        ax.text(i, total + 500, f'{total:,}', ha='center', fontsize=10, fontweight='bold')

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    logger.info(f"Document count chart saved to {output_path}")


def main():
    base_dir = Path(__file__).parent
    data_dir = base_dir / 'data'
    output_dir = base_dir / 'output'
    output_dir.mkdir(exist_ok=True)

    time_points = [
        date(2010, 7, 1),
        date(2015, 7, 1),
        date(2020, 7, 1),
        date(2025, 7, 1),
    ]

    # Fetch titles from API
    titles = fetch_all_titles()

    # Load text corpus
    corpus = load_text_corpus(data_dir)

    # Run analysis
    results = run_analysis(titles, corpus, time_points)

    # Print summary
    print("\n" + "=" * 80)
    print("TIME SERIES ANALYSIS - PRIMARY VS SECONDARY LEGISLATION")
    print("=" * 80)

    for d in sorted(results.keys()):
        r = results[d]
        print(f"\n{d[:4]} (as of July 1):")
        print(f"  Primary (Acts):       {r['primary']['count']:>6,} docs, BC={r['primary']['bc']:>9,}, RegData={r['primary']['regdata']:>9,}")
        print(f"  Secondary (Instruments): {r['secondary']['count']:>6,} docs, BC={r['secondary']['bc']:>9,}, RegData={r['secondary']['regdata']:>9,}")
        print(f"  TOTAL:                {r['total_count']:>6,} docs, BC={r['total_bc']:>9,}, RegData={r['total_regdata']:>9,}")

    # Save JSON
    output_json = output_dir / 'time_series_split_analysis.json'
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump({
            'generated_at': datetime.now().isoformat(),
            'methodology': 'BC and RegData split by Primary/Secondary legislation',
            'results': results
        }, f, indent=2)
    logger.info(f"Results saved to {output_json}")

    # Create charts
    create_requirements_chart(results, str(output_dir / 'requirements_by_legislation_type.png'))
    create_document_count_chart(results, str(output_dir / 'document_count_by_legislation_type.png'))

    return results


if __name__ == "__main__":
    main()
