# Australian Federal Regulatory Burden Analysis Tool

A Python tool to measure the current stock of regulatory burden in Australian federal regulations using two methodologies:

1. **BC-style Requirements Counting** - British Columbia methodology counting binding obligation words
2. **RegData-style Restrictions Counting** - Mercatus Center/QuantGov approach

The tool scrapes legislation from [legislation.gov.au](https://www.legislation.gov.au/), analyzes regulatory text, and generates a one-page PDF report comparing both methodologies.

## Installation

```bash
# Clone or download this repository
cd regcost

# Install dependencies
pip install -r requirements.txt
```

### Dependencies

- `requests` - HTTP requests for web scraping
- `beautifulsoup4` - HTML parsing
- `lxml` - Fast XML/HTML parser
- `pdfplumber` - PDF text extraction
- `reportlab` - PDF report generation
- `matplotlib` - Chart visualization
- `numpy` - Numerical operations

## Usage

### Quick Start (Sample Data)

Test the tool with generated sample data:

```bash
python main.py --sample
```

### Full Analysis

Scrape real regulations from legislation.gov.au and analyze:

```bash
python main.py
```

### Command Line Options

```bash
python main.py [OPTIONS]

Options:
  --sample              Use generated sample data instead of scraping
  --load                Load existing data from previous scrape
  --max N               Maximum regulations to process (default: 500)
  --collection TYPE     Collection type: act, legislativeinstrument,
                        notifiableinstrument, or all (default: all)
  --validate            Run validation on sample regulations
  --report-only         Only generate report from existing results
  --output DIR          Output directory for report
```

### Examples

```bash
# Analyze 100 Acts only
python main.py --max 100 --collection act

# Generate 200 sample regulations for testing
python main.py --sample --max 200

# Regenerate report from previous analysis
python main.py --report-only

# Load existing scraped data and regenerate analysis
python main.py --load
```

## Output

After running, you'll find:

- `output/regulatory_burden_report.pdf` - One-page comparison report
- `output/analysis_results.json` - Detailed results in JSON format
- `output/comparison_chart.png` - Bar chart visualization
- `data/regulations_data.json` - Scraped regulation data
- `data/metadata/` - Individual regulation metadata files

## Methodology

### BC Method (Requirements)

Based on British Columbia's approach, counts instances of:
- "must"
- "shall"
- "required"

**Exclusions:**
- "must not" / "shall not" (prohibitions)
- "may" (discretionary)

### RegData Method (Restrictions)

Based on Mercatus Center/QuantGov methodology, counts:
- "shall"
- "must"
- "may not"
- "required"
- "prohibited"

### Expected Differences

RegData typically produces higher counts because it includes prohibitions ("may not", "prohibited"). This is by design - both metrics measure different aspects of regulatory burden:

- **BC Method**: Affirmative obligations (things you MUST do)
- **RegData Method**: All restrictions including prohibitions (things you MUST do AND things you MAY NOT do)

## Project Structure

```
regcost/
├── main.py              # Main orchestration script
├── config.py            # Configuration settings
├── scraper.py           # Data collection from legislation.gov.au
├── bc_counter.py        # BC methodology implementation
├── regdata_counter.py   # RegData methodology implementation
├── report_generator.py  # PDF report generation
├── requirements.txt     # Python dependencies
├── README.md            # This file
├── data/                # Scraped data storage
│   ├── acts/
│   ├── legislative_instruments/
│   ├── metadata/
│   └── pdfs/
├── output/              # Generated reports
└── logs/                # Log files
```

## Interpreting Results

A typical output might show:

```
BC Method (Requirements):     125,000
RegData Method (Restrictions): 140,000
Difference: RegData is +12% higher than BC
```

This difference is expected because:
1. RegData includes "may not" and "prohibited" - phrases indicating prohibitions
2. BC method focuses strictly on affirmative obligations
3. Both are valid measures of different regulatory burden aspects

## Limitations

1. **Text Extraction**: Some PDFs may not extract cleanly, affecting counts
2. **Context Sensitivity**: Simple word counting doesn't consider context (e.g., "must" in a definition vs. an actual requirement)
3. **Website Changes**: The scraper may need updates if legislation.gov.au changes its structure
4. **Scope**: Currently focuses on principal in-force regulations (not amendments or historical versions)

## Data Source

All data is sourced from the [Federal Register of Legislation](https://www.legislation.gov.au/), managed by the Office of Parliamentary Counsel under the Legislation Act 2003.

## Contributing

Contributions welcome. Areas for improvement:
- More sophisticated NLP for context-aware counting
- Industry classification using machine learning
- Historical trend analysis
- State/territory legislation support

## License

MIT License - See LICENSE file for details.

## References

- [British Columbia Regulatory Requirements Count](https://www2.gov.bc.ca/gov/content/governments/about-the-bc-government/regulatory-reform)
- [Mercatus Center RegData](https://www.mercatus.org/research/regdata)
- [QuantGov](https://www.quantgov.org/)
- [Federal Register of Legislation](https://www.legislation.gov.au/)
