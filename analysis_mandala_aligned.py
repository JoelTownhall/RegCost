#!/usr/bin/env python3
"""
Mandala-Aligned Analysis - Time Series and ANZSIC Charts.

Excludes:
1. Civil aviation legislation (exclusive subject matter)
2. Tariff Concession Orders

This produces counts comparable to the Mandala report methodology.
"""

import json
import re
import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# ============================================================================
# Exclusion Functions
# ============================================================================

def is_civil_aviation_exclusive(doc):
    """
    Check if a document has the EXCLUSIVE subject matter of civil aviation.
    These are excluded from Mandala/ALRC counts.
    """
    title = doc.get('title', '')
    title_lower = title.lower()

    # Airworthiness Directives
    if 'AD/' in title or title.startswith('ad/'):
        return True
    # Civil Aviation Orders
    if 'CAO ' in title or title.startswith('cao '):
        return True
    # CASA instruments
    if 'casa ' in title_lower or 'civil aviation safety' in title_lower:
        return True
    # Civil aviation regulations/determinations
    if 'civil aviation' in title_lower:
        return True
    # Aviation Transport Security
    if 'aviation transport security' in title_lower:
        return True
    # Airspace regulations
    if 'airspace' in title_lower:
        return True
    # Aircraft noise
    if 'aircraft noise' in title_lower:
        return True
    # Air Navigation
    if 'air navigation' in title_lower:
        return True
    # Airworthiness
    if 'airworthiness' in title_lower:
        return True
    # Manual of Standards (aviation-related)
    if 'manual of standards part' in title_lower:
        return True

    return False


def is_tariff_concession(doc):
    """Check if document is a Tariff Concession Order."""
    title = doc.get('title', '').lower()
    return 'tariff concession' in title


def should_exclude(doc):
    """Check if document should be excluded from analysis."""
    return is_civil_aviation_exclusive(doc) or is_tariff_concession(doc)


# ============================================================================
# Analysis Functions
# ============================================================================

def extract_year(register_id: str) -> Optional[int]:
    """Extract year from register_id."""
    match = re.search(r'[CF](\d{4})', register_id)
    return int(match.group(1)) if match else None


def get_legislation_type(collection: str) -> str:
    """Determine if primary or secondary legislation."""
    if collection.lower() == 'act':
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


# ============================================================================
# ANZSIC Classification
# ============================================================================

