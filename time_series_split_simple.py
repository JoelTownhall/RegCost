#!/usr/bin/env python3
"""
Time Series Analysis - Split by Primary vs Secondary Legislation.
Uses existing corpus data instead of API fetch.
"""

import json
import re
import logging
from datetime import datetime, date
from pathlib import Path
from typing import Dict, Optional

import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def extract_year(register_id: str) -> Optional[int]:
    """Extract year from register_id."""
    match = re.search(r'[CF](\d{4})', register_id)
    return int(match.group(1)) if match else None


def get_legislation_type(register_id: str, collection: str) -> str:
    """Determine if primary or secondary legislation."""
    if collection == 'act':
        return 'primary'
    return 'secondary'


def count_bc(text: str) -> int:
    """Count BC requirements."""
    if not text:
        return 0
    text_lower = text.lower()
    text_lower = re.sub(r'\bmust\s+not\b', '__NEG__', text_lower)
    text_lower = re.sub(r'\bshall\s+not\b', '__NEG__', text_lower)
    count = 0
    for word in ['must', 'shall', 'required']:
        count += len(re.findall(r'\b' + word + r'\b', text_lower))
    return count


def count_regdata(text: str) -> int:
    """Count RegData restrictions."""
    if not text:
        return 0
    text_lower = text.lower()
    count = len(re.findall(r'\bmay not\b', text_lower))
    text_lower = re.sub(r'\bmay not\b', '__X__', text_lower)
    for word in ['shall', 'must', 'required', 'prohibited']:
        count += len(re.findall(r'\b' + word + r'\b', text_lower))
    return count


