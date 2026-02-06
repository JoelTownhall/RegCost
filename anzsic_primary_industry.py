#!/usr/bin/env python3
"""
ANZSIC Primary Industry Classification for Australian Legislation.

Classifies each piece of legislation to its PRIMARY industry only
(the most relevant single industry), rather than multiple industries.

Uses 1-digit ANZSIC division codes (A-S).
"""

import json
import re
import logging
from collections import defaultdict, Counter
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 1-digit ANZSIC Division Codes with keywords
# Priority order matters - more specific industries should be checked first
ANZSIC_DIVISIONS = {
    'O': {
        'name': 'Public Administration and Safety',
        'keywords': [
            'government', 'public administration', 'defence', 'defense',
            'national security', 'intelligence', 'military', 'ADF', 'AFP',
            'ASIO', 'police', 'law enforcement', 'emergency', 'fire service',
            'correctional', 'prison', 'border', 'customs', 'immigration',
            'public service', 'commonwealth', 'federal', 'minister'
        ],
        'title_patterns': [
            r'\bdefence\b', r'\bpolice\b', r'\bcustoms\b', r'\bimmigration\b',
            r'\bintelligence\b', r'\bsecurity\b', r'\bemergency\b',
            r'\bpublic service\b', r'\bcommonwealth\b'
        ]
    },
    'Q': {
        'name': 'Health Care and Social Assistance',
        'keywords': [
            'health', 'medical', 'hospital', 'healthcare', 'patient',
            'pharmaceutical', 'medicine', 'therapy', 'therapeutic', 'drug',
            'aged care', 'disability', 'mental health', 'medicare', 'PBS',
            'NDIS', 'nursing', 'dental', 'pathology', 'diagnostic'
        ],
        'title_patterns': [
            r'\bhealth\b', r'\bmedical\b', r'\btherapeutic\b', r'\bpharmaceutical\b',
            r'\bdrug\b', r'\baged care\b', r'\bdisability\b', r'\bmedicare\b'
        ]
    },
    'K': {
        'name': 'Financial and Insurance Services',
        'keywords': [
            'banking', 'bank', 'financial', 'insurance', 'credit', 'loan',
            'investment', 'fund', 'superannuation', 'pension', 'APRA', 'ASIC',
            'prudential', 'ADI', 'securities', 'money', 'currency', 'payment'
        ],
        'title_patterns': [
            r'\bbank\b', r'\bfinancial\b', r'\binsurance\b', r'\bsuperannuation\b',
            r'\bprudential\b', r'\bsecurities\b', r'\bcredit\b'
        ]
    },
    'D': {
        'name': 'Electricity, Gas, Water and Waste Services',
        'keywords': [
            'electricity', 'electric', 'power', 'energy', 'gas', 'water',
            'waste', 'sewage', 'renewable', 'solar', 'wind', 'hydro',
            'nuclear', 'grid', 'transmission', 'pipeline', 'utility'
        ],
        'title_patterns': [
            r'\belectricity\b', r'\benergy\b', r'\bgas\b', r'\bwater\b',
            r'\bwaste\b', r'\brenewable\b', r'\bnuclear\b'
        ]
    },
    'I': {
        'name': 'Transport, Postal and Warehousing',
        'keywords': [
            'transport', 'aviation', 'maritime', 'shipping', 'rail', 'road',
            'airport', 'port', 'cargo', 'freight', 'passenger', 'navigation',
            'airlines', 'seafarer', 'postal', 'mail', 'logistics', 'vehicle'
        ],
        'title_patterns': [
            r'\btransport\b', r'\baviation\b', r'\bmaritime\b', r'\bshipping\b',
            r'\brail\b', r'\bairport\b', r'\bport\b', r'\bpostal\b'
        ]
    },
    'J': {
        'name': 'Information Media and Telecommunications',
        'keywords': [
            'telecommunications', 'broadcasting', 'media', 'internet',
            'television', 'radio', 'radiocommunications', 'spectrum',
            'mobile', 'telephone', 'broadband', 'communications', 'digital'
        ],
        'title_patterns': [
            r'\btelecommunications\b', r'\bbroadcasting\b', r'\bmedia\b',
            r'\bradiocommunications\b', r'\bspectrum\b'
        ]
    },
    'A': {
        'name': 'Agriculture, Forestry and Fishing',
        'keywords': [
            'agriculture', 'farming', 'farm', 'crop', 'livestock', 'cattle',
            'sheep', 'dairy', 'poultry', 'fishing', 'fisheries', 'aquaculture',
            'forestry', 'timber', 'rural', 'primary producer', 'grain',
            'beef', 'wool', 'wheat', 'vineyard', 'biosecurity', 'quarantine'
        ],
        'title_patterns': [
            r'\bagricultur', r'\bfarm\b', r'\bfisheries\b', r'\bforestry\b',
            r'\bquarantine\b', r'\bbiosecurity\b', r'\blivestock\b'
        ]
    },
    'B': {
        'name': 'Mining',
        'keywords': [
            'mining', 'mine', 'mineral', 'coal', 'iron ore', 'gold', 'copper',
            'uranium', 'petroleum', 'oil', 'gas', 'exploration', 'extraction',
            'quarry', 'resources', 'offshore', 'drilling', 'seismic'
        ],
        'title_patterns': [
            r'\bmining\b', r'\bmineral\b', r'\bpetroleum\b', r'\boffshore\b',
            r'\bresources\b', r'\bcoal\b', r'\buranium\b'
        ]
    },
    'C': {
        'name': 'Manufacturing',
        'keywords': [
            'manufacturing', 'factory', 'industrial', 'processing',
            'automotive', 'chemical', 'textile', 'machinery', 'equipment'
        ],
        'title_patterns': [
            r'\bmanufactur', r'\bindustrial\b', r'\bfactory\b'
        ]
    },
    'P': {
        'name': 'Education and Training',
        'keywords': [
            'education', 'school', 'university', 'training', 'student',
            'teacher', 'academic', 'higher education', 'tertiary',
            'vocational', 'TAFE', 'qualification', 'curriculum'
        ],
        'title_patterns': [
            r'\beducation\b', r'\bschool\b', r'\buniversity\b', r'\btraining\b',
            r'\btertiary\b', r'\bvocational\b'
        ]
    },
    'E': {
        'name': 'Construction',
        'keywords': [
            'construction', 'building', 'infrastructure', 'contractor',
            'architect', 'builder', 'project', 'site', 'development'
        ],
        'title_patterns': [
            r'\bconstruction\b', r'\bbuilding\b', r'\binfrastructure\b'
        ]
    },
    'R': {
        'name': 'Arts and Recreation Services',
        'keywords': [
            'arts', 'culture', 'recreation', 'sport', 'entertainment',
            'museum', 'library', 'heritage', 'creative', 'gambling',
            'gaming', 'lottery', 'national park', 'environment'
        ],
        'title_patterns': [
            r'\barts\b', r'\bculture\b', r'\bsport\b', r'\bgambling\b',
            r'\bheritage\b', r'\benvironment\b', r'\bnational park\b'
        ]
    },
    'F': {
        'name': 'Wholesale Trade',
        'keywords': [
            'wholesale', 'import', 'export', 'customs', 'tariff',
            'trade', 'dealer', 'distributor'
        ],
        'title_patterns': [
            r'\bwholesale\b', r'\bimport\b', r'\bexport\b', r'\btariff\b'
        ]
    },
    'G': {
        'name': 'Retail Trade',
        'keywords': [
            'retail', 'shop', 'store', 'consumer', 'merchandise'
        ],
        'title_patterns': [
            r'\bretail\b', r'\bconsumer\b'
        ]
    },
    'H': {
        'name': 'Accommodation and Food Services',
        'keywords': [
            'hotel', 'accommodation', 'tourism', 'restaurant', 'food service',
            'hospitality', 'catering', 'tourist', 'visitor'
        ],
        'title_patterns': [
            r'\baccommodation\b', r'\btourism\b', r'\bhospitality\b'
        ]
    },
    'L': {
        'name': 'Rental, Hiring and Real Estate Services',
        'keywords': [
            'rental', 'lease', 'property', 'real estate', 'land', 'housing',
            'tenancy', 'landlord', 'native title'
        ],
        'title_patterns': [
            r'\brental\b', r'\bproperty\b', r'\breal estate\b', r'\bland\b',
            r'\bnative title\b'
        ]
    },
    'M': {
        'name': 'Professional, Scientific and Technical Services',
        'keywords': [
            'professional', 'consulting', 'technical', 'scientific',
            'research', 'legal', 'accounting', 'veterinary', 'design'
        ],
        'title_patterns': [
            r'\bprofessional\b', r'\bscientific\b', r'\bresearch\b'
        ]
    },
    'N': {
        'name': 'Administrative and Support Services',
        'keywords': [
            'administrative', 'support services', 'staffing', 'recruitment',
            'office', 'security services', 'cleaning', 'maintenance'
        ],
        'title_patterns': [
            r'\badministrative\b', r'\bsupport services\b'
        ]
    },
    'S': {
        'name': 'Other Services',
        'keywords': [
            'repair', 'personal', 'community', 'religious', 'civic',
            'union', 'association', 'organisation'
        ],
        'title_patterns': [
            r'\brepair\b', r'\bcommunity\b', r'\bassociation\b'
        ]
    },
}

