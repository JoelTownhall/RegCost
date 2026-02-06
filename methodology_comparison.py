#!/usr/bin/env python3
"""
Compare our methodology with Mandala report.
Analyze:
1. How many aviation-related instruments we have
2. How repeals are (or aren't) being tracked
3. Reconcile the counts
"""

import json
import re
from pathlib import Path
from collections import defaultdict

def main():
    base_dir = Path(__file__).parent
    data_dir = base_dir / 'data'

    # Load our corpus
    print("Loading data...")
    with open(data_dir / 'scraped_legislation.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    documents = data.get('regulations', data)
    print(f"Total documents in corpus: {len(documents):,}")

    # Aviation-related patterns
    aviation_keywords = [
        r'\baviation\b', r'\baircraft\b', r'\bairworthiness\b', r'\bairspace\b',
        r'\bCASA\b', r'\bcivil aviation\b', r'\bflight\b', r'\bairport\b',
        r'\baeronautical\b', r'\bairline\b', r'\bhelicopter\b', r'\bAD/', r'\bCAO\b',
        r'\baircraft\b', r'\bpilot\b', r'\bavionics\b'
    ]
    aviation_pattern = re.compile('|'.join(aviation_keywords), re.IGNORECASE)

    # Categorize documents
    aviation_docs = []
    non_aviation_docs = []
    acts = []
    instruments = []

    # Track by collection type
    by_collection = defaultdict(int)

    # Track aviation by title vs text match
    aviation_by_title = 0
    aviation_by_text = 0

    for doc in documents:
        register_id = doc.get('register_id', doc.get('id', ''))
        title = doc.get('title', '')
        text = doc.get('text', '')
        collection = doc.get('collection', '').lower()

        by_collection[collection] += 1

        if collection == 'act':
            acts.append(doc)
        else:
            instruments.append(doc)

        # Check if aviation-related
        is_aviation = False
        title_match = aviation_pattern.search(title)
        text_match = aviation_pattern.search(text[:5000]) if text else None

        # Also check register_id patterns for airworthiness directives
        # F2006B02002 pattern - many are aviation ADs
        if 'AD/' in title or 'airworthiness' in title.lower():
            is_aviation = True
            aviation_by_title += 1
        elif title_match:
            is_aviation = True
            aviation_by_title += 1
        elif text_match and ('aviation' in text.lower()[:5000] or 'aircraft' in text.lower()[:5000]):
            is_aviation = True
            aviation_by_text += 1

        if is_aviation:
            aviation_docs.append(doc)
        else:
            non_aviation_docs.append(doc)

    print("\n" + "=" * 80)
    print("DOCUMENT BREAKDOWN")
    print("=" * 80)
    print(f"\nBy collection type:")
    for coll, count in sorted(by_collection.items(), key=lambda x: -x[1]):
        print(f"  {coll}: {count:,}")

    print(f"\nActs: {len(acts):,}")
    print(f"Instruments: {len(instruments):,}")

    print("\n" + "=" * 80)
    print("AVIATION ANALYSIS")
    print("=" * 80)
    print(f"\nAviation-related documents: {len(aviation_docs):,}")
    print(f"  - Matched by title: {aviation_by_title:,}")
    print(f"  - Matched by text only: {aviation_by_text:,}")
    print(f"Non-aviation documents: {len(non_aviation_docs):,}")

    # Aviation breakdown by type
    aviation_acts = sum(1 for d in aviation_docs if d.get('collection', '').lower() == 'act')
    aviation_instruments = len(aviation_docs) - aviation_acts
    print(f"\nAviation breakdown:")
    print(f"  Acts: {aviation_acts:,}")
    print(f"  Instruments: {aviation_instruments:,}")

    # Sample aviation documents
    print("\nSample aviation-related titles:")
    for doc in aviation_docs[:15]:
        title = doc.get('title', '')[:80]
        print(f"  - {title}")

    print("\n" + "=" * 80)
    print("COMPARISON WITH MANDALA")
    print("=" * 80)

    mandala_total = 9600  # Their 2024 figure
    our_total = len(documents)
    our_non_aviation = len(non_aviation_docs)

    print(f"\nMandala 2024 total (excl. aviation): ~{mandala_total:,}")
    print(f"Our total: {our_total:,}")
    print(f"Our total excluding aviation: {our_non_aviation:,}")
    print(f"\nDifference from Mandala: {our_non_aviation - mandala_total:,}")

    # Check repeal status in our data
    print("\n" + "=" * 80)
    print("REPEAL STATUS ANALYSIS")
    print("=" * 80)

    has_status_history = 0
    repealed_count = 0
    in_force_count = 0

    for doc in documents:
        status_history = doc.get('statusHistory', [])
        if status_history:
            has_status_history += 1
            for status in status_history:
                if status.get('status') == 'Repealed':
                    repealed_count += 1
                    break
                elif status.get('status') == 'InForce':
                    in_force_count += 1

    print(f"\nDocuments with statusHistory: {has_status_history:,}")
    print(f"Documents marked as repealed (in statusHistory): {repealed_count:,}")
    print(f"Documents marked as InForce (in statusHistory): {in_force_count:,}")

    # Check isInForce field
    is_in_force_true = sum(1 for d in documents if d.get('isInForce', False))
    is_in_force_false = sum(1 for d in documents if d.get('isInForce') == False)
    is_in_force_none = sum(1 for d in documents if d.get('isInForce') is None)

    print(f"\nisInForce field:")
    print(f"  True: {is_in_force_true:,}")
    print(f"  False: {is_in_force_false:,}")
    print(f"  Not present/None: {is_in_force_none:,}")

    # Non-aviation breakdown for comparison
    non_aviation_acts = sum(1 for d in non_aviation_docs if d.get('collection', '').lower() == 'act')
    non_aviation_instruments = len(non_aviation_docs) - non_aviation_acts

    print("\n" + "=" * 80)
    print("NON-AVIATION COUNTS (for Mandala comparison)")
    print("=" * 80)
    print(f"\nNon-aviation Acts: {non_aviation_acts:,}")
    print(f"Non-aviation Instruments: {non_aviation_instruments:,}")
    print(f"Non-aviation Total: {len(non_aviation_docs):,}")

    # Our methodology issue
    print("\n" + "=" * 80)
    print("METHODOLOGY ISSUE - HOW WE TRACKED 'IN FORCE'")
    print("=" * 80)
    print("""
Our time_series_split_simple.py uses making year from register_id as a proxy:
  - Extract year from register_id (e.g., F2006B09382 -> 2006)
  - Count as "in force at 2025" if making_year <= 2025

This does NOT account for:
  - Actual commencement dates (some legislation commences later)
  - Repeals (legislation that was repealed is still counted)
  - Sunset clauses

Mandala methodology:
  - Uses ALRC DataHub which tracks actual in-force status
  - Excludes repealed legislation
  - Excludes civil aviation legislation entirely
""")

if __name__ == "__main__":
    main()
