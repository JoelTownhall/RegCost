"""Fetch ABS economic data - using pre-fetched bundled CSV files."""

import pandas as pd
import streamlit as st
from pathlib import Path

# Path to output directory
DATA_DIR = Path(__file__).parent.parent / "output"


@st.cache_data(ttl=86400)  # Cache for 24 hours
def load_economic_indicators() -> pd.DataFrame:
    """Load pre-fetched economic indicators from CSV."""
    csv_path = DATA_DIR / "economic_indicators.csv"
    if not csv_path.exists():
        st.warning(f"Economic indicators file not found: {csv_path}")
        return pd.DataFrame()

    df = pd.read_csv(csv_path)
    return df


@st.cache_data(ttl=86400)
def load_industry_stats() -> pd.DataFrame:
    """Load pre-fetched industry statistics from CSV."""
    csv_path = DATA_DIR / "anzsic_industry_stats.csv"
    if not csv_path.exists():
        st.warning(f"Industry stats file not found: {csv_path}")
        return pd.DataFrame()

    df = pd.read_csv(csv_path)
    return df


@st.cache_data(ttl=86400)
def get_headline_indicators(year_start: int, year_end: int) -> pd.DataFrame:
    """Get headline economic indicators for Australia (aggregate)."""
    df = load_economic_indicators()
    if df.empty:
        return pd.DataFrame()

    # Filter to total economy (anzsic_code is empty or 'Total')
    total_df = df[df["anzsic_code"].isna() | (df["anzsic_code"] == "Total")].copy()

    # If no total row, aggregate from industries
    if total_df.empty:
        total_df = df.groupby("year").agg({
            "gva_millions": "sum",
            "hours_worked_millions": "sum",
        }).reset_index()
        total_df["gva_per_hour"] = total_df["gva_millions"] / total_df["hours_worked_millions"]

    # Filter to year range
    total_df = total_df[(total_df["year"] >= year_start) & (total_df["year"] <= year_end)]

    return total_df


@st.cache_data(ttl=86400)
def get_industry_indicators(anzsic_code: str, year_start: int, year_end: int) -> pd.DataFrame:
    """Get economic indicators for a specific ANZSIC industry."""
    df = load_economic_indicators()
    if df.empty:
        return pd.DataFrame()

    # Filter to specific industry
    industry_df = df[df["anzsic_code"] == anzsic_code].copy()

    # Filter to year range
    industry_df = industry_df[(industry_df["year"] >= year_start) & (industry_df["year"] <= year_end)]

    return industry_df


def index_to_base_year(df: pd.DataFrame, base_year: int, columns: list) -> pd.DataFrame:
    """
    Rebase specified columns to index 100 at base year.

    Args:
        df: DataFrame with 'year' column and data columns
        base_year: Year to use as base (index = 100)
        columns: List of column names to index

    Returns:
        DataFrame with new indexed columns (original_name_idx)
    """
    result = df.copy()

    for col in columns:
        if col not in df.columns:
            continue

        # Get base year value
        base_row = df[df["year"] == base_year]
        if base_row.empty:
            # Find nearest available year
            available_years = df["year"].dropna().unique()
            if len(available_years) == 0:
                continue
            nearest_year = min(available_years, key=lambda x: abs(x - base_year))
            base_row = df[df["year"] == nearest_year]

        base_value = base_row[col].iloc[0]
        if pd.isna(base_value) or base_value == 0:
            continue

        # Calculate index
        result[f"{col}_idx"] = (df[col] / base_value * 100).round(2)

    return result
