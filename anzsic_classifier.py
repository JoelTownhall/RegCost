"""
ANZSIC Industry Classification for Australian Legislation.

Implements the CEDA RegCost methodology for:
1. Classifying legislation to ANZSIC industry codes using keyword matching
2. Counting regulatory restrictions (requirements and prohibitions)
3. Analyzing the regulatory burden by industry over time

Reference: CEDA RegCost.pdf methodology (Table A1, Table A2)
"""
import json
import re
import os
import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ============================================================================
# ANZSIC INDUSTRY KEYWORDS (Table A1 from CEDA RegCost methodology)
# ============================================================================

ANZSIC_KEYWORDS = {
    'A_Agriculture': [
        'agriculture', 'agricultural', 'farming', 'farm', 'crop', 'livestock',
        'cattle', 'sheep', 'dairy', 'poultry', 'pig', 'fishing', 'fisheries',
        'aquaculture', 'forestry', 'timber', 'wood', 'rural', 'primary producer',
        'horticultural', 'pastoral', 'grain', 'beef', 'wool', 'cotton', 'wheat',
        'vineyard', 'orchard', 'plantation'
    ],
    'B_Mining': [
        'mining', 'mine', 'mineral', 'minerals', 'coal', 'iron ore', 'gold',
        'copper', 'uranium', 'petroleum', 'oil', 'gas', 'exploration',
        'extraction', 'quarry', 'resources', 'geological', 'drilling',
        'seismic', 'prospect'
    ],
    'C_Manufacturing': [
        'manufacturing', 'factory', 'industrial', 'assembly', 'processing',
        'fabrication', 'automotive', 'pharmaceutical', 'chemical', 'textile',
        'food processing', 'machinery', 'equipment', 'product', 'plant', 'facility'
    ],
    'D_Electricity_Gas_Water_Waste': [
        'electricity', 'electric', 'power', 'energy', 'gas', 'water', 'waste',
        'utility', 'sewage', 'treatment', 'distribution', 'generation',
        'renewable', 'solar', 'wind', 'hydro', 'nuclear', 'transmission',
        'grid', 'pipeline'
    ],
    'E_Construction': [
        'construction', 'building', 'residential', 'commercial', 'infrastructure',
        'contractor', 'planning', 'zoning', 'architect', 'engineer', 'builder',
        'project', 'site'
    ],
    'F_Wholesale_Trade': [
        'wholesale', 'distribution', 'supply chain', 'trading', 'import',
        'export', 'dealer', 'distributor', 'supplier', 'bulk', 'inventory',
        'customs'
    ],
    'G_Retail_Trade': [
        'retail', 'shop', 'store', 'consumer', 'sales', 'merchandise',
        'customer', 'commercial', 'trade', 'market', 'shopping'
    ],
    'H_Accommodation_Food': [
        'hotel', 'accommodation', 'tourism', 'restaurant', 'food service',
        'hospitality', 'catering', 'lodging', 'tourist', 'visitor'
    ],
    'I_Transport_Postal_Warehousing': [
        'transport', 'transportation', 'freight', 'logistics', 'shipping',
        'postal', 'mail', 'delivery', 'warehouse', 'aviation', 'maritime',
        'rail', 'road', 'airport', 'port', 'cargo', 'passenger', 'navigation',
        'airlines', 'railways', 'seafarer'
    ],
    'J_Information_Media_Telecom': [
        'telecommunications', 'broadcasting', 'media', 'internet', 'communication',
        'television', 'radio', 'radiocommunications', 'digital', 'technology',
        'data', 'network', 'spectrum', 'mobile', 'telephone', 'broadband',
        'communications'
    ],
    'K_Financial_Insurance': [
        'banking', 'bank', 'banks', 'financial', 'insurance', 'credit', 'loan',
        'investment', 'fund', 'superannuation', 'pension', 'money', 'deposit',
        'prudential', 'APRA', 'ASIC', 'unclaimed money', 'ADI', 'life insurance'
    ],
    'L_Rental_Real_Estate': [
        'rental', 'lease', 'property', 'real estate', 'land', 'estate',
        'housing', 'residential', 'commercial property', 'tenancy', 'landlord'
    ],
    'M_Professional_Scientific_Technical': [
        'professional', 'consulting', 'technical', 'scientific', 'research',
        'legal', 'accounting', 'engineering', 'veterinary', 'architectural',
        'design', 'advisory', 'specialist', 'expert'
    ],
    'N_Administrative_Support': [
        'support services', 'staffing', 'recruitment', 'office', 'clerical',
        'security', 'cleaning', 'maintenance'
    ],
    'O_Public_Administration_Safety': [
        'government', 'public', 'administration', 'civil', 'defence', 'security',
        'police', 'law enforcement', 'public safety', 'emergency',
        'national security', 'intelligence', 'military', 'ADF', 'AFP', 'ASIO'
    ],
    'P_Education_Training': [
        'education', 'school', 'university', 'training', 'student', 'teacher',
        'academic', 'learning', 'curriculum', 'higher education', 'tertiary',
        'vocational', 'skills', 'qualification', 'universities'
    ],
    'Q_Health_Social_Assistance': [
        'health', 'medical', 'hospital', 'healthcare', 'patient', 'treatment',
        'pharmaceutical', 'medicine', 'therapy', 'care', 'social', 'welfare',
        'disability', 'aged care', 'mental health', 'public health'
    ],
    'R_Arts_Recreation': [
        'arts', 'culture', 'recreation', 'sport', 'entertainment', 'museum',
        'library', 'heritage', 'creative', 'performance', 'festival', 'gambling',
        'gaming', 'lottery', 'marine park', 'national park'
    ],
    'S_Other_Services': [
        'repair', 'personal', 'community', 'religious', 'civic', 'union',
        'association', 'organisation', 'service', 'maintenance'
    ],
}