def main():
    base_dir = Path(__file__).parent
    data_dir = base_dir / 'data'
    output_dir = base_dir / 'output'

    time_points = [2010, 2015, 2020, 2025]

    # Load corpus
    logger.info("Loading data...")
    with open(data_dir / 'scraped_legislation.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    documents = data.get('regulations', data)
    logger.info(f"Loaded {len(documents):,} documents")

    # Process all documents
    processed = []
    for doc in documents:
        register_id = doc.get('register_id', doc.get('id', ''))
        collection = doc.get('collection', '')
        text = doc.get('text', '')

        year = extract_year(register_id)
        if not year:
            continue

        leg_type = get_legislation_type(register_id, collection)
        bc = count_bc(text)
        regdata = count_regdata(text)

        processed.append({
            'year': year,
            'type': leg_type,
            'bc': bc,
            'regdata': regdata,
        })

    logger.info(f"Processed {len(processed):,} documents")

    # Aggregate by time period
    results = {}
    for cutoff_year in time_points:
        # Include docs where making year <= cutoff year
        in_force = [d for d in processed if d['year'] <= cutoff_year]

        stats = {
            'primary': {'count': 0, 'bc': 0, 'regdata': 0},
            'secondary': {'count': 0, 'bc': 0, 'regdata': 0},
        }

        for d in in_force:
            lt = d['type']
            stats[lt]['count'] += 1
            stats[lt]['bc'] += d['bc']
            stats[lt]['regdata'] += d['regdata']

        results[cutoff_year] = stats

    # Print summary
    print("\n" + "=" * 90)
    print("TIME SERIES - PRIMARY VS SECONDARY LEGISLATION")
    print("=" * 90)
    print(f"{'Year':<8} {'Pri Docs':>10} {'Sec Docs':>10} {'Pri BC':>12} {'Sec BC':>12} {'Pri RegData':>12} {'Sec RegData':>12}")
    print("-" * 90)

    for year in time_points:
        s = results[year]
        print(f"{year:<8} {s['primary']['count']:>10,} {s['secondary']['count']:>10,} "
              f"{s['primary']['bc']:>12,} {s['secondary']['bc']:>12,} "
              f"{s['primary']['regdata']:>12,} {s['secondary']['regdata']:>12,}")

    # Create requirements chart
    create_requirements_chart(results, time_points, output_dir / 'requirements_by_legislation_type.png')

    # Create document count chart
    create_count_chart(results, time_points, output_dir / 'document_count_by_legislation_type.png')

    # Save JSON
    with open(output_dir / 'time_series_split_analysis.json', 'w') as f:
        json.dump({
            'generated_at': datetime.now().isoformat(),
            'results': {str(k): v for k, v in results.items()}
        }, f, indent=2)

    logger.info("Analysis complete!")


def create_requirements_chart(results: Dict, years: list, output_path: Path):
    """Create stacked bar chart of requirements."""
    x = range(len(years))
    width = 0.35

    primary_bc = [results[y]['primary']['bc'] for y in years]
    secondary_bc = [results[y]['secondary']['bc'] for y in years]
    primary_reg = [results[y]['primary']['regdata'] for y in years]
    secondary_reg = [results[y]['secondary']['regdata'] for y in years]

    fig, ax = plt.subplots(figsize=(12, 8))

    # BC bars (left)
    ax.bar([i - width/2 for i in x], primary_bc, width, label='BC - Primary (Acts)', color='#1a5276')
    ax.bar([i - width/2 for i in x], secondary_bc, width, bottom=primary_bc,
           label='BC - Secondary (Instruments)', color='#5dade2')

    # RegData bars (right)
    ax.bar([i + width/2 for i in x], primary_reg, width, label='RegData - Primary (Acts)', color='#7b241c')
    ax.bar([i + width/2 for i in x], secondary_reg, width, bottom=primary_reg,
           label='RegData - Secondary (Instruments)', color='#f1948a')

    ax.set_xlabel('Year (as of July 1)', fontsize=12)
    ax.set_ylabel('Regulatory Requirements', fontsize=12)
    ax.set_title('Australian Federal Regulatory Requirements\nPrimary vs Secondary Legislation',
                fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(years)
    ax.legend(loc='upper left')

    # Add totals
    for i, y in enumerate(years):
        bc_total = results[y]['primary']['bc'] + results[y]['secondary']['bc']
        reg_total = results[y]['primary']['regdata'] + results[y]['secondary']['regdata']
        ax.text(i - width/2, bc_total + 3000, f'{bc_total:,}', ha='center', fontsize=9)
        ax.text(i + width/2, reg_total + 3000, f'{reg_total:,}', ha='center', fontsize=9)

    plt.tight_layout()
    plt.savefig(str(output_path), dpi=150, bbox_inches='tight')
    plt.close()
    logger.info(f"Requirements chart saved to {output_path}")


def create_count_chart(results: Dict, years: list, output_path: Path):
    """Create stacked bar chart of document counts."""
    x = range(len(years))
    width = 0.6

    primary = [results[y]['primary']['count'] for y in years]
    secondary = [results[y]['secondary']['count'] for y in years]

    fig, ax = plt.subplots(figsize=(10, 7))

    ax.bar(x, primary, width, label='Primary Legislation (Acts)', color='#2E86AB')
    ax.bar(x, secondary, width, bottom=primary, label='Secondary Legislation (Instruments)', color='#A23B72')

    ax.set_xlabel('Year (as of July 1)', fontsize=12)
    ax.set_ylabel('Number of Documents in Force', fontsize=12)
    ax.set_title('Growth of Australian Federal Legislation\nPrimary vs Secondary',
                fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(years)
    ax.legend(loc='upper left')

    # Add labels
    for i, y in enumerate(years):
        pri = results[y]['primary']['count']
        sec = results[y]['secondary']['count']
        total = pri + sec

        ax.text(i, pri/2, f'{pri:,}', ha='center', va='center', fontsize=10, color='white', fontweight='bold')
        ax.text(i, pri + sec/2, f'{sec:,}', ha='center', va='center', fontsize=10, color='white', fontweight='bold')
        ax.text(i, total + 300, f'{total:,}', ha='center', fontsize=10, fontweight='bold')

    plt.tight_layout()
    plt.savefig(str(output_path), dpi=150, bbox_inches='tight')
    plt.close()
    logger.info(f"Document count chart saved to {output_path}")


if __name__ == "__main__":
    main()
