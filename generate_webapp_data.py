#!/usr/bin/env python3
"""
Generate CSV data for web app visualization.

Columns:
- year: Making year of the legislation (proxy for in-force date)
- register_id: Unique identifier
- title: Name of the act/instrument
- type: Primary (Act) or Secondary (Legislative Instrument)
- subtype: More specific categorization for filtering
- anzsic_code: Primary ANZSIC division code
- anzsic_name: Industry name
- bc_requirements: BC methodology count
- regdata_requirements: RegData methodology count

Includes all legislation (aviation, tariff concessions) with sub-types for filtering.
"""

import json
import re
import csv
import random
import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# ============================================================================
# ANZSIC Classification
# ============================================================================

ANZSIC_DIVISIONS = {
    'A': 'Agriculture, Forestry and Fishing',
    'B': 'Mining',
    'C': 'Manufacturing',
    'D': 'Electricity, Gas, Water and Waste Services',
    'E': 'Construction',
    'F': 'Wholesale Trade',
    'G': 'Retail Trade',
    'H': 'Accommodation and Food Services',
    'I': 'Transport, Postal and Warehousing',
    'J': 'Information Media and Telecommunications',
    'K': 'Financial and Insurance Services',
    'L': 'Rental, Hiring and Real Estate Services',
    'M': 'Professional, Scientific and Technical Services',
    'N': 'Administrative and Support Services',
    'O': 'Public Administration and Safety',
    'P': 'Education and Training',
    'Q': 'Health Care and Social Assistance',
    'R': 'Arts and Recreation Services',
    'S': 'Other Services',
    'X': 'Cross-cutting (Multiple Industries)',
    'U': 'Unclassified',
}

ANZSIC_KEYWORDS = {
    'O': ['government', 'public administration', 'defence', 'defense', 'national security', 'intelligence', 'military', 'ADF', 'AFP', 'ASIO', 'police', 'law enforcement', 'emergency', 'fire service', 'correctional', 'prison', 'border', 'customs', 'immigration', 'public service', 'commonwealth', 'federal', 'minister'],
    'Q': ['health', 'medical', 'hospital', 'healthcare', 'patient', 'pharmaceutical', 'medicine', 'therapy', 'therapeutic', 'drug', 'aged care', 'disability', 'mental health', 'medicare', 'PBS', 'NDIS', 'nursing', 'dental', 'pathology', 'diagnostic'],
    'K': ['banking', 'bank', 'financial', 'insurance', 'credit', 'loan', 'investment', 'fund', 'superannuation', 'pension', 'APRA', 'ASIC', 'prudential', 'ADI', 'securities', 'money', 'currency', 'payment'],
    'D': ['electricity', 'electric', 'power', 'energy', 'gas', 'water', 'waste', 'sewage', 'renewable', 'solar', 'wind', 'hydro', 'nuclear', 'grid', 'transmission', 'pipeline', 'utility'],
    'I': ['transport', 'aviation', 'maritime', 'shipping', 'rail', 'road', 'airport', 'port', 'cargo', 'freight', 'passenger', 'navigation', 'airlines', 'seafarer', 'postal', 'mail', 'logistics', 'vehicle'],
    'J': ['telecommunications', 'broadcasting', 'media', 'internet', 'television', 'radio', 'radiocommunications', 'spectrum', 'mobile', 'telephone', 'broadband', 'communications', 'digital'],
    'A': ['agriculture', 'farming', 'farm', 'crop', 'livestock', 'cattle', 'sheep', 'dairy', 'poultry', 'fishing', 'fisheries', 'aquaculture', 'forestry', 'timber', 'rural', 'primary producer', 'grain', 'beef', 'wool', 'wheat', 'vineyard', 'biosecurity', 'quarantine'],
    'B': ['mining', 'mine', 'mineral', 'coal', 'iron ore', 'gold', 'copper', 'uranium', 'petroleum', 'oil', 'gas', 'exploration', 'extraction', 'quarry', 'resources', 'offshore', 'drilling', 'seismic'],
    'C': ['manufacturing', 'factory', 'industrial', 'processing', 'automotive', 'chemical', 'textile', 'machinery', 'equipment'],
    'P': ['education', 'school', 'university', 'training', 'student', 'teacher', 'academic', 'higher education', 'tertiary', 'vocational', 'TAFE', 'qualification', 'curriculum'],
    'E': ['construction', 'building', 'infrastructure', 'contractor', 'architect', 'builder', 'project', 'site', 'development'],
    'R': ['arts', 'culture', 'recreation', 'sport', 'entertainment', 'museum', 'library', 'heritage', 'creative', 'gambling', 'gaming', 'lottery', 'national park', 'environment'],
    'F': ['wholesale', 'import', 'export', 'customs', 'tariff', 'trade', 'dealer', 'distributor'],
    'G': ['retail', 'shop', 'store', 'consumer', 'merchandise'],
    'H': ['hotel', 'accommodation', 'tourism', 'restaurant', 'food service', 'hospitality', 'catering', 'tourist', 'visitor'],
    'L': ['rental', 'lease', 'property', 'real estate', 'land', 'housing', 'tenancy', 'landlord', 'native title'],
    'M': ['professional', 'consulting', 'technical', 'scientific', 'research', 'legal', 'accounting', 'veterinary', 'design'],
    'N': ['administrative', 'support services', 'staffing', 'recruitment', 'office', 'security services', 'cleaning', 'maintenance'],
    'S': ['repair', 'personal', 'community', 'religious', 'civic', 'union', 'association', 'organisation'],
}