# Keywords indicating legislation applies to ALL industries
ALL_INDUSTRIES_KEYWORDS = [
    'GST', 'customs', 'tariff', 'excise', 'competition', 'consumer',
    'trade practices', 'workplace', 'employment', 'fair work', 'privacy',
    'corporations', 'business', 'commercial', 'regulatory', 'compliance',
    'standards', 'quality', 'environmental protection', 'industrial relations'
]

# Keywords indicating legislation applies to NO industries (government/procedural)
NO_INDUSTRIES_KEYWORDS = [
    'electoral', 'parliament', 'referendum', 'supply act', 'appropriation',
    'judicial', 'federal circuit', 'family court', 'procedural',
    'administrative law', 'income tax', 'interpretation'
]

# ============================================================================
# RESTRICTION KEYWORDS (Table A2 from CEDA RegCost methodology)
# ============================================================================

REQUIREMENT_TERMS = [
    'must', 'shall', 'required', 'mandatory', 'obliged', 'compulsory',
    'necessary', 'duty', 'obligation', 'liable', 'responsible'
]

PROHIBITION_TERMS = [
    'prohibited', 'forbidden', 'banned', 'unlawful', 'illegal',
    'shall not', 'must not', 'cannot', 'may not', 'restricted'
]


class ANZSICClassifier:
    """
    Classifies Australian legislation to ANZSIC industry codes using the
    CEDA RegCost methodology.
    """

    def __init__(self):
        # Pre-compile regex patterns for efficiency
        self.industry_patterns = {}
        for industry, keywords in ANZSIC_KEYWORDS.items():
            # Create pattern that matches any of the keywords as whole words
            pattern = r'\b(' + '|'.join(re.escape(kw) for kw in keywords) + r')\b'
            self.industry_patterns[industry] = re.compile(pattern, re.IGNORECASE)

        # Patterns for all-industries and no-industries
        self.all_industries_pattern = re.compile(
            r'\b(' + '|'.join(re.escape(kw) for kw in ALL_INDUSTRIES_KEYWORDS) + r')\b',
            re.IGNORECASE
        )
        self.no_industries_pattern = re.compile(
            r'\b(' + '|'.join(re.escape(kw) for kw in NO_INDUSTRIES_KEYWORDS) + r')\b',
            re.IGNORECASE
        )

        # Compile restriction patterns
        # Handle multi-word patterns first
        self.requirement_patterns = []
        self.prohibition_patterns = []

        for term in REQUIREMENT_TERMS:
            pattern = re.compile(r'\b' + re.escape(term) + r'\b', re.IGNORECASE)
            self.requirement_patterns.append((term, pattern))

        for term in PROHIBITION_TERMS:
            pattern = re.compile(r'\b' + re.escape(term) + r'\b', re.IGNORECASE)
            self.prohibition_patterns.append((term, pattern))

    def extract_year_from_register_id(self, register_id: str) -> Optional[int]:
        """
        Extract the making year from register_id.
        Format: C2007A00039 -> 2007
        """
        match = re.search(r'C(\d{4})A', register_id)
        if match:
            return int(match.group(1))
        return None

    def get_classification_text(self, doc: dict) -> Tuple[str, str]:
        """
        Get the text to use for classification.
        Priority: title first, then purpose/first ~2000 chars of text.

        Returns: (title, first_portion_of_text)
        """
        title = doc.get('title', '')
        text = doc.get('text', '')

        # Get first ~2000 chars for purpose/first sections
        first_portion = text[:2000] if text else ''

        return title, first_portion

    def classify_industry(self, doc: dict) -> dict:
        """
        Classify a document to one or more ANZSIC industries.

        Returns dict with:
        - industries: list of matched industries
        - classification_type: 'single', 'multiple', 'all', 'none', or 'unclassified'
        - matched_keywords: dict of industry -> list of matched keywords
        """
        title, first_portion = self.get_classification_text(doc)

        # Combine title and first portion for matching
        combined_text = f"{title} {first_portion}"

        result = {
            'industries': [],
            'classification_type': 'unclassified',
            'matched_keywords': {},
            'title_matches': {},
            'text_matches': {}
        }

        # First check for no-industries keywords
        no_match = self.no_industries_pattern.search(combined_text)
        if no_match:
            result['classification_type'] = 'none'
            result['no_industry_keyword'] = no_match.group()
            return result

        # Check for all-industries keywords
        all_match = self.all_industries_pattern.search(combined_text)
        if all_match:
            result['classification_type'] = 'all'
            result['all_industry_keyword'] = all_match.group()
            result['industries'] = list(ANZSIC_KEYWORDS.keys())
            return result

        # Check each industry's keywords
        # Priority: title first, then text
        for industry, pattern in self.industry_patterns.items():
            # Check title first
            title_matches = pattern.findall(title)
            if title_matches:
                result['industries'].append(industry)
                result['matched_keywords'][industry] = title_matches
                result['title_matches'][industry] = title_matches
                continue

            # Then check first portion of text
            text_matches = pattern.findall(first_portion)
            if text_matches:
                result['industries'].append(industry)
                result['matched_keywords'][industry] = text_matches
                result['text_matches'][industry] = text_matches

        # Set classification type
        if len(result['industries']) == 0:
            result['classification_type'] = 'unclassified'
        elif len(result['industries']) == 1:
            result['classification_type'] = 'single'
        else:
            result['classification_type'] = 'multiple'

        return result

    def count_restrictions(self, text: str) -> dict:
        """
        Count restriction terms in the full text.

        Returns dict with:
        - requirements: count of requirement terms
        - prohibitions: count of prohibition terms
        - total: total restrictions
        - by_term: breakdown by individual term
        """
        if not text:
            return {
                'requirements': 0,
                'prohibitions': 0,
                'total': 0,
                'by_term': {}
            }

        # Normalize text
        normalized = text.lower()
        normalized = re.sub(r'\s+', ' ', normalized)

        by_term = {}
        total_requirements = 0
        total_prohibitions = 0

        # Count prohibitions first (to handle "shall not", "must not")
        # We'll mask these before counting requirements
        masked_text = normalized

        for term, pattern in self.prohibition_patterns:
            matches = pattern.findall(masked_text)
            count = len(matches)
            by_term[term] = count
            total_prohibitions += count
            # Mask multi-word prohibitions to avoid double counting
            if ' ' in term:
                masked_text = pattern.sub('__PROHIBITION__', masked_text)

        # Count requirements in masked text
        for term, pattern in self.requirement_patterns:
            matches = pattern.findall(masked_text)
            count = len(matches)
            by_term[term] = count
            total_requirements += count

        return {
            'requirements': total_requirements,
            'prohibitions': total_prohibitions,
            'total': total_requirements + total_prohibitions,
            'by_term': by_term
        }

    def analyze_document(self, doc: dict) -> dict:
        """
        Analyze a single document for industry classification and restrictions.
        """
        register_id = doc.get('register_id', doc.get('id', 'Unknown'))
        year = self.extract_year_from_register_id(register_id)

        # Classify to industries
        classification = self.classify_industry(doc)

        # Count restrictions
        full_text = doc.get('text', '')
        restrictions = self.count_restrictions(full_text)

        return {
            'register_id': register_id,
            'title': doc.get('title', 'Unknown'),
            'collection': doc.get('collection', 'Unknown'),
            'year': year,
            'industries': classification['industries'],
            'classification_type': classification['classification_type'],
            'matched_keywords': classification['matched_keywords'],
            'restrictions': restrictions,
            'text_length': len(full_text)
        }


