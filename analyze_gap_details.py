#!/usr/bin/env python3
"""
Detailed analysis of the gap between our corpus and Mandala numbers.
Focus on identifying what categories of instruments might explain the difference.
"""

import json
import re
from pathlib import Path
from collections import defaultdict

import config


def is_civil_aviation_exclusive(doc):
    """Check if a document has the exclusive subject matter of civil aviation."""
    title = doc.get('title', '')
    title_lower = title.lower()

    if 'AD/' in title or title.startswith('ad/'):
        return True
    if 'CAO ' in title or title.startswith('cao '):
        return True
    if 'casa ' in title_lower or 'civil aviation safety' in title_lower:
        return True
    if 'civil aviation' in title_lower:
        return True
    if 'aviation transport security' in title_lower:
        return True
    if 'airspace' in title_lower:
        return True
    if 'aircraft noise' in title_lower:
        return True
    if 'air navigation' in title_lower:
        return True
    if 'airworthiness' in title_lower:
        return True
    if 'manual of standards part' in title_lower:
        return True

    return False


def categorize_by_title(title):
    """Categorize an instrument by title patterns."""
    title_lower = title.lower()

    # Specific document types that might be excluded
    if 'statement of principles' in title_lower:
        return 'Statement of Principles (RMA)'
    if 'licence area plan' in title_lower:
        return 'Licence Area Plan'
    if 'superannuation' in title_lower and 'family law' in title_lower:
        return 'Superannuation Family Law'
    if 'native title' in title_lower:
        return 'Native Title'
    if 'tariff concession' in title_lower:
        return 'Tariff Concession'
    if 'export control' in title_lower:
        return 'Export Control'
    if 'biosecurity' in title_lower:
        return 'Biosecurity'
    if 'tax file number' in title_lower or 'tfn' in title_lower:
        return 'Tax File Number'
    if 'therapeutic goods' in title_lower:
        return 'Therapeutic Goods'
    if 'industrial chemicals' in title_lower:
        return 'Industrial Chemicals'
    if 'gene technology' in title_lower:
        return 'Gene Technology'
    if 'veterans' in title_lower or 'military rehabilitation' in title_lower:
        return 'Veterans Affairs'
    if 'customs' in title_lower and ('by-law' in title_lower or 'tariff' in title_lower):
        return 'Customs By-Law/Tariff'

    # Generic instrument types
    if 'determination' in title_lower:
        return 'Determination'
    if 'regulation' in title_lower:
        return 'Regulation'
    if 'order' in title_lower:
        return 'Order'
    if 'rules' in title_lower:
        return 'Rules'
    if 'direction' in title_lower:
        return 'Direction'
    if 'notice' in title_lower:
        return 'Notice'
    if 'declaration' in title_lower:
        return 'Declaration'
    if 'standard' in title_lower:
        return 'Standard'
    if 'exemption' in title_lower:
        return 'Exemption'
    if 'approval' in title_lower:
        return 'Approval'
    if 'instrument' in title_lower:
        return 'Instrument (generic)'

    return 'Other'


def get_making_year(register_id):
    """Extract making year from register_id."""
    match = re.search(r'[CF](\d{4})', register_id)
    return int(match.group(1)) if match else None


