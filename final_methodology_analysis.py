#!/usr/bin/env python3
"""
Final analysis of methodology differences with Mandala.
"""

import json
import re
from pathlib import Path
from collections import defaultdict

def is_civil_aviation_exclusive_v2(doc):
    """Broader check for civil aviation instruments."""
    title = doc.get('title', '')
    title_lower = title.lower()

    # Direct aviation indicators
    if 'AD/' in title or title.startswith('ad/'):
        return True, 'AD'
    if 'CAO ' in title or title.startswith('cao '):
        return True, 'CAO'
    if 'casa ' in title_lower or 'civil aviation safety' in title_lower:
        return True, 'CASA'
    if 'civil aviation' in title_lower:
        return True, 'Civil Aviation'
    if 'aviation transport security' in title_lower:
        return True, 'Aviation Security'
    if 'airspace' in title_lower:
        return True, 'Airspace'
    if 'aircraft noise' in title_lower:
        return True, 'Aircraft Noise'
    if 'air navigation' in title_lower:
        return True, 'Air Navigation'
    if 'airworthiness' in title_lower:
        return True, 'Airworthiness'
    if 'manual of standards part' in title_lower:
        # Many are aviation-related MOS
        return True, 'MOS Aviation'

    return False, None


def main():
    base_dir = Path(__file__).parent
    data_dir = base_dir / 'data'

    print("Loading data...")
    with open(data_dir / 'scraped_legislation.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    documents = data.get('regulations', data)

    # Broader aviation check
    aviation_docs = []
    non_aviation_docs = []
    aviation_by_cat = defaultdict(int)

    for doc in documents:
        is_avi, cat = is_civil_aviation_exclusive_v2(doc)
        if is_avi:
            aviation_docs.append(doc)
            aviation_by_cat[cat] += 1
        else:
            non_aviation_docs.append(doc)

    print("\n" + "=" * 80)
    print("REFINED AVIATION COUNT")
    print("=" * 80)
    print(f"\nTotal aviation (broader definition): {len(aviation_docs):,}")
    for cat, count in sorted(aviation_by_cat.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count:,}")

    print(f"\nNon-aviation remaining: {len(non_aviation_docs):,}")

    # Check Statement of Principles
    sop_docs = [d for d in non_aviation_docs if 'statement of principles' in d.get('title', '').lower()]
    print(f"\n'Statement of Principles' documents: {len(sop_docs):,}")
    if sop_docs:
        print("  Sample titles:")
        for d in sop_docs[:5]:
            print(f"    - {d.get('title', '')[:70]}")

    # Licence Area Plans (radiocommunications)
    lap_docs = [d for d in non_aviation_docs if 'licence area plan' in d.get('title', '').lower()]
    print(f"\n'Licence Area Plan' documents: {len(lap_docs):,}")

    # Superannuation orders (many seem administrative)
    super_docs = [d for d in non_aviation_docs
                  if 'superannuation' in d.get('title', '').lower()
                  and 'family law' in d.get('title', '').lower()]
    print(f"\n'Superannuation Family Law' documents: {len(super_docs):,}")

    # Native Title determinations
    native_title = [d for d in non_aviation_docs if 'native title' in d.get('title', '').lower()]
    print(f"\n'Native Title' documents: {len(native_title):,}")

    print("\n" + "=" * 80)
    print("RECONCILIATION WITH MANDALA")
    print("=" * 80)

    # Start with our total
    total = len(documents)
    print(f"\nOur total documents: {total:,}")

    # Subtract aviation
    after_aviation = len(non_aviation_docs)
    print(f"After excluding aviation: {after_aviation:,}")

    # What if ALRC also excludes certain categories?
    # Statement of Principles might be considered separate (RMA determinations)
    # Licence Area Plans are highly administrative
    # Native Title determinations might be categorized differently

    potentially_excluded = len(sop_docs) + len(lap_docs)
    after_sop_lap = after_aviation - potentially_excluded
    print(f"After excluding SOP + LAP: {after_sop_lap:,}")

    print(f"\nMandala 2024 total: ~9,600")
    print(f"Gap remaining: {after_sop_lap - 9600:,}")

    # Check year distribution for non-aviation
    print("\n" + "=" * 80)
    print("NON-AVIATION BY YEAR (making year from register_id)")
    print("=" * 80)

    by_year = defaultdict(int)
    for doc in non_aviation_docs:
        register_id = doc.get('register_id', '')
        match = re.search(r'[CF](\d{4})', register_id)
        if match:
            year = int(match.group(1))
            by_year[year] += 1

    cumulative = 0
    print(f"\n{'Year':>6} {'New':>8} {'Cumulative':>12}")
    print("-" * 30)
    for year in sorted(by_year.keys()):
        cumulative += by_year[year]
        if year >= 2000:
            print(f"{year:>6} {by_year[year]:>8,} {cumulative:>12,}")

    print("\n" + "=" * 80)
    print("SUMMARY OF KEY DIFFERENCES")
    print("=" * 80)
    print(f"""
Our count: {total:,} documents
Mandala count: ~9,600 documents (2024, excl. aviation)

KEY DIFFERENCES:

1. AVIATION EXCLUSION:
   We found {len(aviation_docs):,} aviation-related documents
   - 8,631 Airworthiness Directives (AD/)
   - Other aviation: {len(aviation_docs) - 8631:,}

2. POSSIBLE OTHER EXCLUSIONS BY ALRC:
   - Statement of Principles (RMA): {len(sop_docs):,}
   - Licence Area Plans: {len(lap_docs):,}
   - These are often administrative instruments

3. REPEAL TRACKING (CRITICAL):
   Our analysis uses making year as proxy for 'in force'
   We do NOT track actual repeals
   ALRC DataHub properly tracks repeal status over time

4. DATA SOURCE DIFFERENCES:
   - We use: legislation.gov.au API (isInForce=true at time of query)
   - Mandala uses: ALRC DataHub (historical in-force tracking)

5. REMAINING GAP (~{after_sop_lap - 9600:,} documents):
   Likely explained by:
   a) Repealed instruments we're still counting
   b) Different definitions of 'principal' legislation
   c) ALRC may exclude other administrative instruments
   d) Possible differences in Legislative Instrument definition
""")

    # Final comparison
    print("\n" + "=" * 80)
    print("FINAL COUNT COMPARISON")
    print("=" * 80)
    non_avi_acts = sum(1 for d in non_aviation_docs if d.get('collection', '').lower() == 'act')
    non_avi_instr = len(non_aviation_docs) - non_avi_acts
    print(f"""
MANDALA (2024, excl. aviation):
  Acts: ~1,200 (from page 6 chart showing ~9,500 with same acts proportion)
  Legislative Instruments: ~8,400
  Total: ~9,600

OUR DATA (excl. aviation):
  Acts: {non_avi_acts:,}
  Legislative Instruments: {non_avi_instr:,}
  Total: {len(non_aviation_docs):,}

ACTS COMPARISON:
  Mandala ~1,200 vs Our {non_avi_acts:,} = fairly close!

INSTRUMENTS COMPARISON:
  Mandala ~8,400 vs Our {non_avi_instr:,}
  Gap: ~{non_avi_instr - 8400:,} instruments

CONCLUSION:
  The ~5,600 instrument gap is likely due to:
  1. Statement of Principles ({len(sop_docs)})
  2. Licence Area Plans ({len(lap_docs)})
  3. Repealed instruments not filtered out
  4. Other administrative instruments ALRC excludes
""")

if __name__ == "__main__":
    main()