ANZSIC_DIVISIONS = {
    'O': {'name': 'Public Administration and Safety', 'keywords': ['government', 'public administration', 'defence', 'defense', 'national security', 'intelligence', 'military', 'ADF', 'AFP', 'ASIO', 'police', 'law enforcement', 'emergency', 'fire service', 'correctional', 'prison', 'border', 'customs', 'immigration', 'public service', 'commonwealth', 'federal', 'minister']},
    'Q': {'name': 'Health Care and Social Assistance', 'keywords': ['health', 'medical', 'hospital', 'healthcare', 'patient', 'pharmaceutical', 'medicine', 'therapy', 'therapeutic', 'drug', 'aged care', 'disability', 'mental health', 'medicare', 'PBS', 'NDIS', 'nursing', 'dental', 'pathology', 'diagnostic']},
    'K': {'name': 'Financial and Insurance Services', 'keywords': ['banking', 'bank', 'financial', 'insurance', 'credit', 'loan', 'investment', 'fund', 'superannuation', 'pension', 'APRA', 'ASIC', 'prudential', 'ADI', 'securities', 'money', 'currency', 'payment']},
    'D': {'name': 'Electricity, Gas, Water and Waste', 'keywords': ['electricity', 'electric', 'power', 'energy', 'gas', 'water', 'waste', 'sewage', 'renewable', 'solar', 'wind', 'hydro', 'nuclear', 'grid', 'transmission', 'pipeline', 'utility']},
    'I': {'name': 'Transport, Postal and Warehousing', 'keywords': ['transport', 'maritime', 'shipping', 'rail', 'road', 'port', 'cargo', 'freight', 'passenger', 'navigation', 'seafarer', 'postal', 'mail', 'logistics', 'vehicle']},
    'J': {'name': 'Information Media and Telecom', 'keywords': ['telecommunications', 'broadcasting', 'media', 'internet', 'television', 'radio', 'radiocommunications', 'spectrum', 'mobile', 'telephone', 'broadband', 'communications', 'digital']},
    'A': {'name': 'Agriculture, Forestry and Fishing', 'keywords': ['agriculture', 'farming', 'farm', 'crop', 'livestock', 'cattle', 'sheep', 'dairy', 'poultry', 'fishing', 'fisheries', 'aquaculture', 'forestry', 'timber', 'rural', 'primary producer', 'grain', 'beef', 'wool', 'wheat', 'vineyard', 'biosecurity', 'quarantine']},
    'B': {'name': 'Mining', 'keywords': ['mining', 'mine', 'mineral', 'coal', 'iron ore', 'gold', 'copper', 'uranium', 'petroleum', 'oil', 'gas', 'exploration', 'extraction', 'quarry', 'resources', 'offshore', 'drilling', 'seismic']},
    'C': {'name': 'Manufacturing', 'keywords': ['manufacturing', 'factory', 'industrial', 'processing', 'automotive', 'chemical', 'textile', 'machinery', 'equipment']},
    'P': {'name': 'Education and Training', 'keywords': ['education', 'school', 'university', 'training', 'student', 'teacher', 'academic', 'higher education', 'tertiary', 'vocational', 'TAFE', 'qualification', 'curriculum']},
    'E': {'name': 'Construction', 'keywords': ['construction', 'building', 'infrastructure', 'contractor', 'architect', 'builder', 'project', 'site', 'development']},
    'R': {'name': 'Arts and Recreation Services', 'keywords': ['arts', 'culture', 'recreation', 'sport', 'entertainment', 'museum', 'library', 'heritage', 'creative', 'gambling', 'gaming', 'lottery', 'national park', 'environment']},
    'F': {'name': 'Wholesale Trade', 'keywords': ['wholesale', 'import', 'export', 'trade', 'dealer', 'distributor']},
    'G': {'name': 'Retail Trade', 'keywords': ['retail', 'shop', 'store', 'consumer', 'merchandise']},
    'H': {'name': 'Accommodation and Food Services', 'keywords': ['hotel', 'accommodation', 'tourism', 'restaurant', 'food service', 'hospitality', 'catering', 'tourist', 'visitor']},
    'L': {'name': 'Rental, Hiring and Real Estate', 'keywords': ['rental', 'lease', 'property', 'real estate', 'land', 'housing', 'tenancy', 'landlord', 'native title']},
    'M': {'name': 'Professional, Scientific, Technical', 'keywords': ['professional', 'consulting', 'technical', 'scientific', 'research', 'legal', 'accounting', 'veterinary', 'design']},
    'N': {'name': 'Administrative and Support Services', 'keywords': ['administrative', 'support services', 'staffing', 'recruitment', 'office', 'security services', 'cleaning', 'maintenance']},
    'S': {'name': 'Other Services', 'keywords': ['repair', 'personal', 'community', 'religious', 'civic', 'union', 'association', 'organisation']},
}

CROSS_CUTTING_KEYWORDS = ['corporations', 'competition', 'consumer', 'workplace', 'employment', 'fair work', 'privacy', 'taxation', 'GST', 'income tax']


class IndustryClassifier:
    def __init__(self):
        self.patterns = {}
        for code, div in ANZSIC_DIVISIONS.items():
            pattern = r'\b(' + '|'.join(re.escape(kw) for kw in div['keywords']) + r')\b'
            self.patterns[code] = re.compile(pattern, re.IGNORECASE)

        self.cross_cutting = re.compile(
            r'\b(' + '|'.join(re.escape(kw) for kw in CROSS_CUTTING_KEYWORDS) + r')\b',
            re.IGNORECASE
        )

    def classify(self, title: str, text: str) -> str:
        """Return primary industry code."""
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
            return 'X'  # Cross-cutting

        return 'U'  # Unclassified