# Cross-cutting legislation indicators (should still try to find primary industry)
CROSS_CUTTING_KEYWORDS = [
    'corporations', 'competition', 'consumer', 'workplace', 'employment',
    'fair work', 'privacy', 'taxation', 'GST', 'income tax'
]


class PrimaryIndustryClassifier:
    """Classifies legislation to its PRIMARY ANZSIC industry."""

    def __init__(self):
        # Pre-compile regex patterns
        self.division_patterns = {}
        for code, div in ANZSIC_DIVISIONS.items():
            keyword_pattern = r'\b(' + '|'.join(re.escape(kw) for kw in div['keywords']) + r')\b'
            title_patterns = [re.compile(p, re.IGNORECASE) for p in div.get('title_patterns', [])]
            self.division_patterns[code] = {
                'keyword_pattern': re.compile(keyword_pattern, re.IGNORECASE),
                'title_patterns': title_patterns,
                'name': div['name']
            }

        self.cross_cutting_pattern = re.compile(
            r'\b(' + '|'.join(re.escape(kw) for kw in CROSS_CUTTING_KEYWORDS) + r')\b',
            re.IGNORECASE
        )

    def classify_primary_industry(self, doc: Dict) -> Dict:
        """
        Classify a document to its PRIMARY industry.

        Returns dict with:
        - primary_industry_code: single letter code (A-S) or 'X' for cross-cutting
        - primary_industry_name: full name
        - confidence: 'high', 'medium', 'low'
        - matched_keywords: list of matched keywords
        """
        title = doc.get('title', '')
        text = doc.get('text', '')[:5000]  # First 5000 chars

        # Score each industry
        scores = {}
        matches = {}

        for code, patterns in self.division_patterns.items():
            score = 0
            matched = []

            # Check title first (higher weight)
            for tp in patterns['title_patterns']:
                title_matches = tp.findall(title)
                if title_matches:
                    score += len(title_matches) * 10  # Title matches worth 10x
                    matched.extend(title_matches)

            # Check text keywords
            keyword_matches = patterns['keyword_pattern'].findall(title + ' ' + text)
            if keyword_matches:
                score += len(keyword_matches)
                matched.extend(keyword_matches)

            if score > 0:
                scores[code] = score
                matches[code] = list(set(matched))

        # Find primary industry (highest score)
        if scores:
            primary_code = max(scores, key=scores.get)
            max_score = scores[primary_code]

            # Determine confidence
            other_scores = [s for c, s in scores.items() if c != primary_code]
            if not other_scores or max_score >= 2 * max(other_scores + [1]):
                confidence = 'high'
            elif max_score >= 1.5 * max(other_scores + [1]):
                confidence = 'medium'
            else:
                confidence = 'low'

            return {
                'primary_industry_code': primary_code,
                'primary_industry_name': ANZSIC_DIVISIONS[primary_code]['name'],
                'confidence': confidence,
                'matched_keywords': matches.get(primary_code, []),
                'all_scores': scores
            }

        # Check for cross-cutting
        if self.cross_cutting_pattern.search(title + ' ' + text):
            return {
                'primary_industry_code': 'X',
                'primary_industry_name': 'Cross-cutting (all industries)',
                'confidence': 'medium',
                'matched_keywords': [],
                'all_scores': {}
            }

        # Unclassified
        return {
            'primary_industry_code': 'U',
            'primary_industry_name': 'Unclassified',
            'confidence': 'low',
            'matched_keywords': [],
            'all_scores': {}
        }


