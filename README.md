# RegCost: Australian Federal Regulatory Burden Analysis

A Python toolkit to measure and visualise the regulatory burden in Australian federal regulations using two methodologies:

1. **BC-style Requirements Counting** - British Columbia methodology counting binding obligation words
2. **RegData-style Restrictions Counting** - Mercatus Center/QuantGov approach

The tool scrapes legislation from [legislation.gov.au](https://www.legislation.gov.au/), analyzes regulatory text, and provides both a PDF report and an interactive Streamlit web application.

## Web Application

The RegCost Streamlit app provides three interactive visualisations:

1. **Growth in Legislation and Requirements** - Shows cumulative legislation counts and requirement totals over time
2. **Industry Impacts** - Displays how regulatory requirements are distributed across ANZSIC industry divisions
3. **Regulation vs Economic Performance** - Compares regulatory growth against economic indicators (GVA, employment, productivity)

### Running the Web App

```bash
# Install dependencies
pip install -r requirements.txt

# Run the Streamlit app
streamlit run app.py
```

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
- `streamlit` - Interactive web application
- `plotly` - Interactive charts
- `pandas` - Data processing

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
- `output/webapp_data_base.csv` - Legislation data for web app
- `output/webapp_data_timeseries.csv` - Time series data for web app
- `output/economic_indicators.csv` - ABS economic indicators
- `data/regulations_data.json` - Scraped regulation data
- `data/metadata/` - Individual regulation metadata files

## Project Structure

```
regcost/
├── app.py                          # Streamlit web application
├── main.py                         # Main orchestration script
├── config.py                       # Configuration settings
├── scraper.py                      # Data collection from legislation.gov.au
├── bc_counter.py                   # BC methodology implementation
├── regdata_counter.py              # RegData methodology implementation
├── report_generator.py             # PDF report generation
├── requirements.txt                # Python dependencies
├── README.md                       # This file
├── .streamlit/
│   └── config.toml                 # Streamlit theme
├── charts/                         # Web app chart modules
│   ├── chart_legislation_growth.py
│   ├── chart_industry_impacts.py
│   └── chart_regulation_vs_economy.py
├── config/                         # Web app configuration
│   ├── colours.py
│   ├── annotations.py
│   └── anzsic.py
├── data/                           # Data modules and scraped data
│   ├── fetch_legislation.py
│   ├── fetch_abs.py
│   ├── industry_mapping.py
│   └── process.py
├── output/                         # Generated reports and data
├── utils/
│   └── helpers.py
└── logs/                           # Log files
```

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

## Data Sources

- **Federal Register of Legislation** (legislation.gov.au) - Acts, Legislative Instruments, Notifiable Instruments
- **Australian Bureau of Statistics** - Economic indicators (GVA, employment, productivity by industry)

## Limitations

1. **Text Extraction**: Some PDFs may not extract cleanly, affecting counts
2. **Context Sensitivity**: Simple word counting doesn't consider context
3. **Repeal Data**: Repeal data is not currently incorporated; counts show gross cumulative totals
4. **Industry Classification**: Approximate, based on administering department and keyword matching
5. **Scope**: Currently focuses on principal in-force regulations (not amendments or historical versions)

## Deployment

The Streamlit app can be deployed to Streamlit Community Cloud:

1. Push the repository to GitHub
2. Connect to Streamlit Community Cloud
3. Set main file path to `app.py`

## License

MIT License - See LICENSE file for details.

## References

- [British Columbia Regulatory Requirements Count](https://www2.gov.bc.ca/gov/content/governments/about-the-bc-government/regulatory-reform)
- [Mercatus Center RegData](https://www.mercatus.org/research/regdata)
- [QuantGov](https://www.quantgov.org/)
- [Federal Register of Legislation](https://www.legislation.gov.au/)