CROSS_CUTTING_KEYWORDS = ['corporations', 'competition', 'consumer', 'workplace', 'employment', 'fair work', 'privacy', 'taxation', 'GST', 'income tax']


class IndustryClassifier:
    def __init__(self):
        self.patterns = {}
        for code, keywords in ANZSIC_KEYWORDS.items():
            pattern = r'\b(' + '|'.join(re.escape(kw) for kw in keywords) + r')\b'
            self.patterns[code] = re.compile(pattern, re.IGNORECASE)

        self.cross_cutting = re.compile(
            r'\b(' + '|'.join(re.escape(kw) for kw in CROSS_CUTTING_KEYWORDS) + r')\b',
            re.IGNORECASE
        )

    def classify(self, title: str, text: str) -> str:
        scores = {}
        for code, pattern in self.patterns.items():
            title_matches = len(pattern.findall(title)) * 10
            text_matches = len(pattern.findall(text[:3000]))
            if title_matches + text_matches > 0:
                scores[code] = title_matches + text_matches

        if scores:
            return max(scores, key=scores.get)

        combined = f"{title} {text[:3000]}"
        if self.cross_cutting.search(combined):
            return 'X'

        return 'U'


# ============================================================================
# Sub-type Classification
# ============================================================================

def get_subtype(doc) -> str:
    """
    Classify document into a sub-type for filtering.
    Returns a specific sub-type string.
    """
    title = doc.get('title', '')
    title_lower = title.lower()

    # Aviation sub-types
    if 'AD/' in title or title.startswith('ad/'):
        return 'Aviation - Airworthiness Directive'
    if 'CAO ' in title or title.startswith('cao '):
        return 'Aviation - Civil Aviation Order'
    if 'casa ' in title_lower or 'civil aviation safety' in title_lower:
        return 'Aviation - CASA Instrument'
    if 'civil aviation' in title_lower:
        return 'Aviation - Civil Aviation'
    if 'aviation transport security' in title_lower:
        return 'Aviation - Transport Security'
    if 'airspace' in title_lower:
        return 'Aviation - Airspace'
    if 'aircraft noise' in title_lower:
        return 'Aviation - Aircraft Noise'
    if 'air navigation' in title_lower:
        return 'Aviation - Air Navigation'
    if 'airworthiness' in title_lower:
        return 'Aviation - Airworthiness'
    if 'manual of standards part' in title_lower:
        return 'Aviation - Manual of Standards'

    # Other specific sub-types
    if 'tariff concession' in title_lower:
        return 'Tariff Concession Order'
    if 'statement of principles' in title_lower:
        return 'Statement of Principles (RMA)'
    if 'licence area plan' in title_lower:
        return 'Licence Area Plan'
    if 'native title' in title_lower:
        return 'Native Title'
    if 'superannuation' in title_lower and 'family law' in title_lower:
        return 'Superannuation Family Law'
    if 'biosecurity' in title_lower:
        return 'Biosecurity'
    if 'therapeutic goods' in title_lower:
        return 'Therapeutic Goods'
    if 'export control' in title_lower:
        return 'Export Control'

    # Generic instrument types
    if doc.get('collection', '').lower() == 'act':
        return 'Act'

    # Instrument sub-types based on title
    if ' regulation' in title_lower or title_lower.endswith(' regulations'):
        return 'Regulation'
    if ' determination' in title_lower:
        return 'Determination'
    if ' order' in title_lower:
        return 'Order'
    if ' rules' in title_lower:
        return 'Rules'
    if ' direction' in title_lower:
        return 'Direction'
    if ' notice' in title_lower:
        return 'Notice'
    if ' declaration' in title_lower:
        return 'Declaration'
    if ' standard' in title_lower or 'accounting standard' in title_lower:
        return 'Standard'
    if 'exemption' in title_lower:
        return 'Exemption'
    if 'approval' in title_lower:
        return 'Approval'
    if ' instrument' in title_lower:
        return 'Instrument'
    if 'proclamation' in title_lower:
        return 'Proclamation'

    return 'Other Instrument'


