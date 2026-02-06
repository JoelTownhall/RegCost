#!/usr/bin/env python3
"""
Analyze the types of instruments in our corpus to understand the gap with Mandala.
"""

import json
import re
from pathlib import Path
from collections import defaultdict

def is_civil_aviation_exclusive(doc):
    """Check if a document has the exclusive subject matter of civil aviation."""
    title = doc.get('title', '').lower()

    if 'AD/' in doc.get('title', '') or title.startswith('ad/'):
        return True
    if 'CAO ' in doc.get('title', '') or title.startswith('cao '):
        return True
    if 'casa ' in title or 'civil aviation safety' in title:
        return True
    if 'civil aviation' in title and ('regulation' in title or 'determination' in title or 'direction' in title):
        return True
    if 'aviation transport security' in title:
        return True
    if 'airspace' in title and ('regulation' in title or 'determination' in title):
        return True
    if 'aircraft noise' in title:
        return True
    if 'air navigation' in title and ('regulation' in title or 'order' in title):
        return True

    return False


def categorize_instrument(title):
    """Categorize an instrument by its type based on title patterns."""
    title_lower = title.lower()

    # Regulations
    if ' regulation' in title_lower or title_lower.endswith(' regulations'):
        return 'Regulations'

    # Orders
    if ' order' in title_lower:
        return 'Orders'

    # Determinations
    if ' determination' in title_lower:
        return 'Determinations'

    # Declarations
    if ' declaration' in title_lower:
        return 'Declarations'

    # Directions
    if ' direction' in title_lower:
        return 'Directions'

    # Rules
    if ' rules' in title_lower:
        return 'Rules'

    # Notices
    if ' notice' in title_lower:
        return 'Notices'

    # Instruments (generic)
    if ' instrument' in title_lower:
        return 'Instruments (generic)'

    # Standards
    if ' standard' in title_lower or 'accounting standard' in title_lower:
        return 'Standards'

    # Proclamations
    if 'proclamation' in title_lower:
        return 'Proclamations'

    # Lists/Schedules
    if ' list' in title_lower or ' schedule' in title_lower:
        return 'Lists/Schedules'

    # Exemptions
    if 'exemption' in title_lower:
        return 'Exemptions'

    # Approvals
    if 'approval' in title_lower:
        return 'Approvals'

    return 'Other'


def main():
    base_dir = Path(__file__).parent
    data_dir = base_dir / 'data'

    print("Loading data...")
    with open(data_dir / 'scraped_legislation.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    documents = data.get('regulations', data)

    # Filter to non-aviation instruments only
    non_aviation = [d for d in documents if not is_civil_aviation_exclusive(d)]
    instruments = [d for d in non_aviation if d.get('collection', '').lower() != 'act']

    print(f"Total non-aviation instruments: {len(instruments):,}")

    # Categorize by type
    by_type = defaultdict(list)
    for doc in instruments:
        title = doc.get('title', '')
        cat = categorize_instrument(title)
        by_type[cat].append(doc)

    print("\n" + "=" * 80)
    print("NON-AVIATION INSTRUMENTS BY TYPE")
    print("=" * 80)
    for cat, docs in sorted(by_type.items(), key=lambda x: -len(x[1])):
        print(f"\n{cat}: {len(docs):,}")
        for d in docs[:5]:
            title = d.get('title', '')[:75]
            print(f"  - {title}")

    # Check for potentially excluded categories
    print("\n" + "=" * 80)
    print("POTENTIALLY EXCLUDED INSTRUMENT TYPES")
    print("=" * 80)
    print("""
The ALRC DataHub may exclude certain instrument types that we're including:

1. Exemptions and Approvals - often administrative/operational
2. Notices - often temporary or administrative
3. Lists/Schedules - often supporting documents
4. Standards (Accounting, etc.) - may be categorized differently
""")

    # Calculate what happens if we exclude certain categories
    excluded_cats = ['Exemptions', 'Approvals', 'Notices', 'Lists/Schedules']
    excluded_count = sum(len(by_type[c]) for c in excluded_cats)

    print(f"\nIf we excluded these categories:")
    for cat in excluded_cats:
        print(f"  {cat}: {len(by_type[cat]):,}")
    print(f"  Total excluded: {excluded_count:,}")

    remaining = len(instruments) - excluded_count
    remaining_with_acts = remaining + sum(1 for d in non_aviation if d.get('collection', '').lower() == 'act')

    print(f"\nRemaining instruments: {remaining:,}")
    print(f"Remaining total (with acts): {remaining_with_acts:,}")
    print(f"Mandala total: ~9,600")
    print(f"Gap after exclusions: {remaining_with_acts - 9600:,}")

    # Check the "Other" category
    print("\n" + "=" * 80)
    print("BREAKDOWN OF 'OTHER' CATEGORY")
    print("=" * 80)

    other_patterns = defaultdict(int)
    for doc in by_type['Other']:
        title = doc.get('title', '')
        # Get first few words
        words = title.split()[:3]
        pattern = ' '.join(words) if len(words) >= 3 else title[:30]
        other_patterns[pattern] += 1

    print("\nMost common patterns in 'Other':")
    for pattern, count in sorted(other_patterns.items(), key=lambda x: -x[1])[:30]:
        print(f"  {count:>5}: {pattern}")

if __name__ == "__main__":
    main()
