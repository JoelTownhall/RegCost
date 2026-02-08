"""Data processing and aggregation functions."""

import pandas as pd
import streamlit as st
from typing import Tuple

from config.anzsic import ANZSIC_DIVISIONS


@st.cache_data(ttl=3600)
def aggregate_by_industry(
    df: pd.DataFrame,
    year: int,
    methodology: str = "BC Method",
    include_cross_cutting: bool = True
) -> pd.DataFrame:
    """
    Aggregate legislation and requirements by ANZSIC industry.

    Args:
        df: Time series DataFrame with legislation data
        year: Year to aggregate for (uses as_of_year)
        methodology: "BC Method" or "RegData Method"
        include_cross_cutting: Whether to include cross-cutting legislation

    Returns:
        DataFrame with columns: anzsic_code, anzsic_name, leg_count, req_count, pct_of_total
    """
    req_col = "bc_requirements" if methodology == "BC Method" else "regdata_requirements"

    # Filter to specified year
    df_year = df[df["as_of_year"] == year].copy()

    if df_year.empty:
        return pd.DataFrame()

    # Optionally exclude cross-cutting
    if not include_cross_cutting:
        df_year = df_year[df_year["anzsic_code"] != "X"]

    # Aggregate by ANZSIC code
    grouped = df_year.groupby(["anzsic_code", "anzsic_name"]).agg(
        leg_count=("register_id", "count"),
        req_count=(req_col, "sum"),
        top_legislation=("title", lambda x: list(x.head(20)))
    ).reset_index()

    # Calculate percentage of total
    total_reqs = grouped["req_count"].sum()
    grouped["pct_of_total"] = (grouped["req_count"] / total_reqs * 100).round(1) if total_reqs > 0 else 0

    # Sort by requirement count descending
    grouped = grouped.sort_values("req_count", ascending=False)

    return grouped


@st.cache_data(ttl=3600)
def get_industry_legislation_detail(
    df: pd.DataFrame,
    year: int,
    anzsic_code: str,
    methodology: str = "BC Method"
) -> pd.DataFrame:
    """Get detailed legislation list for a specific industry."""
    req_col = "bc_requirements" if methodology == "BC Method" else "regdata_requirements"

    # Filter to year and industry
    filtered = df[
        (df["as_of_year"] == year) &
        (df["anzsic_code"] == anzsic_code)
    ].copy()

    # Select columns for display
    result = filtered[["title", "display_type", "making_year", req_col]].copy()
    result.columns = ["Title", "Type", "Year", "Requirement Count"]
    result = result.sort_values("Requirement Count", ascending=False).head(20)

    return result


@st.cache_data(ttl=3600)
def build_chart3_headline_data(
    leg_df: pd.DataFrame,
    econ_df: pd.DataFrame,
    year_start: int,
    year_end: int,
    base_year: int,
    methodology: str = "BC Method"
) -> pd.DataFrame:
    """
    Build combined DataFrame for Chart 3a (headline indicators).

    Returns DataFrame with indexed values for legislation, requirements,
    and economic indicators.
    """
    req_col = "bc_requirements" if methodology == "BC Method" else "regdata_requirements"

    # Get legislation counts by year
    leg_by_year = leg_df.groupby("as_of_year").agg(
        leg_count=("register_id", "count"),
        req_count=(req_col, "sum")
    ).reset_index()
    leg_by_year.rename(columns={"as_of_year": "year"}, inplace=True)

    # Filter to year range
    leg_by_year = leg_by_year[
        (leg_by_year["year"] >= year_start) &
        (leg_by_year["year"] <= year_end)
    ]

    # Get aggregate economic indicators
    if "anzsic_code" in econ_df.columns:
        # Sum across industries for total
        econ_total = econ_df.groupby("year").agg({
            "gva_millions": "sum",
            "employment_thousands": "sum",
            "hours_worked_millions": "sum",
        }).reset_index()
        econ_total["productivity"] = econ_total["gva_millions"] / econ_total["hours_worked_millions"]
    else:
        econ_total = econ_df.copy()
        if "gva_per_hour" in econ_total.columns:
            econ_total["productivity"] = econ_total["gva_per_hour"]

    # Merge datasets
    combined = leg_by_year.merge(econ_total, on="year", how="outer")
    combined = combined.sort_values("year")

    # Filter to year range
    combined = combined[
        (combined["year"] >= year_start) &
        (combined["year"] <= year_end)
    ]

    # Index to base year
    combined = index_series(combined, base_year, [
        "leg_count", "req_count", "gva_millions",
        "employment_thousands", "productivity"
    ])

    return combined


@st.cache_data(ttl=3600)
def build_chart3_industry_data(
    leg_df: pd.DataFrame,
    econ_df: pd.DataFrame,
    anzsic_code: str,
    year_start: int,
    year_end: int,
    base_year: int,
    methodology: str = "BC Method"
) -> pd.DataFrame:
    """
    Build combined DataFrame for Chart 3b (industry-level indicators).
    """
    req_col = "bc_requirements" if methodology == "BC Method" else "regdata_requirements"

    # Get industry legislation counts by year
    industry_leg = leg_df[leg_df["anzsic_code"] == anzsic_code].groupby("as_of_year").agg(
        req_count=(req_col, "sum")
    ).reset_index()
    industry_leg.rename(columns={"as_of_year": "year"}, inplace=True)

    # Get industry economic indicators
    industry_econ = econ_df[econ_df["anzsic_code"] == anzsic_code].copy()

    # Merge datasets
    combined = industry_leg.merge(industry_econ[["year", "gva_millions", "employment_thousands"]],
                                   on="year", how="outer")
    combined = combined.sort_values("year")

    # Filter to year range
    combined = combined[
        (combined["year"] >= year_start) &
        (combined["year"] <= year_end)
    ]

    # Index to base year
    combined = index_series(combined, base_year, [
        "req_count", "gva_millions", "employment_thousands"
    ])

    return combined


def index_series(df: pd.DataFrame, base_year: int, columns: list) -> pd.DataFrame:
    """Index specified columns to 100 at base year."""
    result = df.copy()

    for col in columns:
        if col not in df.columns:
            continue

        # Find base year value
        base_row = df[df["year"] == base_year]
        if base_row.empty:
            # Use first available year as fallback
            available = df[df[col].notna()]["year"]
            if len(available) == 0:
                continue
            base_year_fallback = available.iloc[0]
            base_row = df[df["year"] == base_year_fallback]

        base_value = base_row[col].iloc[0]
        if pd.isna(base_value) or base_value == 0:
            continue

        result[f"{col}_idx"] = (df[col] / base_value * 100).round(1)

    return result