def get_type(doc) -> str:
    """Get primary type (Primary/Secondary)."""
    if doc.get('collection', '').lower() == 'act':
        return 'Primary'
    return 'Secondary'


# ============================================================================
# Requirement Counting
# ============================================================================

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


def extract_year(register_id: str) -> Optional[int]:
    """Extract making year from register_id."""
    match = re.search(r'[CF](\d{4})', register_id)
    return int(match.group(1)) if match else None


# ============================================================================
# Main Processing
# ============================================================================

def process_documents(documents: list, classifier: IndustryClassifier, sample_pct: float = 1.0) -> list:
    """Process documents and return list of row dicts."""

    # Sample if requested
    if sample_pct < 1.0:
        sample_size = int(len(documents) * sample_pct)
        documents = random.sample(documents, sample_size)
        logger.info(f"Sampled {len(documents):,} documents ({sample_pct*100:.0f}%)")

    rows = []
    for doc in documents:
        register_id = doc.get('register_id', doc.get('id', ''))
        title = doc.get('title', '')
        text = doc.get('text', '')

        year = extract_year(register_id)
        if not year or year < 2000:
            continue

        doc_type = get_type(doc)
        subtype = get_subtype(doc)
        anzsic_code = classifier.classify(title, text)
        anzsic_name = ANZSIC_DIVISIONS.get(anzsic_code, 'Unknown')
        bc = count_bc(text)
        regdata = count_regdata(text)

        rows.append({
            'making_year': year,
            'register_id': register_id,
            'title': title,
            'type': doc_type,
            'subtype': subtype,
            'anzsic_code': anzsic_code,
            'anzsic_name': anzsic_name,
            'bc_requirements': bc,
            'regdata_requirements': regdata,
        })

    return rows


def generate_time_series_rows(base_rows: list, start_year: int = 2000, end_year: int = 2025) -> list:
    """
    Generate time series rows.
    Each document appears in each year from its making_year through end_year.
    """
    time_series_rows = []

    for row in base_rows:
        making_year = row['making_year']

        # Document is "in force" from making_year onwards
        for year in range(max(making_year, start_year), end_year + 1):
            ts_row = row.copy()
            ts_row['as_of_year'] = year
            ts_row['as_of_date'] = f"{year}-07-01"
            time_series_rows.append(ts_row)

    return time_series_rows