def main():
    data_dir = config.DATA_DIR

    # Load data
    print("Loading data...")
    with open(data_dir / 'scraped_legislation.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    documents = data.get('regulations', data)

    # Filter to non-aviation instruments only
    instruments = []
    for doc in documents:
        if doc.get('collection', '').lower() == 'act':
            continue
        if is_civil_aviation_exclusive(doc):
            continue
        instruments.append(doc)

    print(f"\nNon-aviation instruments: {len(instruments):,}")
    mandala_instruments = 8400
    gap = len(instruments) - mandala_instruments
    print(f"Mandala instruments: ~{mandala_instruments:,}")
    print(f"Gap to explain: {gap:,}")

    # Categorize all instruments
    by_category = defaultdict(list)
    for doc in instruments:
        cat = categorize_by_title(doc.get('title', ''))
        by_category[cat].append(doc)

    # Print breakdown
    print("\n" + "=" * 80)
    print("INSTRUMENTS BY CATEGORY")
    print("=" * 80)

    categories = sorted(by_category.items(), key=lambda x: -len(x[1]))
    for cat, docs in categories:
        print(f"\n{cat}: {len(docs):,}")

        # Show samples
        for d in docs[:3]:
            title = d.get('title', '')[:70]
            year = get_making_year(d.get('register_id', '')) or '?'
            print(f"  - [{year}] {title}")

    # Categories likely to be excluded by ALRC
    print("\n" + "=" * 80)
    print("CATEGORIES POTENTIALLY EXCLUDED BY ALRC")
    print("=" * 80)

    likely_excluded = [
        'Statement of Principles (RMA)',
        'Licence Area Plan',
        'Superannuation Family Law',
        'Native Title',
        'Tariff Concession',
        'Therapeutic Goods',
        'Export Control',
        'Customs By-Law/Tariff',
    ]

    exclusion_total = 0
    print(f"\n{'Category':<40} {'Count':>8}")
    print("-" * 50)
    for cat in likely_excluded:
        count = len(by_category.get(cat, []))
        exclusion_total += count
        print(f"{cat:<40} {count:>8,}")

    print(f"\n{'Total likely exclusions':<40} {exclusion_total:>8,}")
    print(f"{'Remaining gap':<40} {gap - exclusion_total:>8,}")

    # Check what percentage of each category is from recent years
    print("\n" + "=" * 80)
    print("TEMPORAL ANALYSIS - POST-2020 GROWTH")
    print("=" * 80)

    print(f"\n{'Category':<40} {'Pre-2020':>10} {'2020+':>10} {'% Recent':>10}")
    print("-" * 72)

    for cat, docs in sorted(categories, key=lambda x: -len(x[1]))[:15]:
        pre_2020 = sum(1 for d in docs if (get_making_year(d.get('register_id', '')) or 9999) < 2020)
        post_2020 = len(docs) - pre_2020
        pct = (post_2020 / len(docs) * 100) if docs else 0
        print(f"{cat:<40} {pre_2020:>10,} {post_2020:>10,} {pct:>9.1f}%")

    # Check for amending vs principal legislation
    print("\n" + "=" * 80)
    print("CHECK FOR AMENDING LEGISLATION")
    print("=" * 80)

    amending_keywords = ['amendment', 'amending', 'repeal', 'repealing', 'transitional']
    amending_count = 0
    for doc in instruments:
        title_lower = doc.get('title', '').lower()
        if any(kw in title_lower for kw in amending_keywords):
            amending_count += 1

    print(f"\nInstruments with 'amendment/amending/repeal' in title: {amending_count:,}")
    print("(These should have been filtered by isPrincipal=true in our query)")

    # Year-by-year breakdown for recent years
    print("\n" + "=" * 80)
    print("YEAR-BY-YEAR INSTRUMENT COUNT (Recent Years)")
    print("=" * 80)

    by_year = defaultdict(int)
    for doc in instruments:
        year = get_making_year(doc.get('register_id', ''))
        if year:
            by_year[year] += 1

    print(f"\n{'Year':<8} {'Count':>8} {'Cumulative':>12}")
    print("-" * 30)

    cumulative = 0
    for year in sorted(by_year.keys()):
        cumulative += by_year[year]
        if year >= 2018:
            print(f"{year:<8} {by_year[year]:>8,} {cumulative:>12,}")

    print(f"\nNote: Mandala 2024 instruments: ~{mandala_instruments:,}")

    # Final summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    print(f"""
Total non-aviation instruments in our corpus: {len(instruments):,}
Mandala 2024 instruments: ~{mandala_instruments:,}
Gap: {gap:,}

Possible explanations for gap:

1. CATEGORY EXCLUSIONS (ALRC may not count):
   - Statement of Principles: {len(by_category.get('Statement of Principles (RMA)', [])):,}
   - Licence Area Plans: {len(by_category.get('Licence Area Plan', [])):,}
   - Native Title: {len(by_category.get('Native Title', [])):,}
   - Tariff Concession: {len(by_category.get('Tariff Concession', [])):,}
   - Therapeutic Goods: {len(by_category.get('Therapeutic Goods', [])):,}
   - Other likely exclusions: ~{exclusion_total - len(by_category.get('Statement of Principles (RMA)', [])) - len(by_category.get('Licence Area Plan', [])):,}
   Subtotal: {exclusion_total:,}

2. POST-2024 ADDITIONS:
   - 2025 instruments: {by_year.get(2025, 0):,}
   - 2026 instruments: {by_year.get(2026, 0):,}
   Subtotal: {by_year.get(2025, 0) + by_year.get(2026, 0):,}

3. CUMULATIVE COUNT AT 2024: {cumulative - by_year.get(2025, 0) - by_year.get(2026, 0):,}
   vs Mandala: ~{mandala_instruments:,}
   Remaining gap: {cumulative - by_year.get(2025, 0) - by_year.get(2026, 0) - mandala_instruments:,}

4. UNEXPLAINED PORTION:
   This remaining gap of ~{cumulative - by_year.get(2025, 0) - by_year.get(2026, 0) - mandala_instruments - exclusion_total:,}
   instruments may be due to:
   - Different "principal" legislation definitions
   - ALRC DataHub tracking repeals we don't capture
   - Other category exclusions not identified
""")


if __name__ == "__main__":
    main()