def filter_by_date(documents: List[dict], cutoff_date: datetime) -> List[dict]:
    """
    Filter documents to include only those made on or before the cutoff date.
    Using July 1 of each year as the cutoff (as of July 1).
    """
    filtered = []
    cutoff_year = cutoff_date.year
    cutoff_month = cutoff_date.month
    cutoff_day = cutoff_date.day

    for doc in documents:
        year = doc.get('year')
        if year is None:
            continue

        # Simple approximation: include if year < cutoff_year
        # or if year == cutoff_year and we're using July 1 (month 7)
        if year < cutoff_year:
            filtered.append(doc)
        elif year == cutoff_year and cutoff_month >= 7:
            # Include legislation from same year if cutoff is after July
            filtered.append(doc)

    return filtered


def aggregate_by_industry(analyzed_docs: List[dict], time_periods: List[int]) -> dict:
    """
    Aggregate restriction counts by industry for each time period.

    Returns dict with structure:
    {
        year: {
            industry: {
                'total_restrictions': int,
                'requirements': int,
                'prohibitions': int,
                'document_count': int,
                'documents': [...]
            }
        }
    }
    """
    results = {}

    for year in time_periods:
        cutoff = datetime(year, 7, 1)  # July 1 of each year
        filtered = filter_by_date(analyzed_docs, cutoff)

        industry_stats = defaultdict(lambda: {
            'total_restrictions': 0,
            'requirements': 0,
            'prohibitions': 0,
            'document_count': 0,
            'documents': []
        })

        for doc in filtered:
            industries = doc.get('industries', [])
            classification_type = doc.get('classification_type', 'unclassified')
            restrictions = doc.get('restrictions', {})

            # For "all" industries, distribute to all
            if classification_type == 'all':
                industries = list(ANZSIC_KEYWORDS.keys())

            # For unclassified or none, put in a special category
            if not industries:
                industries = ['_Unclassified']

            for industry in industries:
                industry_stats[industry]['total_restrictions'] += restrictions.get('total', 0)
                industry_stats[industry]['requirements'] += restrictions.get('requirements', 0)
                industry_stats[industry]['prohibitions'] += restrictions.get('prohibitions', 0)
                industry_stats[industry]['document_count'] += 1
                # Store document summary (limit to save memory)
                if len(industry_stats[industry]['documents']) < 100:
                    industry_stats[industry]['documents'].append({
                        'register_id': doc['register_id'],
                        'title': doc['title'],
                        'restrictions': restrictions.get('total', 0)
                    })

        results[year] = dict(industry_stats)

    return results


