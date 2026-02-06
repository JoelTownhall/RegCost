#!/usr/bin/env python3
"""
Australian Federal Regulatory Burden Analysis Tool

Measures the current stock of regulatory burden in Australian federal regulations
using two methodologies:
1. BC-style Requirements Counting - counts binding obligation words
2. RegData-style Restrictions Counting - uses QuantGov/Mercatus approach

Outputs a one-page PDF report comparing both methodologies.

Usage:
    python main.py                     # Run full analysis with scraping
    python main.py --sample            # Run with sample data (for testing)
    python main.py --load              # Load existing data and regenerate report
    python main.py --max 100           # Limit to 100 regulations
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

import config
from scraper import LegislationScraper, generate_sample_data
from bc_counter import BCRequirementsCounter
from regdata_counter import RegDataRestrictionsCounter
from report_generator import ReportGenerator

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(config.LOGS_DIR / 'analysis.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def run_analysis(regulations: list) -> tuple:
    """
    Run both BC and RegData analyses on the regulations.

    Args:
        regulations: List of regulation dicts with 'text' field

    Returns:
        tuple of (bc_results, regdata_results)
    """
    logger.info(f"Running analysis on {len(regulations)} regulations...")

    # BC Analysis
    logger.info("Running BC-style requirements counting...")
    bc_counter = BCRequirementsCounter()
    bc_results = bc_counter.analyze_regulations(regulations)
    logger.info(f"BC Method: {bc_results['total_requirements']:,} requirements found")

    # RegData Analysis
    logger.info("Running RegData-style restrictions counting...")
    regdata_counter = RegDataRestrictionsCounter()
    regdata_results = regdata_counter.analyze_regulations(regulations)
    logger.info(f"RegData Method: {regdata_results['total_restrictions']:,} restrictions found")

    return bc_results, regdata_results


def validate_counts(regulations: list, bc_results: dict, regdata_results: dict, num_samples: int = 3):
    """
    Manually validate counts on a few sample regulations.

    Args:
        regulations: List of regulations
        bc_results: BC analysis results
        regdata_results: RegData analysis results
        num_samples: Number of samples to validate
    """
    logger.info(f"\nValidating counts on {num_samples} sample regulations...")

    bc_counter = BCRequirementsCounter()
    regdata_counter = RegDataRestrictionsCounter()

    for i, reg in enumerate(regulations[:num_samples]):
        title = reg.get('title', 'Unknown')[:50]
        text = reg.get('text', '')

        bc_count = bc_counter.count_requirements(text)
        rd_count = regdata_counter.count_restrictions(text)

        print(f"\n--- Sample {i+1}: {title}... ---")
        print(f"Text length: {len(text):,} characters")
        print(f"BC Requirements: {bc_count['total']}")
        print(f"  - must: {bc_count['by_word'].get('must', 0)}")
        print(f"  - shall: {bc_count['by_word'].get('shall', 0)}")
        print(f"  - required: {bc_count['by_word'].get('required', 0)}")
        print(f"RegData Restrictions: {rd_count['total']}")
        print(f"  - must: {rd_count['by_word'].get('must', 0)}")
        print(f"  - shall: {rd_count['by_word'].get('shall', 0)}")
        print(f"  - required: {rd_count['by_word'].get('required', 0)}")
        print(f"  - may not: {rd_count['by_word'].get('may not', 0)}")
        print(f"  - prohibited: {rd_count['by_word'].get('prohibited', 0)}")


def save_results(bc_results: dict, regdata_results: dict, metadata: dict):
    """Save analysis results to JSON file."""
    results = {
        'analysis_date': datetime.now().isoformat(),
        'metadata': metadata,
        'bc_results': {
            'total_requirements': bc_results['total_requirements'],
            'total_regulations': bc_results['total_regulations'],
            'regulations_analyzed': bc_results['regulations_analyzed'],
            'by_department': bc_results['by_department'],
            'by_word': bc_results['by_word'],
            'top_regulations': bc_results['top_regulations'],
        },
        'regdata_results': {
            'total_restrictions': regdata_results['total_restrictions'],
            'total_regulations': regdata_results['total_regulations'],
            'regulations_analyzed': regdata_results['regulations_analyzed'],
            'by_department': regdata_results['by_department'],
            'by_word': regdata_results['by_word'],
            'top_regulations': regdata_results['top_regulations'],
        }
    }

    results_path = config.OUTPUT_DIR / 'analysis_results.json'
    with open(results_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)

    logger.info(f"Saved results to {results_path}")
    return results_path


def main():
    parser = argparse.ArgumentParser(
        description='Australian Federal Regulatory Burden Analysis Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python main.py                          # Full analysis (scrape + analyze + report)
    python main.py --sample                 # Use sample data for testing
    python main.py --sample --max 200       # Generate 200 sample regulations
    python main.py --load                   # Load existing data, regenerate report
    python main.py --max 50 --collection act  # Analyze 50 Acts only
    python main.py --validate               # Validate counts on sample regulations
        """
    )

    parser.add_argument('--sample', action='store_true',
                       help='Use generated sample data instead of scraping')
    parser.add_argument('--load', action='store_true',
                       help='Load existing data from previous scrape')
    parser.add_argument('--max', type=int, default=config.MAX_REGULATIONS,
                       help=f'Maximum regulations to process (default: {config.MAX_REGULATIONS})')
    parser.add_argument('--collection', choices=['act', 'legislativeinstrument', 'notifiableinstrument', 'all'],
                       default='all', help='Collection type to scrape')
    parser.add_argument('--validate', action='store_true',
                       help='Run validation on sample regulations')
    parser.add_argument('--report-only', action='store_true',
                       help='Only generate report from existing results')
    parser.add_argument('--output', type=str, default=None,
                       help='Output directory for report')

    args = parser.parse_args()

    print("=" * 60)
    print("Australian Federal Regulatory Burden Analysis")
    print("=" * 60)
    print()

    # Determine output path
    output_dir = Path(args.output) if args.output else config.OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    # Check for report-only mode
    if args.report_only:
        results_path = config.OUTPUT_DIR / 'analysis_results.json'
        if not results_path.exists():
            logger.error("No existing results found. Run analysis first.")
            sys.exit(1)

        with open(results_path, encoding='utf-8') as f:
            results = json.load(f)

        bc_results = results['bc_results']
        regdata_results = results['regdata_results']
        metadata = results['metadata']

        logger.info("Generating report from existing results...")
        report_gen = ReportGenerator(output_dir)
        report_path = report_gen.generate_report(bc_results, regdata_results, metadata)
        print(f"\nReport generated: {report_path}")
        return

    # Get regulations data
    regulations = []
    is_sample = False

    if args.sample:
        # Generate sample data
        logger.info(f"Generating {args.max} sample regulations...")
        regulations = generate_sample_data(args.max)
        is_sample = True

    elif args.load:
        # Load existing data
        logger.info("Loading existing regulation data...")
        scraper = LegislationScraper()

        # Try loading from combined file first
        regulations = scraper.load_data()

        # If empty, try loading from metadata files
        if not regulations:
            regulations = scraper.load_from_metadata()

        if not regulations:
            logger.error("No existing data found. Run scraping first or use --sample.")
            sys.exit(1)

    else:
        # Scrape new data
        logger.info("Starting data collection from legislation.gov.au...")
        scraper = LegislationScraper()

        collections = None if args.collection == 'all' else [args.collection]

        try:
            regulations = scraper.scrape_regulations(
                max_items=args.max,
                collections=collections
            )
        except KeyboardInterrupt:
            logger.info("Scraping interrupted by user")
            regulations = scraper.load_from_metadata()

        if regulations:
            scraper.save_data(regulations)
        else:
            logger.warning("No regulations scraped. Falling back to sample data...")
            regulations = generate_sample_data(args.max)
            is_sample = True
            scraper.save_data(regulations)

    if not regulations:
        logger.error("No regulations to analyze")
        sys.exit(1)

    logger.info(f"Total regulations to analyze: {len(regulations)}")

    # Run analysis
    bc_results, regdata_results = run_analysis(regulations)

    # Build metadata
    metadata = {
        'data_source': 'legislation.gov.au',
        'scope': f"Federal regulations - {'Sample Data' if is_sample else 'In Force'}",
        'is_sample': is_sample,
        'max_items': args.max,
        'collection': args.collection,
        'analysis_date': datetime.now().isoformat(),
    }

    # Validate if requested
    if args.validate:
        validate_counts(regulations, bc_results, regdata_results)

    # Save results
    save_results(bc_results, regdata_results, metadata)

    # Generate report
    logger.info("Generating PDF report...")
    report_gen = ReportGenerator(output_dir)
    report_path = report_gen.generate_report(bc_results, regdata_results, metadata)

    # Print summary
    print("\n" + "=" * 60)
    print("ANALYSIS COMPLETE")
    print("=" * 60)
    print(f"\nRegulations Analyzed: {bc_results['regulations_analyzed']:,}")
    print(f"\nBC Method (Requirements):")
    print(f"  Total: {bc_results['total_requirements']:,}")
    print(f"  Breakdown: must={bc_results['by_word'].get('must', 0):,}, "
          f"shall={bc_results['by_word'].get('shall', 0):,}, "
          f"required={bc_results['by_word'].get('required', 0):,}")

    print(f"\nRegData Method (Restrictions):")
    print(f"  Total: {regdata_results['total_restrictions']:,}")
    print(f"  Breakdown: must={regdata_results['by_word'].get('must', 0):,}, "
          f"shall={regdata_results['by_word'].get('shall', 0):,}, "
          f"required={regdata_results['by_word'].get('required', 0):,}, "
          f"may not={regdata_results['by_word'].get('may not', 0):,}, "
          f"prohibited={regdata_results['by_word'].get('prohibited', 0):,}")

    # Calculate difference
    bc_total = bc_results['total_requirements']
    rd_total = regdata_results['total_restrictions']
    if bc_total > 0:
        pct_diff = ((rd_total - bc_total) / bc_total) * 100
        print(f"\nDifference: RegData is {pct_diff:+.1f}% {'higher' if pct_diff > 0 else 'lower'} than BC")

    print(f"\nReport saved to: {report_path}")
    print(f"Results saved to: {config.OUTPUT_DIR / 'analysis_results.json'}")

    if is_sample:
        print("\nNote: Analysis used SAMPLE DATA for testing purposes.")
        print("Run without --sample flag to analyze real legislation.")


if __name__ == "__main__":
    main()
