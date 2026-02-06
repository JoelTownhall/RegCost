#!/usr/bin/env python3
"""
Time Series Analysis of Australian Federal Regulatory Requirements.

Properly accounts for:
1. Commencement dates (when legislation comes into force)
2. Repeal dates (when legislation is no longer in force)
3. Word count changes from amendments (using current text as proxy)

Methodologies:
- BC Method: Count binding words (must, shall, required)
- RegData/Mercatus Method: Count restriction words (shall, must, may not, required, prohibited)
"""

import json
import re
import requests
import logging
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# API endpoint
API_URL = "https://api.prod.legislation.gov.au/v1"

# BC Methodology keywords
BC_BINDING_WORDS = ['must', 'shall', 'required']
BC_EXCLUSION_PATTERNS = [
    re.compile(r'\bmust\s+not\b', re.IGNORECASE),
    re.compile(r'\bshall\s+not\b', re.IGNORECASE),
]

# RegData/Mercatus keywords
REGDATA_RESTRICTION_WORDS = ['shall', 'must', 'may not', 'required', 'prohibited']


def fetch_all_titles() -> List[Dict]:
    """
    Fetch all titles from the API with status history for proper date tracking.
    Uses statusHistory to extract commencement and repeal dates.
    """
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
                # Only include principal legislation (not amending Acts)
                if not item.get('isPrincipal', False):
                    continue

                # Parse statusHistory for commencement and repeal dates
                status_history = item.get('statusHistory', [])
                commencement_date = None
                repeal_date = None

                for status in status_history:
                    if status.get('status') == 'InForce':
                        commencement_date = status.get('start')
                    elif status.get('status') == 'Repealed':
                        repeal_date = status.get('start')

                # Fall back to makingDate if no commencement found
                if not commencement_date:
                    commencement_date = item.get('makingDate')

                all_items.append({
                    'register_id': item['id'],
                    'title': item['name'],
                    'collection': item.get('collection', '').lower(),
                    'making_date': item.get('makingDate'),
                    'commencement_date': commencement_date,
                    'repeal_date': repeal_date,
                    'is_in_force': item.get('isInForce', False),
                    'year': item.get('year'),
                })

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
        # Handle various date formats
        if 'T' in date_str:
            return datetime.fromisoformat(date_str.replace('Z', '+00:00')).date()
        return datetime.strptime(date_str[:10], '%Y-%m-%d').date()
    except:
        return None


def is_in_force_at(doc: Dict, check_date: date) -> bool:
    """
    Determine if a document was in force at a specific date.

    A document is in force if:
    - Its commencement_date is on or before check_date
    - Its repeal_date is None OR after check_date
    """
    commencement = parse_date(doc.get('commencement_date'))
    repeal = parse_date(doc.get('repeal_date'))

    # If no commencement date, fall back to making_date
    if not commencement:
        making = parse_date(doc.get('making_date'))
        if making:
            commencement = making
        else:
            # Try to use year field from API
            year = doc.get('year')
            if year:
                commencement = date(year, 1, 1)
            else:
                # Try to extract year from register_id
                match = re.search(r'[CF](\d{4})', doc.get('register_id', ''))
                if match:
                    year = int(match.group(1))
                    commencement = date(year, 1, 1)
                else:
                    return False  # Can't determine, exclude

    # Check if commenced by check_date
    if commencement > check_date:
        return False

    # Check if not repealed by check_date
    if repeal and repeal <= check_date:
        return False

    return True


def count_bc_requirements(text: str) -> int:
    """
    Count BC methodology binding requirements.
    Counts 'must', 'shall', 'required' excluding negations.
    """
    if not text:
        return 0

    text_lower = text.lower()

    # First, mask out negation patterns
    masked_text = text_lower
    for pattern in BC_EXCLUSION_PATTERNS:
        masked_text = pattern.sub('__EXCLUDED__', masked_text)

    count = 0
    for word in BC_BINDING_WORDS:
        pattern = re.compile(r'\b' + re.escape(word) + r'\b', re.IGNORECASE)
        count += len(pattern.findall(masked_text))

    return count


def count_regdata_restrictions(text: str) -> int:
    """
    Count RegData/Mercatus methodology restrictions.
    Counts 'shall', 'must', 'may not', 'required', 'prohibited'.
    """
    if not text:
        return 0

    text_lower = text.lower()
    count = 0

    # Count multi-word patterns first
    multi_word = ['may not']
    for phrase in multi_word:
        pattern = re.compile(r'\b' + re.escape(phrase) + r'\b', re.IGNORECASE)
        matches = len(pattern.findall(text_lower))
        count += matches
        # Mask to avoid double counting
        text_lower = pattern.sub('__COUNTED__', text_lower)

    # Count single words
    single_words = ['shall', 'must', 'required', 'prohibited']
    for word in single_words:
        pattern = re.compile(r'\b' + re.escape(word) + r'\b', re.IGNORECASE)
        count += len(pattern.findall(text_lower))

    return count


def load_text_corpus(data_dir: Path) -> Dict[str, str]:
    """Load all text files into a dictionary keyed by register_id."""
    text_dir = data_dir / 'legislation_text'
    corpus = {}

    logger.info(f"Loading text corpus from {text_dir}...")

    for text_file in text_dir.glob('*.txt'):
        register_id = text_file.stem
        try:
            with open(text_file, 'r', encoding='utf-8') as f:
                corpus[register_id] = f.read()
        except Exception as e:
            logger.error(f"Error loading {text_file}: {e}")

    logger.info(f"Loaded {len(corpus)} text files")
    return corpus