def generate_summary_table(aggregated_results: dict, time_periods: List[int]) -> str:
    """Generate a formatted summary table."""
    lines = []
    lines.append("\n" + "=" * 100)
    lines.append("ANZSIC INDUSTRY CLASSIFICATION - REGULATORY RESTRICTIONS SUMMARY")
    lines.append("=" * 100)

    # Header
    header = f"{'Industry':<45}"
    for year in time_periods:
        header += f"{year:>12}"
    lines.append(header)
    lines.append("-" * 100)

    # Get all industries (sorted)
    all_industries = set()
    for year_data in aggregated_results.values():
        all_industries.update(year_data.keys())

    # Sort with _Unclassified at the end
    sorted_industries = sorted([i for i in all_industries if not i.startswith('_')])
    sorted_industries += sorted([i for i in all_industries if i.startswith('_')])

    # Totals row data
    totals = {year: 0 for year in time_periods}

    for industry in sorted_industries:
        # Format industry name (remove prefix letter)
        display_name = industry.replace('_', ' ')
        if display_name.startswith('A ') or display_name.startswith('B '):
            display_name = display_name[2:]

        row = f"{display_name:<45}"
        for year in time_periods:
            count = aggregated_results.get(year, {}).get(industry, {}).get('total_restrictions', 0)
            totals[year] += count
            row += f"{count:>12,}"
        lines.append(row)

    # Totals row
    lines.append("-" * 100)
    total_row = f"{'TOTAL':<45}"
    for year in time_periods:
        total_row += f"{totals[year]:>12,}"
    lines.append(total_row)
    lines.append("=" * 100)

    return "\n".join(lines)