def main():
    base_dir = Path(__file__).parent
    data_dir = base_dir / 'data'
    output_dir = base_dir / 'output'

    # Configuration
    SAMPLE_PCT = 1.0  # Full dataset
    START_YEAR = 2000
    END_YEAR = 2025

    # Load data
    logger.info("Loading data...")
    with open(data_dir / 'scraped_legislation.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    documents = data.get('regulations', data)
    logger.info(f"Loaded {len(documents):,} total documents")

    # Initialize classifier
    classifier = IndustryClassifier()

    # Process documents (10% sample)
    logger.info(f"\nProcessing {SAMPLE_PCT*100:.0f}% sample...")
    base_rows = process_documents(documents, classifier, sample_pct=SAMPLE_PCT)
    logger.info(f"Processed {len(base_rows):,} documents (post-2000)")

    # Collect type/subtype statistics
    type_counts = defaultdict(int)
    subtype_counts = defaultdict(int)

    for row in base_rows:
        type_counts[row['type']] += 1
        subtype_counts[row['subtype']] += 1

    # Print type/subtype summary
    print("\n" + "=" * 70)
    print("TYPES AND SUBTYPES SUMMARY")
    print("=" * 70)

    print("\nTYPES:")
    for t, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"  {t}: {count:,}")

    print("\nSUBTYPES (sorted by count):")
    for st, count in sorted(subtype_counts.items(), key=lambda x: -x[1]):
        pct = count / len(base_rows) * 100
        print(f"  {st}: {count:,} ({pct:.1f}%)")

    # Generate time series (one row per document per year in-force)
    logger.info(f"\nGenerating time series ({START_YEAR}-{END_YEAR})...")
    ts_rows = generate_time_series_rows(base_rows, START_YEAR, END_YEAR)
    logger.info(f"Generated {len(ts_rows):,} time series rows")

    # Save base data CSV (one row per document)
    base_csv_path = output_dir / 'webapp_data_base.csv'
    fieldnames_base = ['making_year', 'register_id', 'title', 'type', 'subtype',
                       'anzsic_code', 'anzsic_name', 'bc_requirements', 'regdata_requirements']

    with open(base_csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames_base)
        writer.writeheader()
        writer.writerows(base_rows)

    logger.info(f"Saved base data: {base_csv_path}")

    # Save time series CSV
    ts_csv_path = output_dir / 'webapp_data_timeseries.csv'
    fieldnames_ts = ['as_of_year', 'as_of_date', 'making_year', 'register_id', 'title',
                     'type', 'subtype', 'anzsic_code', 'anzsic_name',
                     'bc_requirements', 'regdata_requirements']

    with open(ts_csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames_ts)
        writer.writeheader()
        writer.writerows(ts_rows)

    logger.info(f"Saved time series: {ts_csv_path}")

    # Save types/subtypes reference
    types_ref = {
        'types': [
            {'code': 'Primary', 'description': 'Acts of Parliament'},
            {'code': 'Secondary', 'description': 'Legislative Instruments (regulations, rules, etc.)'},
        ],
        'subtypes': [
            {'code': st, 'count': count, 'percentage': round(count/len(base_rows)*100, 1)}
            for st, count in sorted(subtype_counts.items(), key=lambda x: -x[1])
        ],
        'subtype_groups': {
            'Aviation': [
                'Aviation - Airworthiness Directive',
                'Aviation - Civil Aviation Order',
                'Aviation - CASA Instrument',
                'Aviation - Civil Aviation',
                'Aviation - Transport Security',
                'Aviation - Airspace',
                'Aviation - Aircraft Noise',
                'Aviation - Air Navigation',
                'Aviation - Airworthiness',
                'Aviation - Manual of Standards',
            ],
            'Administrative': [
                'Tariff Concession Order',
                'Statement of Principles (RMA)',
                'Licence Area Plan',
                'Superannuation Family Law',
            ],
            'Standard Instruments': [
                'Act',
                'Regulation',
                'Determination',
                'Order',
                'Rules',
                'Direction',
                'Notice',
                'Declaration',
                'Standard',
                'Exemption',
                'Approval',
                'Instrument',
                'Proclamation',
                'Other Instrument',
            ],
            'Sector-Specific': [
                'Native Title',
                'Biosecurity',
                'Therapeutic Goods',
                'Export Control',
            ],
        },
        'anzsic_divisions': [
            {'code': code, 'name': name}
            for code, name in sorted(ANZSIC_DIVISIONS.items())
        ],
    }

    ref_path = output_dir / 'webapp_reference_data.json'
    with open(ref_path, 'w') as f:
        json.dump(types_ref, f, indent=2)

    logger.info(f"Saved reference data: {ref_path}")

    # Summary statistics
    print("\n" + "=" * 70)
    print("OUTPUT SUMMARY")
    print("=" * 70)
    print(f"""
Sample size: {SAMPLE_PCT*100:.0f}% of corpus
Documents processed: {len(base_rows):,}
Time series rows: {len(ts_rows):,}
Year range: {START_YEAR}-{END_YEAR}

Files created:
  - {base_csv_path.name} ({base_csv_path.stat().st_size/1024:.1f} KB)
  - {ts_csv_path.name} ({ts_csv_path.stat().st_size/1024:.1f} KB)
  - {ref_path.name}

CSV Columns:
  Base data:
    - making_year: Year the legislation was made
    - register_id: Unique identifier (e.g., C2004A01234)
    - title: Full title of the legislation
    - type: Primary (Act) or Secondary (Instrument)
    - subtype: Specific category for filtering
    - anzsic_code: Primary industry code (A-S, X, U)
    - anzsic_name: Industry name
    - bc_requirements: BC methodology count
    - regdata_requirements: RegData methodology count

  Time series (adds):
    - as_of_year: Reference year (2000-2025)
    - as_of_date: Reference date (July 1 of each year)
""")


if __name__ == "__main__":
    main()