# ============================================================================
# Chart Generation
# ============================================================================

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

    ax.set_xlabel('Year', fontsize=12)
    ax.set_ylabel('Regulatory Requirements', fontsize=12)
    ax.set_title('Australian Federal Regulatory Requirements\n(Excluding Aviation & Tariff Concessions)',
                fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(years)
    ax.legend(loc='upper left')

    # Add totals
    for i, y in enumerate(years):
        bc_total = results[y]['primary']['bc'] + results[y]['secondary']['bc']
        reg_total = results[y]['primary']['regdata'] + results[y]['secondary']['regdata']
        ax.text(i - width/2, bc_total + 2000, f'{bc_total:,}', ha='center', fontsize=9)
        ax.text(i + width/2, reg_total + 2000, f'{reg_total:,}', ha='center', fontsize=9)

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

    ax.set_xlabel('Year', fontsize=12)
    ax.set_ylabel('Number of Documents in Force', fontsize=12)
    ax.set_title('Growth of Australian Federal Legislation\n(Excluding Aviation & Tariff Concessions)',
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
        ax.text(i, total + 150, f'{total:,}', ha='center', fontsize=10, fontweight='bold')

    plt.tight_layout()
    plt.savefig(str(output_path), dpi=150, bbox_inches='tight')
    plt.close()
    logger.info(f"Document count chart saved to {output_path}")


def create_anzsic_regdata_chart(stats: Dict, output_path: Path):
    """Create horizontal stacked bar chart of RegData by industry."""
    sorted_inds = sorted(stats.keys(),
                        key=lambda x: stats[x]['primary_regdata'] + stats[x]['secondary_regdata'],
                        reverse=True)

    # Filter out small categories
    sorted_inds = [i for i in sorted_inds if stats[i]['primary_regdata'] + stats[i]['secondary_regdata'] > 500]

    industries = []
    for ind in sorted_inds:
        name = ANZSIC_DIVISIONS.get(ind, {}).get('name', 'Cross-cutting' if ind == 'X' else 'Unclassified')
        industries.append(f"{ind} - {name}")

    primary_vals = [stats[i]['primary_regdata'] for i in sorted_inds]
    secondary_vals = [stats[i]['secondary_regdata'] for i in sorted_inds]

    fig, ax = plt.subplots(figsize=(14, 10))

    y = range(len(industries))

    ax.barh(y, primary_vals, label='Primary (Acts)', color='#2E86AB')
    ax.barh(y, secondary_vals, left=primary_vals, label='Secondary (Instruments)', color='#A23B72')

    ax.set_yticks(y)
    ax.set_yticklabels(industries, fontsize=9)
    ax.invert_yaxis()

    ax.set_xlabel('RegData Restrictions', fontsize=12)
    ax.set_title('Regulatory Restrictions by ANZSIC Industry\n(Excluding Aviation & Tariff Concessions)',
                fontsize=14, fontweight='bold')
    ax.legend(loc='lower right')

    # Add totals
    for i, ind in enumerate(sorted_inds):
        total = stats[ind]['primary_regdata'] + stats[ind]['secondary_regdata']
        ax.text(total + 200, i, f'{total:,}', va='center', fontsize=9)

    plt.tight_layout()
    plt.savefig(str(output_path), dpi=150, bbox_inches='tight')
    plt.close()
    logger.info(f"ANZSIC RegData chart saved to {output_path}")


def create_anzsic_count_chart(stats: Dict, output_path: Path):
    """Create horizontal stacked bar chart of document counts by industry."""
    sorted_inds = sorted(stats.keys(),
                        key=lambda x: stats[x]['primary_count'] + stats[x]['secondary_count'],
                        reverse=True)

    # Filter out small categories
    sorted_inds = [i for i in sorted_inds if stats[i]['primary_count'] + stats[i]['secondary_count'] > 20]

    industries = []
    for ind in sorted_inds:
        name = ANZSIC_DIVISIONS.get(ind, {}).get('name', 'Cross-cutting' if ind == 'X' else 'Unclassified')
        industries.append(f"{ind} - {name}")

    primary_vals = [stats[i]['primary_count'] for i in sorted_inds]
    secondary_vals = [stats[i]['secondary_count'] for i in sorted_inds]

    fig, ax = plt.subplots(figsize=(14, 10))

    y = range(len(industries))

    ax.barh(y, primary_vals, label='Primary (Acts)', color='#2E86AB')
    ax.barh(y, secondary_vals, left=primary_vals, label='Secondary (Instruments)', color='#A23B72')

    ax.set_yticks(y)
    ax.set_yticklabels(industries, fontsize=9)
    ax.invert_yaxis()

    ax.set_xlabel('Number of Documents', fontsize=12)
    ax.set_title('Legislation Count by ANZSIC Industry\n(Excluding Aviation & Tariff Concessions)',
                fontsize=14, fontweight='bold')
    ax.legend(loc='lower right')

    # Add totals
    for i, ind in enumerate(sorted_inds):
        total = stats[ind]['primary_count'] + stats[ind]['secondary_count']
        ax.text(total + 10, i, f'{total:,}', va='center', fontsize=9)

    plt.tight_layout()
    plt.savefig(str(output_path), dpi=150, bbox_inches='tight')
    plt.close()
    logger.info(f"ANZSIC count chart saved to {output_path}")


# ============================================================================
# Main Analysis
# ============================================================================

def main():
    base_dir = Path(__file__).parent
    data_dir = base_dir / 'data'
    output_dir = base_dir / 'output'
    output_dir.mkdir(exist_ok=True)

    time_points = [2010, 2015, 2020, 2025]

    # Load data
    logger.info("Loading data...")
    with open(data_dir / 'scraped_legislation.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    documents = data.get('regulations', data)
    logger.info(f"Loaded {len(documents):,} total documents")

    # Filter out excluded documents
    included_docs = [d for d in documents if not should_exclude(d)]
    excluded_count = len(documents) - len(included_docs)

    logger.info(f"Excluded {excluded_count:,} documents (aviation + tariff concessions)")
    logger.info(f"Analyzing {len(included_docs):,} documents")

    # Count exclusions by type
    aviation_count = sum(1 for d in documents if is_civil_aviation_exclusive(d))
    tariff_count = sum(1 for d in documents if is_tariff_concession(d))
    logger.info(f"  - Aviation: {aviation_count:,}")
    logger.info(f"  - Tariff Concessions: {tariff_count:,}")

    # ========================================================================
    # Time Series Analysis
    # ========================================================================
    logger.info("\n" + "=" * 70)
    logger.info("TIME SERIES ANALYSIS")
    logger.info("=" * 70)

    # Process documents for time series
    processed = []
    for doc in included_docs:
        register_id = doc.get('register_id', doc.get('id', ''))
        collection = doc.get('collection', '')
        text = doc.get('text', '')

        year = extract_year(register_id)
        if not year:
            continue

        leg_type = get_legislation_type(collection)
        bc = count_bc(text)
        regdata = count_regdata(text)

        processed.append({
            'year': year,
            'type': leg_type,
            'bc': bc,
            'regdata': regdata,
            'title': doc.get('title', ''),
            'text': text,
        })

    logger.info(f"Processed {len(processed):,} documents with valid years")

    # Aggregate by time period
    time_results = {}
    for cutoff_year in time_points:
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

        time_results[cutoff_year] = stats

    # Print time series summary
    print("\n" + "=" * 100)
    print("TIME SERIES - PRIMARY VS SECONDARY LEGISLATION (Mandala-Aligned)")
    print("=" * 100)
    print(f"{'Year':<8} {'Pri Docs':>10} {'Sec Docs':>10} {'Total':>10} {'Pri BC':>12} {'Sec BC':>12} {'Pri RegData':>12} {'Sec RegData':>12}")
    print("-" * 100)

    for year in time_points:
        s = time_results[year]
        total = s['primary']['count'] + s['secondary']['count']
        print(f"{year:<8} {s['primary']['count']:>10,} {s['secondary']['count']:>10,} {total:>10,} "
              f"{s['primary']['bc']:>12,} {s['secondary']['bc']:>12,} "
              f"{s['primary']['regdata']:>12,} {s['secondary']['regdata']:>12,}")

    # Compare with Mandala
    print(f"\nMandala 2024 comparison:")
    print(f"  Our Acts (2025): {time_results[2025]['primary']['count']:,} vs Mandala ~1,200")
    print(f"  Our Instruments (2025): {time_results[2025]['secondary']['count']:,} vs Mandala ~8,400")

    # ========================================================================
    # ANZSIC Industry Analysis
    # ========================================================================
    logger.info("\n" + "=" * 70)
    logger.info("ANZSIC INDUSTRY ANALYSIS")
    logger.info("=" * 70)

    classifier = IndustryClassifier()

    # Use 2025 cutoff
    in_force_2025 = [d for d in processed if d['year'] <= 2025]

    industry_stats = defaultdict(lambda: {
        'primary_count': 0, 'primary_regdata': 0,
        'secondary_count': 0, 'secondary_regdata': 0,
    })

    for doc in in_force_2025:
        industry = classifier.classify(doc['title'], doc['text'])
        lt = doc['type']

        if lt == 'primary':
            industry_stats[industry]['primary_count'] += 1
            industry_stats[industry]['primary_regdata'] += doc['regdata']
        else:
            industry_stats[industry]['secondary_count'] += 1
            industry_stats[industry]['secondary_regdata'] += doc['regdata']

    # Print ANZSIC summary
    print("\n" + "=" * 100)
    print("ANZSIC PRIMARY INDUSTRY ANALYSIS (2025, Mandala-Aligned)")
    print("=" * 100)
    print(f"{'Industry':<45} {'Primary':>10} {'Secondary':>10} {'Pri RegData':>12} {'Sec RegData':>12}")
    print("-" * 100)

    sorted_industries = sorted(industry_stats.keys(),
                               key=lambda x: industry_stats[x]['primary_regdata'] + industry_stats[x]['secondary_regdata'],
                               reverse=True)

    for ind in sorted_industries:
        stats = industry_stats[ind]
        name = ANZSIC_DIVISIONS.get(ind, {}).get('name', 'Cross-cutting' if ind == 'X' else 'Unclassified')
        print(f"{ind} - {name[:40]:<43} {stats['primary_count']:>10,} {stats['secondary_count']:>10,} "
              f"{stats['primary_regdata']:>12,} {stats['secondary_regdata']:>12,}")

    # ========================================================================
    # Generate Charts
    # ========================================================================
    logger.info("\nGenerating charts...")

    # Time series charts
    create_requirements_chart(time_results, time_points,
                              output_dir / 'requirements_by_legislation_type.png')
    create_count_chart(time_results, time_points,
                       output_dir / 'document_count_by_legislation_type.png')

    # ANZSIC charts
    create_anzsic_regdata_chart(industry_stats,
                                output_dir / 'anzsic_regdata_by_legislation_type.png')
    create_anzsic_count_chart(industry_stats,
                              output_dir / 'anzsic_count_by_legislation_type.png')

    # ========================================================================
    # Save JSON Results
    # ========================================================================
    output_data = {
        'generated_at': datetime.now().isoformat(),
        'methodology': 'Mandala-aligned (excluding aviation and tariff concessions)',
        'exclusions': {
            'aviation': aviation_count,
            'tariff_concessions': tariff_count,
            'total_excluded': excluded_count,
        },
        'documents_analyzed': len(included_docs),
        'time_series': {str(k): v for k, v in time_results.items()},
        'anzsic_2025': {k: dict(v) for k, v in industry_stats.items()},
    }

    with open(output_dir / 'mandala_aligned_analysis.json', 'w') as f:
        json.dump(output_data, f, indent=2)

    logger.info("\n" + "=" * 70)
    logger.info("ANALYSIS COMPLETE!")
    logger.info("=" * 70)
    logger.info(f"Charts saved to: {output_dir}")
    logger.info("  - requirements_by_legislation_type.png")
    logger.info("  - document_count_by_legislation_type.png")
    logger.info("  - anzsic_regdata_by_legislation_type.png")
    logger.info("  - anzsic_count_by_legislation_type.png")


if __name__ == "__main__":
    main()
