# RegCost Web Application — Claude Code Build Prompt

## Project Overview

Build a deployable Streamlit web application called **RegCost** that visualises the growth and economic impact of Australian federal regulation. The app should be clean, accessible, and focused on three interactive Plotly charts. It must be deployable to Streamlit Community Cloud directly from a GitHub repository.

The project already has a data pipeline that:
- Scrapes legislation from legislation.gov.au (Acts, Legislative Instruments, Notifiable Instruments)
- Counts regulatory requirements using two methodologies:
  - **BC method**: counts "must", "shall", "required" (excluding "must not", "shall not")
  - **RegData method**: counts "shall", "must", "may not", "required", "prohibited"
- Stores metadata including legislation title, type, year of registration, and administering department

Your job is to build the **webapp layer** on top of this existing data, structuring it for the three charts described below, and making it deployable.

---

## Technology Stack

- **Framework**: Streamlit
- **Charts**: Plotly (interactive, with hover and click behaviours)
- **Data**: Pandas DataFrames, cached with `@st.cache_data`
- **Economic data**: `readabs` package for ABS data, `readrba` for RBA data
- **Deployment**: Streamlit Community Cloud via GitHub
- **Python**: 3.10+

---

## App Layout & Structure

### General Layout Principles

- **Clean, minimal design** — no sidebar clutter. Use a narrow sidebar only for global settings (methodology toggle: BC vs RegData, date range).
- **Single-page scrolling layout** with three clearly separated chart sections, each with its own heading and brief explanatory text.
- **Accessible**: use colourblind-friendly palettes (e.g. Plotly's `Safe` or a custom qualitative palette). Ensure sufficient contrast. All charts must have clear axis labels, titles, and legends.
- **Responsive**: charts should use `use_container_width=True`.
- **Consistent colour coding**: legislation types (Acts, Legislative Instruments, Notifiable Instruments) should use the same colours across all charts.
- **Page title**: "RegCost: Australia's Regulatory Burden"
- **Subtitle/tagline**: "Measuring the stock of federal legislative requirements"

### Sidebar (Global Controls)

```
- Methodology selector: Radio button — "BC Method" / "RegData Method"
- Date range: Slider for year range (e.g. 1901–2025, defaulting to 2000–2025)
- Brief "About" expander explaining what the app measures
```

---

## Chart 1: Growth in Legislation and Legislative Requirements

### Purpose
Show how the stock of Australian federal legislation and the number of binding requirements within it have grown over time.

### Chart Type
**Dual-axis combination chart** (Plotly)

- **Left y-axis / Bar chart**: Cumulative count of in-force legislation by year, stacked by type:
  - Acts (one colour)
  - Legislative Instruments (second colour)
  - Notifiable Instruments (third colour)
- **Right y-axis / Line chart**: Cumulative total requirement count (using the selected methodology — BC or RegData), plotted as a line overlaying the bars.
- **X-axis**: Year

### Interactivity

- **Hover on bars**: Show the count of legislation for that type and year, plus the legislation titles added that year (truncated list, max ~10 items with "and X more..." if needed).
- **Click on a bar segment**: Expand a detail panel (use `st.expander` or a conditional `st.dataframe` below the chart) showing a full table of all legislation of that type registered in that year. Columns: Title, Registration ID, Administering Department, Requirement Count.
- **Hover on line**: Show the cumulative requirement count and the year-on-year change (absolute and percentage).

### Data Requirements

Build or adapt a function that produces a DataFrame with columns:
```
year | leg_type | leg_count_cumulative | leg_titles_list | req_count_cumulative | req_count_yoy_change
```

Where:
- `leg_type` is one of: "Act", "Legislative Instrument", "Notifiable Instrument"
- Cumulative counts represent the total stock in force at the end of each year (not just new registrations — account for repeals if data is available)
- `leg_titles_list` is a list of titles registered that year (for hover display)

### Notes
- If repeal data is unavailable, note this limitation in the "About" section and use gross cumulative counts.
- The year range should start from whenever reliable data begins (likely post-1901 for Acts, more recent for Legislative Instruments).

---

## Chart 2: Industry Impacts

### Purpose
Show how regulatory requirements are distributed across the 19 ANZSIC industry divisions.

### Chart Type
**Horizontal bar chart** (Plotly), sorted by requirement count descending.

- Each bar represents one ANZSIC division
- Bar length = total requirement count from legislation mapped to that industry
- Bars should be coloured by a gradient or use a single accent colour with the top 5 highlighted

### Industry Mapping Logic

This is the hardest analytical piece. Implement a mapping from legislation to ANZSIC divisions using a multi-layered approach:

1. **Department-to-industry mapping** (primary method): Create a lookup table mapping administering government departments/agencies to the ANZSIC divisions they primarily regulate. For example:
   - Department of Agriculture → "A: Agriculture, Forestry and Fishing"
   - APRA/Treasury (financial regulation) → "K: Financial and Insurance Services"
   - Department of Health → "Q: Health Care and Social Assistance"
   - Department of Education → "P: Education and Training"
   - ASIC → "K: Financial and Insurance Services"
   - Safe Work Australia / Comcare → maps broadly across all industries (apportion equally or by employment share)

2. **Keyword-based classification** (supplementary): For legislation that doesn't map cleanly via department, scan the legislation title for industry-relevant keywords. Build a simple keyword→ANZSIC lookup. E.g. "mining" → "B: Mining", "telecommunications" → "J: Information Media and Telecommunications", "banking" → "K: Financial and Insurance Services".

3. **Cross-cutting regulation**: Some legislation applies across all industries (e.g. taxation, workplace health and safety, privacy, corporations law). Flag these as "Cross-cutting" and either:
   - Show them as a separate bar labelled "Cross-cutting / All Industries", OR
   - Apportion them across industries weighted by ABS employment share (Labour Force survey, cat. 6291.0)

4. **Fallback**: Any legislation that can't be mapped → "Unclassified"

Store the mapping as a separate config file (e.g. `industry_mapping.py` or `industry_mapping.json`) so it can be refined over time.

### The 19 ANZSIC Divisions

For reference, the ANZSIC divisions are:
```
A: Agriculture, Forestry and Fishing
B: Mining
C: Manufacturing
D: Electricity, Gas, Water and Waste Services
E: Construction
F: Wholesale Trade
G: Retail Trade
H: Accommodation and Food Services
I: Transport, Postal and Warehousing
J: Information Media and Telecommunications
K: Financial and Insurance Services
L: Rental, Hiring and Real Estate Services
M: Professional, Scientific and Technical Services
N: Administrative and Support Services
O: Public Administration and Safety
P: Education and Training
Q: Health Care and Social Assistance
R: Arts and Recreation Services
S: Other Services
```

### Interactivity

- **Hover on bar**: Show the ANZSIC division name, total requirement count, percentage of all requirements, and number of distinct pieces of legislation mapped to that industry.
- **Click on bar**: Expand a detail panel below the chart listing the top 20 pieces of legislation (by requirement count) mapped to that industry, with columns: Title, Type, Year, Requirement Count, Mapping Method (department/keyword/cross-cutting).
- **Toggle**: Add a checkbox or radio button above the chart: "Include cross-cutting regulation" (default on) vs "Industry-specific only". This toggle controls whether broadly applicable legislation (tax, WHS, corporations) is included in the industry bars or shown separately.

### Data Requirements

DataFrame with columns:
```
anzsic_division | anzsic_code | req_count | leg_count | pct_of_total | top_legislation_list
```

---

## Chart 3: Regulation vs Economic Performance

### Purpose
Compare the growth trajectory of legislation/requirements against key macroeconomic indicators — both at the headline Australia level and broken down by ANZSIC industry.

### Chart Type
**Indexed line chart** (Plotly) — all series rebased to 100 at a common start year (user-selectable, default 2000).

### Sub-chart 3a: Headline (Australia-level)

Plot these series on a single chart, all indexed to 100:

1. **Cumulative legislation count** (from Chart 1 data)
2. **Cumulative requirement count** (from Chart 1 data, using selected methodology)
3. **Real GDP** — ABS cat. 5206.0, chain volume measures, seasonally adjusted. Use `readabs` to fetch. Convert quarterly to annual (financial year average or calendar year average, be consistent).
4. **Total employment** — ABS cat. 6202.0, trend or seasonally adjusted. Convert monthly to annual average.
5. **Labour productivity** — ABS cat. 5206.0 (GDP per hour worked) or derive from GDP/hours worked.
6. **Business investment** — ABS cat. 5206.0, private gross fixed capital formation, chain volume.

Use `readabs` to pull ABS data. Cache aggressively. Handle series breaks gracefully.

### Sub-chart 3b: By Industry

Add a **dropdown selector** (`st.selectbox`) above this sub-chart to choose an ANZSIC division.

When an industry is selected, plot:

1. **Requirement count for that industry** (from Chart 2 mapping), indexed to 100
2. **Industry gross value added (GVA)** — ABS cat. 5206.0, by industry, chain volume. Use `readabs`.
3. **Industry employment** — ABS cat. 6291.0 (Labour Force, Detailed), employment by industry. Use `readabs`.

All indexed to 100 at the selected base year.

If industry-level data isn't available for a particular series, note this clearly on the chart or in a `st.info()` box.

### Interactivity

- **Hover**: Show the index value, the actual level, and the annualised growth rate from base year for each series.
- **Legend toggle**: Users can click legend items to show/hide individual series (Plotly default behaviour — ensure this works).
- **Base year selector**: `st.slider` or `st.number_input` to change the index base year. Default 2000, range from earliest available data year to latest minus 2.
- **Annotation**: Optionally mark key regulatory events (e.g. "2013: Abbott deregulation agenda", "2024: AICD report") as vertical dashed lines with annotations. Store these in a config list.

### Data Requirements

For 3a, build a combined DataFrame:
```
year | leg_count_idx | req_count_idx | real_gdp_idx | employment_idx | productivity_idx | investment_idx
```

For 3b, for each ANZSIC division:
```
year | industry_req_count_idx | industry_gva_idx | industry_employment_idx
```

All `_idx` columns are indexed to 100 at the base year.

### ABS Series References (for `readabs`)

Use `readabs.read_abs()` or `readabs.read_abs_series()`. Key catalogue numbers:

- **5206.0** — Australian National Accounts: National Income, Expenditure and Product
  - Table 1: GDP chain volume, seasonally adjusted
  - Table 5: GVA by industry
  - Table 2 or 34: Private GFCF
- **6202.0** — Labour Force, Australia
  - Total employment, seasonally adjusted
- **6291.0** — Labour Force, Australia, Detailed
  - Employment by industry (ANZSIC division)
- **5206.0 Table 37 or derived**: GDP per hour worked (productivity)

Use `readabs` search functionality if exact table numbers have changed. Cache all ABS data downloads.

---

## Project File Structure

```
regcost/
├── app.py                          # Main Streamlit app entry point
├── requirements.txt                # Dependencies for Streamlit Cloud
├── .streamlit/
│   └── config.toml                 # Streamlit theme config
├── data/
│   ├── fetch_legislation.py        # Load/process legislation data
│   ├── fetch_abs.py                # Fetch ABS macro data via readabs
│   ├── fetch_rba.py                # Fetch RBA data if needed via readrba
│   ├── industry_mapping.py         # Department→ANZSIC and keyword→ANZSIC lookups
│   └── process.py                  # Data transformations, indexing, aggregation
├── charts/
│   ├── chart_legislation_growth.py # Chart 1 builder
│   ├── chart_industry_impacts.py   # Chart 2 builder
│   └── chart_regulation_vs_economy.py  # Chart 3 builder
├── config/
│   ├── colours.py                  # Colour palette definitions
│   ├── annotations.py              # Key regulatory event annotations
│   └── anzsic.py                   # ANZSIC division codes and names
├── utils/
│   └── helpers.py                  # Shared utility functions
└── README.md                       # Project documentation
```

---

## app.py Structure

```python
import streamlit as st

st.set_page_config(
    page_title="RegCost: Australia's Regulatory Burden",
    page_icon="📜",
    layout="wide",
)

# --- Sidebar ---
with st.sidebar:
    methodology = st.radio("Counting methodology", ["BC Method", "RegData Method"])
    year_range = st.slider("Year range", 1901, 2025, (2000, 2025))
    with st.expander("About RegCost"):
        st.markdown("Brief explanation of what this app measures...")

# --- Header ---
st.title("RegCost: Australia's Regulatory Burden")
st.markdown("Measuring the stock of federal legislative requirements")
st.divider()

# --- Chart 1 ---
st.header("📈 Growth in Legislation and Requirements")
st.markdown("Brief 1-2 sentence explanation of what this chart shows.")
# [render chart 1]
# [render click-through detail panel]
st.divider()

# --- Chart 2 ---
st.header("🏭 Industry Impacts")
st.markdown("Brief 1-2 sentence explanation.")
# [cross-cutting toggle]
# [render chart 2]
# [render click-through detail panel]
st.divider()

# --- Chart 3 ---
st.header("📊 Regulation vs Economic Performance")
st.markdown("Brief 1-2 sentence explanation.")

st.subheader("Australia — Headline")
# [base year selector]
# [render chart 3a]

st.subheader("By Industry")
# [industry dropdown]
# [base year selector]
# [render chart 3b]

# --- Footer ---
st.divider()
st.caption("Data sources: Federal Register of Legislation, ABS, RBA. "
           "Methodology based on British Columbia requirements counting and "
           "Mercatus Center RegData approach.")
```

---

## Streamlit Theme (.streamlit/config.toml)

```toml
[theme]
primaryColor = "#1f4e79"
backgroundColor = "#ffffff"
secondaryBackgroundColor = "#f5f7fa"
textColor = "#1a1a2e"
font = "sans serif"
```

---

## requirements.txt

```
streamlit>=1.30
pandas>=2.0
plotly>=5.18
readabs>=0.2
readrba>=0.2
openpyxl
requests
beautifulsoup4
lxml
```

---

## Deployment Checklist

1. Ensure all data fetching uses `@st.cache_data` with appropriate TTL values (legislation data: long TTL or load from bundled CSV; ABS data: 24h TTL).
2. Handle network failures gracefully — if ABS/RBA data can't be fetched, show a `st.warning()` and fall back to bundled sample data if available.
3. Test locally with `streamlit run app.py`.
4. Push to GitHub.
5. Deploy on Streamlit Community Cloud: connect repo, set main file path to `app.py`.
6. Ensure no hardcoded local file paths — all data either fetched via API or bundled in the repo.

---

## Data Strategy

### Option A: Live fetch (preferred for ABS macro data)
Use `readabs` and `readrba` to pull economic data on app load, cached for 24 hours. This keeps the macro data current without manual updates.

### Option B: Bundled CSV (preferred for legislation data)
The legislation scraping and requirement counting is computationally expensive and the dataset changes slowly. Pre-process this data and bundle it as CSV files in the `data/` folder:
- `legislation_counts.csv` — year, type, count, cumulative count
- `requirements_by_legislation.csv` — legislation ID, title, type, year, department, bc_count, regdata_count
- `requirements_by_industry.csv` — ANZSIC division, requirement count, legislation count

These CSVs get updated periodically by running the scraper/counter pipeline separately (not in the webapp).

### Combined approach
Use **Option B for legislation data** and **Option A for economic data**. This keeps the app fast (no scraping on load) while ensuring economic comparisons use current ABS figures.

---

## Key Implementation Notes

1. **Plotly click events in Streamlit**: Streamlit doesn't natively support Plotly click callbacks. Use `plotly_events` from the `streamlit-plotly-events` package, OR implement the drill-down using `st.selectbox` / `st.multiselect` filters that update a detail table below the chart. The latter is simpler and more reliable.

2. **Index calculation**: When rebasing to 100, use: `index = (value / value_at_base_year) * 100`. Handle missing base year values by finding the nearest available year.

3. **Financial year vs calendar year**: ABS national accounts are in financial years (July–June). Be explicit about which convention you use. Either convert everything to calendar year or everything to financial year. Document the choice.

4. **readabs usage**: The `readabs` package downloads ABS time series data. Typical usage:
   ```python
   from readabs import read_abs
   df = read_abs("5206.0")  # downloads all tables for that catalogue number
   # Then filter to the specific series you need
   ```

5. **Colour palette**: Define once in `config/colours.py` and import everywhere:
   ```python
   LEG_COLOURS = {
       "Act": "#1f4e79",
       "Legislative Instrument": "#2e86ab",
       "Notifiable Instrument": "#a4c3d2",
   }
   MACRO_COLOURS = {
       "Legislation": "#1f4e79",
       "Requirements": "#c0392b",
       "Real GDP": "#27ae60",
       "Employment": "#8e44ad",
       "Productivity": "#f39c12",
       "Investment": "#2c3e50",
   }
   ```

6. **Error handling**: Wrap all data fetching in try/except blocks. If a data source fails, display `st.error()` with a clear message and continue rendering other charts.

7. **Performance**: The app should load in under 10 seconds on Streamlit Cloud. Cache everything. Consider pre-computing the industry mapping rather than running it on every load.

---

## What NOT to Build (Out of Scope)

- Do NOT build the legislation scraper or requirement counter — these already exist as separate scripts.
- Do NOT calculate dollar-value compliance costs (the $65B→$160B figures). This app focuses on counts and growth comparisons.
- Do NOT include state/territory legislation — federal only.
- Do NOT build user authentication or data upload features.
- Do NOT use React, Next.js, or any non-Streamlit framework.

---

## Summary of Deliverables

1. A complete, working Streamlit app with the three interactive charts described above.
2. Clean, modular code following the file structure specified.
3. Bundled sample/mock CSV data for legislation if real scraped data isn't available in the repo (so the app can demo without running the full pipeline).
4. A `requirements.txt` ready for Streamlit Cloud.
5. A `README.md` with setup instructions, data source descriptions, and methodology notes.
6. The app must run with `streamlit run app.py` out of the box.