def generate_classification_summary(analyzed_docs: List[dict]) -> str:
    """Generate a summary of classification results."""
    lines = []
    lines.append("\n" + "=" * 60)
    lines.append("CLASSIFICATION SUMMARY")
    lines.append("=" * 60)

    total = len(analyzed_docs)
    classification_counts = defaultdict(int)

    for doc in analyzed_docs:
        classification_counts[doc['classification_type']] += 1

    lines.append(f"Total documents analyzed: {total:,}")
    lines.append("-" * 60)

    for ctype, count in sorted(classification_counts.items()):
        pct = (count / total * 100) if total > 0 else 0
        lines.append(f"{ctype:<20}: {count:>8,} ({pct:>5.1f}%)")

    lines.append("=" * 60)

    return "\n".join(lines)


def create_bar_chart(aggregated_results: dict, year: int, output_path: str):
    """Create a bar chart showing restrictions by industry for a specific year."""
    try:
        import matplotlib.pyplot as plt
        import matplotlib
        matplotlib.use('Agg')  # Use non-interactive backend
    except ImportError:
        logger.warning("matplotlib not available, skipping chart generation")
        return

    year_data = aggregated_results.get(year, {})

    # Filter out _Unclassified for the chart and sort by restriction count
    industry_data = [(k, v['total_restrictions'])
                     for k, v in year_data.items()
                     if not k.startswith('_')]
    industry_data.sort(key=lambda x: x[1], reverse=True)

    if not industry_data:
        logger.warning(f"No industry data for year {year}")
        return

    # Create figure
    fig, ax = plt.subplots(figsize=(14, 10))

    industries = [item[0].replace('_', ' ')[2:] if item[0][1] == '_' else item[0].replace('_', ' ')
                  for item in industry_data]
    restrictions = [item[1] for item in industry_data]

    # Create horizontal bar chart
    bars = ax.barh(range(len(industries)), restrictions, color='#2E86AB')

    ax.set_yticks(range(len(industries)))
    ax.set_yticklabels(industries)
    ax.invert_yaxis()  # Largest at top

    ax.set_xlabel('Total Regulatory Restrictions', fontsize=12)
    ax.set_title(f'Regulatory Restrictions by ANZSIC Industry ({year})', fontsize=14, fontweight='bold')

    # Add value labels
    for i, (bar, val) in enumerate(zip(bars, restrictions)):
        ax.text(val + max(restrictions) * 0.01, bar.get_y() + bar.get_height()/2,
                f'{val:,}', va='center', fontsize=9)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

    logger.info(f"Chart saved to {output_path}")


