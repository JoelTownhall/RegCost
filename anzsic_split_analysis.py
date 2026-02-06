#!/usr/bin/env python3
"""
ANZSIC Primary Industry Analysis - Split by Primary vs Secondary Legislation.

Creates:
1. Chart of RegData restrictions by industry, split by primary/secondary
2. Chart of document counts by industry, split by primary/secondary
"""

import json
import re
import logging
from collections import defaultdict
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Optional

import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 1-digit ANZSIC Division keywords (same as anzsic_primary_industry.py)
ANZSIC_DIVISIONS = {
    'O': {'name': 'Public Administration and Safety', 'keywords': ['government', 'public administration', 'defence', 'defense', 'national security', 'intelligence', 'military', 'ADF', 'AFP', 'ASIO', 'police', 'law enforcement', 'emergency', 'fire service', 'correctional', 'prison', 'border', 'customs', 'immigration', 'public service', 'commonwealth', 'federal', 'minister']},
    'Q': {'name': 'Health Care and Social Assistance', 'keywords': ['health', 'medical', 'hospital', 'healthcare', 'patient', 'pharmaceutical', 'medicine', 'therapy', 'therapeutic', 'drug', 'aged care', 'disability', 'mental health', 'medicare', 'PBS', 'NDIS', 'nursing', 'dental', 'pathology', 'diagnostic']},
    'K': {'name': 'Financial and Insurance Services', 'keywords': ['banking', 'bank', 'financial', 'insurance', 'credit', 'loan', 'investment', 'fund', 'superannuation', 'pension', 'APRA', 'ASIC', 'prudential', 'ADI', 'securities', 'money', 'currency', 'payment']},
    'D': {'name': 'Electricity, Gas, Water and Waste', 'keywords': ['electricity', 'electric', 'power', 'energy', 'gas', 'water', 'waste', 'sewage', 'renewable', 'solar', 'wind', 'hydro', 'nuclear', 'grid', 'transmission', 'pipeline', 'utility']},
    'I': {'name': 'Transport, Postal and Warehousing', 'keywords': ['transport', 'aviation', 'maritime', 'shipping', 'rail', 'road', 'airport', 'port', 'cargo', 'freight', 'passenger', 'navigation', 'airlines', 'seafarer', 'postal', 'mail', 'logistics', 'vehicle']},
    'J': {'name': 'Information Media and Telecom', 'keywords': ['telecommunications', 'broadcasting', 'media', 'internet', 'television', 'radio', 'radiocommunications', 'spectrum', 'mobile', 'telephone', 'broadband', 'communications', 'digital']},
    'A': {'name': 'Agriculture, Forestry and Fishing', 'keywords': ['agriculture', 'farming', 'farm', 'crop', 'livestock', 'cattle', 'sheep', 'dairy', 'poultry', 'fishing', 'fisheries', 'aquaculture', 'forestry', 'timber', 'rural', 'primary producer', 'grain', 'beef', 'wool', 'wheat', 'vineyard', 'biosecurity', 'quarantine']},
    'B': {'name': 'Mining', 'keywords': ['mining', 'mine', 'mineral', 'coal', 'iron ore', 'gold', 'copper', 'uranium', 'petroleum', 'oil', 'gas', 'exploration', 'extraction', 'quarry', 'resources', 'offshore', 'drilling', 'seismic']},
    'C': {'name': 'Manufacturing', 'keywords': ['manufacturing', 'factory', 'industrial', 'processing', 'automotive', 'chemical', 'textile', 'machinery', 'equipment']},
    'P': {'name': 'Education and Training', 'keywords': ['education', 'school', 'university', 'training', 'student', 'teacher', 'academic', 'higher education', 'tertiary', 'vocational', 'TAFE', 'qualification', 'curriculum']},
    'E': {'name': 'Construction', 'keywords': ['construction', 'building', 'infrastructure', 'contractor', 'architect', 'builder', 'project', 'site', 'development']},
    'R': {'name': 'Arts and Recreation Services', 'keywords': ['arts', 'culture', 'recreation', 'sport', 'entertainment', 'museum', 'library', 'heritage', 'creative', 'gambling', 'gaming', 'lottery', 'national park', 'environment']},
    'F': {'name': 'Wholesale Trade', 'keywords': ['wholesale', 'import', 'export', 'customs', 'tariff', 'trade', 'dealer', 'distributor']},
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
        combined = f"{title} {text[:3000]}"

        scores = {}
        for code, pattern in self.patterns.items():
            # Title matches worth more
            title_matches = len(pattern.findall(title)) * 10
            text_matches = len(pattern.findall(text[:3000]))
            if title_matches + text_matches > 0:
                scores[code] = title_matches + text_matches

        if scores:
            return max(scores, key=scores.get)

        if self.cross_cutting.search(combined):
            return 'X'  # Cross-cutting

        return 'U'  # Unclassified


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
    """Extract year from register_id."""
    match = re.search(r'[CF](\d{4})', register_id)
    return int(match.group(1)) if match else None


def get_legislation_type(register_id: str, collection: str) -> str:
    """Determine if primary or secondary legislation."""
    if collection == 'act' or register_id.startswith('C') and 'A' in register_id[5:9]:
        return 'primary'
    return 'secondary'


def main():
    base_dir = Path(__file__).parent
    data_dir = base_dir / 'data'
    output_dir = base_dir / 'output'

    # Load data
    logger.info("Loading data...")
    with open(data_dir / 'scraped_legislation.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    documents = data.get('regulations', data)
    logger.info(f"Loaded {len(documents):,} documents")

    # Classify all documents
    classifier = IndustryClassifier()
    classified = []

    logger.info("Classifying documents...")
    for doc in documents:
        register_id = doc.get('register_id', doc.get('id', ''))
        title = doc.get('title', '')
        text = doc.get('text', '')
        collection = doc.get('collection', '')

        industry = classifier.classify(title, text)
        leg_type = get_legislation_type(register_id, collection)
        regdata = count_regdata(text)
        year = extract_year(register_id)

        classified.append({
            'register_id': register_id,
            'industry': industry,
            'legislation_type': leg_type,
            'regdata': regdata,
            'year': year,
        })

    # Filter to 2025 in-force (using year <= 2025 as proxy)
    in_force_2025 = [d for d in classified if d['year'] and d['year'] <= 2025]
    logger.info(f"Documents in force 2025: {len(in_force_2025):,}")

    # Aggregate by industry and legislation type
    industry_stats = defaultdict(lambda: {
        'primary_count': 0, 'primary_regdata': 0,
        'secondary_count': 0, 'secondary_regdata': 0,
    })

    for doc in in_force_2025:
        ind = doc['industry']
        lt = doc['legislation_type']

        if lt == 'primary':
            industry_stats[ind]['primary_count'] += 1
            industry_stats[ind]['primary_regdata'] += doc['regdata']
        else:
            industry_stats[ind]['secondary_count'] += 1
            industry_stats[ind]['secondary_regdata'] += doc['regdata']

    # Print summary
    print("\n" + "=" * 100)
    print("ANZSIC PRIMARY INDUSTRY ANALYSIS - BY LEGISLATION TYPE (2025)")
    print("=" * 100)
    print(f"{'Industry':<45} {'Primary':>12} {'Secondary':>12} {'Pri RegData':>12} {'Sec RegData':>12}")
    print("-" * 100)

    # Sort by total regdata
    sorted_industries = sorted(industry_stats.keys(),
                               key=lambda x: industry_stats[x]['primary_regdata'] + industry_stats[x]['secondary_regdata'],
                               reverse=True)

    for ind in sorted_industries:
        stats = industry_stats[ind]
        name = ANZSIC_DIVISIONS.get(ind, {}).get('name', 'Cross-cutting' if ind == 'X' else 'Unclassified')
        print(f"{ind} - {name[:40]:<43} {stats['primary_count']:>12,} {stats['secondary_count']:>12,} "
              f"{stats['primary_regdata']:>12,} {stats['secondary_regdata']:>12,}")

    # Create charts
    create_regdata_chart(industry_stats, output_dir / 'anzsic_regdata_by_legislation_type.png')
    create_count_chart(industry_stats, output_dir / 'anzsic_count_by_legislation_type.png')

    # Save JSON
    output_data = {
        'generated_at': datetime.now().isoformat(),
        'by_industry': {k: dict(v) for k, v in industry_stats.items()}
    }
    with open(output_dir / 'anzsic_split_analysis.json', 'w') as f:
        json.dump(output_data, f, indent=2)

    logger.info("Analysis complete!")


def create_regdata_chart(stats: Dict, output_path: Path):
    """Create horizontal stacked bar chart of RegData by industry."""
    # Sort by total regdata descending
    sorted_inds = sorted(stats.keys(),
                        key=lambda x: stats[x]['primary_regdata'] + stats[x]['secondary_regdata'],
                        reverse=True)

    # Filter out tiny categories
    sorted_inds = [i for i in sorted_inds if stats[i]['primary_regdata'] + stats[i]['secondary_regdata'] > 1000]

    industries = []
    for ind in sorted_inds:
        name = ANZSIC_DIVISIONS.get(ind, {}).get('name', 'Cross-cutting' if ind == 'X' else 'Unclassified')
        industries.append(f"{ind} - {name}")

    primary_vals = [stats[i]['primary_regdata'] for i in sorted_inds]
    secondary_vals = [stats[i]['secondary_regdata'] for i in sorted_inds]

    fig, ax = plt.subplots(figsize=(14, 10))

    y = range(len(industries))

    bars1 = ax.barh(y, primary_vals, label='Primary (Acts)', color='#2E86AB')
    bars2 = ax.barh(y, secondary_vals, left=primary_vals, label='Secondary (Instruments)', color='#A23B72')

    ax.set_yticks(y)
    ax.set_yticklabels(industries, fontsize=9)
    ax.invert_yaxis()

    ax.set_xlabel('RegData Restrictions', fontsize=12)
    ax.set_title('Regulatory Restrictions by ANZSIC Industry (2025)\nPrimary vs Secondary Legislation',
                fontsize=14, fontweight='bold')
    ax.legend(loc='lower right')

    # Add totals
    for i, ind in enumerate(sorted_inds):
        total = stats[ind]['primary_regdata'] + stats[ind]['secondary_regdata']
        ax.text(total + 200, i, f'{total:,}', va='center', fontsize=9)

    plt.tight_layout()
    plt.savefig(str(output_path), dpi=150, bbox_inches='tight')
    plt.close()
    logger.info(f"RegData chart saved to {output_path}")


def create_count_chart(stats: Dict, output_path: Path):
    """Create horizontal stacked bar chart of document counts by industry."""
    # Sort by total count descending
    sorted_inds = sorted(stats.keys(),
                        key=lambda x: stats[x]['primary_count'] + stats[x]['secondary_count'],
                        reverse=True)

    # Filter out tiny categories
    sorted_inds = [i for i in sorted_inds if stats[i]['primary_count'] + stats[i]['secondary_count'] > 50]

    industries = []
    for ind in sorted_inds:
        name = ANZSIC_DIVISIONS.get(ind, {}).get('name', 'Cross-cutting' if ind == 'X' else 'Unclassified')
        industries.append(f"{ind} - {name}")

    primary_vals = [stats[i]['primary_count'] for i in sorted_inds]
    secondary_vals = [stats[i]['secondary_count'] for i in sorted_inds]

    fig, ax = plt.subplots(figsize=(14, 10))

    y = range(len(industries))

    bars1 = ax.barh(y, primary_vals, label='Primary (Acts)', color='#2E86AB')
    bars2 = ax.barh(y, secondary_vals, left=primary_vals, label='Secondary (Instruments)', color='#A23B72')

    ax.set_yticks(y)
    ax.set_yticklabels(industries, fontsize=9)
    ax.invert_yaxis()

    ax.set_xlabel('Number of Documents', fontsize=12)
    ax.set_title('Legislation Count by ANZSIC Industry (2025)\nPrimary vs Secondary Legislation',
                fontsize=14, fontweight='bold')
    ax.legend(loc='lower right')

    # Add totals
    for i, ind in enumerate(sorted_inds):
        total = stats[ind]['primary_count'] + stats[ind]['secondary_count']
        ax.text(total + 20, i, f'{total:,}', va='center', fontsize=9)

    plt.tight_layout()
    plt.savefig(str(output_path), dpi=150, bbox_inches='tight')
    plt.close()
    logger.info(f"Count chart saved to {output_path}")


if __name__ == "__main__":
    main()
