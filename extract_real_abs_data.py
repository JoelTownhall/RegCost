#!/usr/bin/env python3
"""
Extract REAL ABS data for GVA by industry.
Uses readabs package to fetch actual ABS time series data.
"""

import readabs
import pandas as pd
import re
import csv
from pathlib import Path

# ANZSIC Division names
ANZSIC_NAMES = {
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
}


def main():
    print("=" * 70)
    print("EXTRACTING REAL ABS DATA")
    print("=" * 70)

    print("\nFetching ABS Cat. 5206.0 (National Accounts)...")
    tables, meta = readabs.read_abs_cat('5206.0')
    print(f"Downloaded {len(tables)} tables")

    # Use the annual GVA table (goes from 1960 to 2025)
    gva_annual = tables.get('5206037_Industry_Gross_Value_Added_Annual')
    if gva_annual is None:
        print("ERROR: Could not find annual GVA table")
        return

    print(f"\nAnnual GVA table: {gva_annual.shape}")
    print(f"Date range: {gva_annual.index.min()} to {gva_annual.index.max()}")

    # Find series for each ANZSIC industry
    # Pattern: "Industry Name (X) ; Gross value added"
    gva_series = meta[
        (meta['Table'] == '5206037_Industry_Gross_Value_Added_Annual') &
        (meta['Data Item Description'].str.contains(r'\([A-S]\)', regex=True, na=False))
    ]

    print(f"\nFound {len(gva_series)} industry series in annual table")

    # Map ANZSIC codes to series IDs
    code_to_series = {}
    for _, row in gva_series.iterrows():
        desc = row['Data Item Description']
        match = re.search(r'\(([A-S])\)', desc)
        if match:
            code = match.group(1)
            # Prefer chain volume measures over current prices
            if code not in code_to_series or 'Chain volume' in desc:
                code_to_series[code] = {
                    'series_id': row['Series ID'],
                    'description': desc
                }

    print(f"Mapped {len(code_to_series)} ANZSIC divisions")

    # Extract data
    records = []
    for code, info in sorted(code_to_series.items()):
        series_id = info['series_id']
        if series_id in gva_annual.columns:
            series = gva_annual[series_id]
            for year in series.index:
                year_int = int(str(year)[:4]) if hasattr(year, 'year') else int(year)
                value = series.loc[year]
                if pd.notna(value) and 2000 <= year_int <= 2025:
                    records.append({
                        'year': year_int,
                        'anzsic_code': code,
                        'anzsic_name': ANZSIC_NAMES.get(code, 'Unknown'),
                        'gva_millions': round(float(value), 1),
                    })

    df = pd.DataFrame(records)
    print(f"\nExtracted {len(df)} records")
    print(f"Years: {df['year'].min()} to {df['year'].max()}")
    print(f"Industries: {df['anzsic_code'].nunique()}")

    # Calculate year-over-year growth to verify it's real data
    print("\n" + "=" * 70)
    print("VERIFICATION: Year-over-year growth rates (should vary, not constant)")
    print("=" * 70)

    for code in ['A', 'B', 'C']:
        industry_df = df[df['anzsic_code'] == code].sort_values('year')
        industry_df['growth'] = industry_df['gva_millions'].pct_change() * 100
        print(f"\n{code}: {ANZSIC_NAMES[code]}")
        print(f"  Growth rates: {industry_df['growth'].dropna().round(1).tolist()[:10]}")
        print(f"  Std dev: {industry_df['growth'].std():.1f}% (should be > 1 if real data)")

    # Save to CSV
    output_dir = Path(__file__).parent / 'output'
    output_path = output_dir / 'economic_indicators.csv'

    # Add placeholder columns for hours worked and productivity
    df['hours_worked_millions'] = None
    df['gva_per_hour'] = None

    # Calculate growth percentages
    growth_records = []
    for code in df['anzsic_code'].unique():
        industry_df = df[df['anzsic_code'] == code].sort_values('year')
        industry_df['gva_growth_pct'] = industry_df['gva_millions'].pct_change() * 100
        growth_records.extend(industry_df.to_dict('records'))

    df_final = pd.DataFrame(growth_records)
    df_final = df_final.sort_values(['year', 'anzsic_code'])

    # Save
    df_final.to_csv(output_path, index=False)
    print(f"\nSaved: {output_path}")
    print(f"Size: {output_path.stat().st_size / 1024:.1f} KB")

    # Also update anzsic_industry_stats.csv
    stats_path = output_dir / 'anzsic_industry_stats.csv'
    stats_df = df_final[['year', 'anzsic_code', 'anzsic_name', 'gva_millions']].copy()
    stats_df['firm_count'] = None  # Placeholder - would need Cat. 8165.0
    stats_df.to_csv(stats_path, index=False)
    print(f"Saved: {stats_path}")

    print("\n" + "=" * 70)
    print("DONE - Real ABS data extracted!")
    print("Note: Hours worked and firm counts need additional ABS catalogues")
    print("=" * 70)


if __name__ == "__main__":
    main()