def main():
    """Main execution function."""
    # Paths
    base_dir = Path(__file__).parent
    data_path = base_dir / "data" / "scraped_legislation.json"
    output_dir = base_dir / "output"
    output_dir.mkdir(exist_ok=True)

    json_output_path = output_dir / "anzsic_industry_analysis.json"
    chart_output_path = output_dir / "anzsic_industry_restrictions_2025.png"

    # Time periods to analyze
    time_periods = [2010, 2015, 2020, 2025]

    logger.info("Loading legislation data...")

    # Load data
    with open(data_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Handle different data structures
    if isinstance(data, dict) and 'regulations' in data:
        documents = data['regulations']
    elif isinstance(data, list):
        documents = data
    else:
        raise ValueError("Unexpected data format in scraped_legislation.json")

    logger.info(f"Loaded {len(documents):,} documents")

    # Initialize classifier
    classifier = ANZSICClassifier()

    # Analyze all documents
    logger.info("Analyzing documents...")
    analyzed_docs = []

    for i, doc in enumerate(documents):
        if i > 0 and i % 5000 == 0:
            logger.info(f"Processed {i:,} documents...")

        try:
            analysis = classifier.analyze_document(doc)
            analyzed_docs.append(analysis)
        except Exception as e:
            logger.error(f"Error analyzing document {doc.get('register_id', 'unknown')}: {e}")

    logger.info(f"Analyzed {len(analyzed_docs):,} documents")

    # Print classification summary
    print(generate_classification_summary(analyzed_docs))

    # Aggregate by industry and time period
    logger.info("Aggregating results by industry and time period...")
    aggregated = aggregate_by_industry(analyzed_docs, time_periods)

    # Print summary table
    print(generate_summary_table(aggregated, time_periods))

    # Save JSON output
    logger.info(f"Saving JSON output to {json_output_path}...")

    # Prepare output data (convert for JSON serialization)
    output_data = {
        'generated_at': datetime.now().isoformat(),
        'total_documents': len(analyzed_docs),
        'time_periods': time_periods,
        'methodology': 'CEDA RegCost - ANZSIC Industry Classification',
        'by_time_period': {}
    }

    for year in time_periods:
        year_summary = {}
        for industry, stats in aggregated.get(year, {}).items():
            year_summary[industry] = {
                'total_restrictions': stats['total_restrictions'],
                'requirements': stats['requirements'],
                'prohibitions': stats['prohibitions'],
                'document_count': stats['document_count']
            }
        output_data['by_time_period'][str(year)] = year_summary

    with open(json_output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2)

    logger.info(f"JSON output saved to {json_output_path}")

    # Generate bar chart for 2025
    logger.info("Generating bar chart...")
    create_bar_chart(aggregated, 2025, str(chart_output_path))

    logger.info("Analysis complete!")

    # Return results for testing
    return {
        'analyzed_docs': len(analyzed_docs),
        'aggregated': aggregated,
        'output_data': output_data
    }


if __name__ == "__main__":
    main()