def count_requirements(text: str) -> Dict:
    """Count BC and RegData requirements."""
    if not text:
        return {'bc': 0, 'regdata': 0}

    text_lower = text.lower()

    # BC: must, shall, required (excluding negations)
    bc_count = 0
    for word in ['must', 'shall', 'required']:
        pattern = re.compile(r'\b' + word + r'\b', re.IGNORECASE)
        bc_count += len(pattern.findall(text_lower))

    # Subtract negations
    negation_count = len(re.findall(r'\bmust\s+not\b', text_lower))
    negation_count += len(re.findall(r'\bshall\s+not\b', text_lower))
    bc_count = max(0, bc_count - negation_count)

    # RegData: shall, must, may not, required, prohibited
    regdata_count = 0
    for term in ['shall', 'must', 'may not', 'required', 'prohibited']:
        pattern = re.compile(r'\b' + re.escape(term) + r'\b', re.IGNORECASE)
        regdata_count += len(pattern.findall(text_lower))

    return {'bc': bc_count, 'regdata': regdata_count}


def parse_date(date_str: Optional[str]) -> Optional[date]:
    """Parse ISO date string."""
    if not date_str:
        return None
    try:
        if 'T' in date_str:
            return datetime.fromisoformat(date_str.replace('Z', '+00:00')).date()
        return datetime.strptime(date_str[:10], '%Y-%m-%d').date()
    except:
        return None


