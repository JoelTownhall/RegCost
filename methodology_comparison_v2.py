#!/usr/bin/env python3
"""
Compare our methodology with Mandala report - refined aviation detection.
"""

import json
import re
from pathlib import Path
from collections import defaultdict

def is_civil_aviation_exclusive(doc):
    """
    Check if a document has the EXCLUSIVE subject matter of civil aviation.
    This is stricter than just mentioning aviation.
    """
    title = doc.get('title', '').lower()
    text = doc.get('text', '')[:10000].lower() if doc.get('text') else ''
    register_id = doc.get('register_id', '')

    # Airworthiness Directives - definitely civil aviation
    if 'AD/' in doc.get('title', '') or title.startswith('ad/'):
        return True, 'Airworthiness Directive'

    # Civil Aviation Orders
    if 'CAO ' in doc.get('title', '') or title.startswith('cao '):
        return True, 'Civil Aviation Order'

    # CASA instruments
    if 'casa ' in title or 'civil aviation safety' in title:
        return True, 'CASA Instrument'

    # Civil aviation regulations/determinations
    if 'civil aviation' in title and ('regulation' in title or 'determination' in title or 'direction' in title):
        return True, 'Civil Aviation Regulation'

    # Aviation Transport Security
    if 'aviation transport security' in title:
        return True, 'Aviation Transport Security'

    # Airspace regulations
    if 'airspace' in title and ('regulation' in title or 'determination' in title):
        return True, 'Airspace Regulation'

    # Flight Path changes
    if 'flight path' in title:
        return True, 'Flight Path'

    # Aircraft noise
    if 'aircraft noise' in title:
        return True, 'Aircraft Noise'

    # Air Navigation
    if 'air navigation' in title and ('regulation' in title or 'order' in title):
        return True, 'Air Navigation'

    # Check for instruments that are exclusively about civil aviation based on text
    # Must have "civil aviation" prominently and not be about other topics
    if 'civil aviation act' in text[:2000] and 'civil aviation' in title:
        return True, 'Civil Aviation Act Reference'

    return False, None


def main():
    base_dir = Path(__file__).parent
    data_dir = base_dir / 'data'

    print("Loading data...")
    with open(data_dir / 'scraped_legislation.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    documents = data.get('regulations', data)
    print(f"Total documents in corpus: {len(documents):,}")

    # Categorize
    aviation_docs = defaultdict(list)
    non_aviation_docs = []
    acts = []
    instruments = []

    for doc in documents:
        collection = doc.get('collection', '').lower()

        if collection == 'act':
            acts.append(doc)
        else:
            instruments.append(doc)

        is_aviation, category = is_civil_aviation_exclusive(doc)
        if is_aviation:
            aviation_docs[category].append(doc)
        else:
            non_aviation_docs.append(doc)

    total_aviation = sum(len(v) for v in aviation_docs.values())

    print("\n" + "=" * 80)
    print("CIVIL AVIATION EXCLUSIVE LEGISLATION (Mandala Exclusion)")
    print("=" * 80)
    print(f"\nTotal civil aviation exclusive: {total_aviation:,}")
    print("\nBreakdown by category:")
    for cat, docs in sorted(aviation_docs.items(), key=lambda x: -len(x[1])):
        print(f"  {cat}: {len(docs):,}")
        # Sample titles
        for d in docs[:3]:
            print(f"    - {d.get('title', '')[:70]}")

    print("\n" + "=" * 80)
    print("COMPARISON WITH MANDALA")
    print("=" * 80)

    mandala_total = 9600
    our_total = len(documents)
    our_non_aviation = len(non_aviation_docs)

    print(f"\nMandala 2024 total (excl. aviation): ~{mandala_total:,}")
    print(f"Our total: {our_total:,}")
    print(f"Our total excluding civil aviation: {our_non_aviation:,}")
    print(f"\nRemaining gap: {our_non_aviation - mandala_total:,}")

    # Non-aviation breakdown
    non_aviation_acts = sum(1 for d in non_aviation_docs if d.get('collection', '').lower() == 'act')
    non_aviation_instruments = len(non_aviation_docs) - non_aviation_acts

    print(f"\nNon-aviation breakdown:")
    print(f"  Acts: {non_aviation_acts:,}")
    print(f"  Instruments: {non_aviation_instruments:,}")

    # Mandala shows ~1,200 acts in 2024 (from their chart on page 6)
    # Let's see the breakdown
    print("\n" + "=" * 80)
    print("ACTS ANALYSIS")
    print("=" * 80)
    print(f"Our Acts: {len(acts):,}")
    print(f"Non-aviation Acts: {non_aviation_acts:,}")

    # Check for Mandala's ALRC source methodology
    print("\n" + "=" * 80)
    print("KEY METHODOLOGY DIFFERENCES")
    print("=" * 80)
    print("""
1. CIVIL AVIATION EXCLUSION:
   - We found ~{:,} exclusively civil aviation documents
   - Mostly Airworthiness Directives and CASA instruments

2. REPEAL TRACKING - CRITICAL ISSUE:
   - Our data has NO statusHistory or isInForce metadata stored
   - We queried API with isInForce=true, but didn't store the field
   - Our time series uses making_year as proxy, not actual in-force status

3. DATA SOURCE:
   - Mandala: ALRC DataHub (tracks actual in-force status over time)
   - Us: legislation.gov.au API (current snapshot, filtered by isInForce=true)

4. REMAINING GAP EXPLANATION:
   - After excluding aviation, we still have {:,} vs Mandala's {:,}
   - Gap of ~{:,} documents

   Possible explanations for remaining gap:
   a) Our API query returned all currently in-force instruments
   b) Mandala may use different "principal" criteria
   c) ALRC may have different categorization
   d) Time period difference (2024 vs 2025)
   e) Our corpus may include instruments that ALRC doesn't count
""".format(total_aviation, our_non_aviation, mandala_total, our_non_aviation - mandala_total))

    # Let's look at what years our instruments are from
    print("\n" + "=" * 80)
    print("DOCUMENTS BY DECADE (Making Year)")
    print("=" * 80)

    by_decade = defaultdict(lambda: {'acts': 0, 'instruments': 0, 'aviation': 0})

    for doc in documents:
        register_id = doc.get('register_id', '')
        collection = doc.get('collection', '').lower()
        match = re.search(r'[CF](\d{4})', register_id)
        if match:
            year = int(match.group(1))
            decade = (year // 10) * 10

            if collection == 'act':
                by_decade[decade]['acts'] += 1
            else:
                by_decade[decade]['instruments'] += 1

            is_aviation, _ = is_civil_aviation_exclusive(doc)
            if is_aviation:
                by_decade[decade]['aviation'] += 1

    print(f"\n{'Decade':<10} {'Acts':>8} {'Instruments':>12} {'Aviation':>10} {'Non-Avi Total':>14}")
    print("-" * 60)
    for decade in sorted(by_decade.keys()):
        d = by_decade[decade]
        non_avi = d['acts'] + d['instruments'] - d['aviation']
        print(f"{decade}s{'':<5} {d['acts']:>8,} {d['instruments']:>12,} {d['aviation']:>10,} {non_avi:>14,}")

    # Sum post-2000 to compare with Mandala claim of "doubled since 2000"
    post_2000_non_avi = sum(
        by_decade[d]['acts'] + by_decade[d]['instruments'] - by_decade[d]['aviation']
        for d in by_decade if d >= 2000
    )
    print(f"\nTotal post-2000 (non-aviation): {post_2000_non_avi:,}")

if __name__ == "__main__":
    main()