def run_time_series_analysis(
    titles: List[Dict],
    corpus: Dict[str, str],
    time_points: List[date]
) -> Dict:
    """
    Run BC and RegData analysis for each time point.

    Returns dict with results for each time point.
    """
    results = {}

    for check_date in time_points:
        logger.info(f"Analyzing {check_date}...")

        # Filter documents in force at this date
        in_force = [doc for doc in titles if is_in_force_at(doc, check_date)]

        # Count requirements
        bc_total = 0
        regdata_total = 0
        docs_with_text = 0
        docs_without_text = 0

        for doc in in_force:
            register_id = doc['register_id']
            text = corpus.get(register_id, '')

            if text:
                docs_with_text += 1
                bc_total += count_bc_requirements(text)
                regdata_total += count_regdata_restrictions(text)
            else:
                docs_without_text += 1

        results[str(check_date)] = {
            'date': str(check_date),
            'documents_in_force': len(in_force),
            'documents_with_text': docs_with_text,
            'documents_without_text': docs_without_text,
            'bc_requirements': bc_total,
            'regdata_restrictions': regdata_total,
        }

        logger.info(f"  {check_date}: {len(in_force)} docs in force, "
                   f"BC={bc_total:,}, RegData={regdata_total:,}")

    return results


def create_time_series_chart(results: Dict, output_path: str):
    """Create bar chart showing requirements over time."""
    dates = sorted(results.keys())

    if not dates or all(results[d]['documents_in_force'] == 0 for d in dates):
        logger.warning("No data to chart")
        return

    bc_values = [results[d]['bc_requirements'] for d in dates]
    regdata_values = [results[d]['regdata_restrictions'] for d in dates]
    doc_counts = [results[d]['documents_in_force'] for d in dates]

    # Create labels (just year)
    labels = [d[:4] for d in dates]

    x = list(range(len(dates)))
    width = 0.35

    fig, ax1 = plt.subplots(figsize=(12, 8))

    # Bar chart for requirements
    bars1 = ax1.bar([i - width/2 for i in x], bc_values, width,
                    label='BC Requirements', color='#2E86AB')
    bars2 = ax1.bar([i + width/2 for i in x], regdata_values, width,
                    label='RegData Restrictions', color='#A23B72')

    ax1.set_xlabel('Year (as of July 1)', fontsize=12)
    ax1.set_ylabel('Count of Regulatory Requirements', fontsize=12)
    ax1.set_title('Australian Federal Regulatory Requirements Over Time\n'
                  '(Accounting for Commencement and Repeal Dates)',
                  fontsize=14, fontweight='bold')
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels)
    ax1.legend(loc='upper left')

    # Add value labels on bars
    for bar, val in zip(bars1, bc_values):
        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1000,
                f'{val:,}', ha='center', va='bottom', fontsize=9)
    for bar, val in zip(bars2, regdata_values):
        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1000,
                f'{val:,}', ha='center', va='bottom', fontsize=9)

    # Secondary axis for document count
    ax2 = ax1.twinx()
    ax2.plot(x, doc_counts, 'g--o', label='Documents in Force', linewidth=2)
    ax2.set_ylabel('Documents in Force', color='green', fontsize=12)
    ax2.tick_params(axis='y', labelcolor='green')
    ax2.legend(loc='upper right')

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

    logger.info(f"Chart saved to {output_path}")


def main():
    base_dir = Path(__file__).parent
    data_dir = base_dir / 'data'
    output_dir = base_dir / 'output'
    output_dir.mkdir(exist_ok=True)

    # Time points to analyze (July 1 of each year)
    time_points = [
        date(2010, 7, 1),
        date(2015, 7, 1),
        date(2020, 7, 1),
        date(2025, 7, 1),
    ]

    # Fetch all titles with dates from API
    all_titles = fetch_all_titles()
    logger.info(f"Total titles from API: {len(all_titles)}")

    # Load text corpus
    corpus = load_text_corpus(data_dir)

    # Run analysis
    results = run_time_series_analysis(all_titles, corpus, time_points)

    # Print results
    print("\n" + "=" * 80)
    print("TIME SERIES ANALYSIS - BC AND REGDATA METHODOLOGIES")
    print("(Using Commencement/Repeal Dates for Accurate In-Force Counts)")
    print("=" * 80)

    for date_str in sorted(results.keys()):
        r = results[date_str]
        print(f"\n{date_str[:4]} (as of July 1):")
        print(f"  Documents in force: {r['documents_in_force']:,}")
        print(f"  Documents with text: {r['documents_with_text']:,}")
        print(f"  BC requirements: {r['bc_requirements']:,}")
        print(f"  RegData restrictions: {r['regdata_restrictions']:,}")

    # Save results
    output_json = output_dir / 'time_series_analysis.json'
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump({
            'generated_at': datetime.now().isoformat(),
            'methodology': 'BC and RegData with proper in-force filtering',
            'total_titles': len(all_titles),
            'corpus_size': len(corpus),
            'results': results
        }, f, indent=2)
    logger.info(f"Results saved to {output_json}")

    # Create chart
    chart_path = output_dir / 'time_series_proper_dates.png'
    create_time_series_chart(results, str(chart_path))

    return results


if __name__ == "__main__":
    main()