def extract_year_from_id(register_id: str) -> Optional[int]:
    """Extract year from register_id."""
    match = re.search(r'[CF](\d{4})', register_id)
    if match:
        return int(match.group(1))
    return None


def filter_in_force(docs: List[Dict], check_date: date) -> List[Dict]:
    """Filter documents to those in force at a given date."""
    in_force = []
    for doc in docs:
        # Get making year
        year = extract_year_from_id(doc.get('register_id', ''))
        if not year:
            continue

        # Simple heuristic: if year <= check_year, assume in force
        # (proper filtering would use commencement/repeal dates)
        if year <= check_date.year:
            in_force.append(doc)

    return in_force


def run_analysis(data_dir: Path, output_dir: Path, time_points: List[date]):
    """Run the primary industry analysis."""
    output_dir.mkdir(exist_ok=True)

    # Load data
    data_path = data_dir / 'scraped_legislation.json'
    logger.info(f"Loading data from {data_path}...")

    with open(data_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if isinstance(data, dict) and 'regulations' in data:
        documents = data['regulations']
    else:
        documents = data

    logger.info(f"Loaded {len(documents):,} documents")

    # Classify all documents
    classifier = PrimaryIndustryClassifier()
    classified_docs = []

    logger.info("Classifying documents by primary industry...")
    for i, doc in enumerate(documents):
        if i > 0 and i % 5000 == 0:
            logger.info(f"  Processed {i:,}...")

        classification = classifier.classify_primary_industry(doc)
        requirements = count_requirements(doc.get('text', ''))

        classified_docs.append({
            'register_id': doc.get('register_id', doc.get('id', '')),
            'title': doc.get('title', ''),
            'year': extract_year_from_id(doc.get('register_id', doc.get('id', ''))),
            'primary_industry_code': classification['primary_industry_code'],
            'primary_industry_name': classification['primary_industry_name'],
            'confidence': classification['confidence'],
            'bc_requirements': requirements['bc'],
            'regdata_restrictions': requirements['regdata'],
        })

    logger.info(f"Classified {len(classified_docs):,} documents")

    # Classification summary
    print("\n" + "=" * 70)
    print("CLASSIFICATION SUMMARY")
    print("=" * 70)

    code_counts = Counter(d['primary_industry_code'] for d in classified_docs)
    for code in sorted(code_counts.keys()):
        count = code_counts[code]
        pct = count / len(classified_docs) * 100
        name = ANZSIC_DIVISIONS.get(code, {}).get('name', 'Cross-cutting' if code == 'X' else 'Unclassified')
        print(f"{code} - {name:<45}: {count:>6,} ({pct:>5.1f}%)")

    # Time series analysis
    results = {}
    for check_date in time_points:
        logger.info(f"Analyzing {check_date}...")

        # Filter to docs in force
        in_force = [d for d in classified_docs
                   if d['year'] and d['year'] <= check_date.year]

        # Aggregate by industry
        industry_stats = defaultdict(lambda: {
            'document_count': 0,
            'bc_total': 0,
            'regdata_total': 0
        })

        for doc in in_force:
            code = doc['primary_industry_code']
            industry_stats[code]['document_count'] += 1
            industry_stats[code]['bc_total'] += doc['bc_requirements']
            industry_stats[code]['regdata_total'] += doc['regdata_restrictions']

        results[str(check_date)] = dict(industry_stats)

    # Print time series table
    print("\n" + "=" * 100)
    print("PRIMARY INDUSTRY REGULATORY RESTRICTIONS BY TIME PERIOD")
    print("=" * 100)

    # Header
    header = f"{'Industry':<45}"
    for tp in time_points:
        header += f"{tp.year:>12}"
    print(header)
    print("-" * 100)

    # Get all codes
    all_codes = set()
    for year_data in results.values():
        all_codes.update(year_data.keys())

    sorted_codes = [c for c in 'ABCDEFGHIJKLMNOPQRS' if c in all_codes]
    sorted_codes += [c for c in all_codes if c not in 'ABCDEFGHIJKLMNOPQRS']

    totals = {str(tp): 0 for tp in time_points}

    for code in sorted_codes:
        name = ANZSIC_DIVISIONS.get(code, {}).get('name', 'Cross-cutting' if code == 'X' else 'Unclassified')
        row = f"{code} - {name[:40]:<44}"
        for tp in time_points:
            count = results.get(str(tp), {}).get(code, {}).get('regdata_total', 0)
            totals[str(tp)] += count
            row += f"{count:>12,}"
        print(row)

    print("-" * 100)
    total_row = f"{'TOTAL':<45}"
    for tp in time_points:
        total_row += f"{totals[str(tp)]:>12,}"
    print(total_row)

    # Save results
    output_data = {
        'generated_at': datetime.now().isoformat(),
        'methodology': 'ANZSIC Primary Industry Classification (1-digit)',
        'total_documents': len(classified_docs),
        'time_periods': [str(tp) for tp in time_points],
        'by_time_period': results
    }

    output_path = output_dir / 'anzsic_primary_industry_analysis.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2)
    logger.info(f"Results saved to {output_path}")

    # Create chart for 2025
    create_industry_chart(results, time_points[-1], output_dir / 'anzsic_primary_2025.png')

    return results


def create_industry_chart(results: Dict, check_date: date, output_path: Path):
    """Create horizontal bar chart of restrictions by primary industry."""
    year_data = results.get(str(check_date), {})

    if not year_data:
        logger.warning("No data for chart")
        return

    # Prepare data
    chart_data = []
    for code, stats in year_data.items():
        name = ANZSIC_DIVISIONS.get(code, {}).get('name', 'Cross-cutting' if code == 'X' else 'Unclassified')
        chart_data.append((f"{code} - {name}", stats.get('regdata_total', 0)))

    # Sort by restrictions
    chart_data.sort(key=lambda x: x[1], reverse=True)

    if not chart_data:
        return

    industries = [d[0] for d in chart_data]
    restrictions = [d[1] for d in chart_data]

    # Create chart
    fig, ax = plt.subplots(figsize=(14, 12))

    bars = ax.barh(range(len(industries)), restrictions, color='#2E86AB')

    ax.set_yticks(range(len(industries)))
    ax.set_yticklabels(industries, fontsize=9)
    ax.invert_yaxis()

    ax.set_xlabel('RegData Restrictions', fontsize=12)
    ax.set_title(f'Regulatory Restrictions by Primary ANZSIC Industry ({check_date.year})',
                fontsize=14, fontweight='bold')

    # Add value labels
    for bar, val in zip(bars, restrictions):
        ax.text(val + max(restrictions) * 0.01, bar.get_y() + bar.get_height()/2,
                f'{val:,}', va='center', fontsize=9)

    plt.tight_layout()
    plt.savefig(str(output_path), dpi=150, bbox_inches='tight')
    plt.close()

    logger.info(f"Chart saved to {output_path}")


def main():
    base_dir = Path(__file__).parent
    data_dir = base_dir / 'data'
    output_dir = base_dir / 'output'

    time_points = [
        date(2010, 7, 1),
        date(2015, 7, 1),
        date(2020, 7, 1),
        date(2025, 7, 1),
    ]

    run_analysis(data_dir, output_dir, time_points)


if __name__ == "__main__":
    main()
