"""Load and process legislation data from bundled CSV files."""

import pandas as pd
import streamlit as st
from pathlib import Path

# Path to output directory (relative to app root)
DATA_DIR = Path(__file__).parent.parent / "output"


@st.cache_data(ttl=3600)  # Cache for 1 hour
def load_legislation_base() -> pd.DataFrame:
    """Load the base legislation dataset with requirement counts."""
    csv_path = DATA_DIR / "webapp_data_base.csv"
    if not csv_path.exists():
        st.error(f"Legislation data file not found: {csv_path}")
        return pd.DataFrame()

    df = pd.read_csv(csv_path)

    # Standardize type names for display
    df["display_type"] = df["subtype"].map({
        "Act": "Act",
        "Legislative instrument": "Legislative Instrument",
        "Notifiable instrument": "Notifiable Instrument",
    }).fillna(df["subtype"])

    return df


@st.cache_data(ttl=3600)
def load_legislation_timeseries() -> pd.DataFrame:
    """Load the time series legislation data (legislation at each point in time)."""
    csv_path = DATA_DIR / "webapp_data_timeseries.csv"
    if not csv_path.exists():
        st.error(f"Time series data file not found: {csv_path}")
        return pd.DataFrame()

    df = pd.read_csv(csv_path)

    # Standardize type names
    df["display_type"] = df["subtype"].map({
        "Act": "Act",
        "Legislative instrument": "Legislative Instrument",
        "Notifiable instrument": "Notifiable Instrument",
    }).fillna(df["subtype"])

    return df


@st.cache_data(ttl=3600)
def get_cumulative_counts_by_year(
    df: pd.DataFrame,
    year_start: int,
    year_end: int,
    methodology: str = "BC Method"
) -> pd.DataFrame:
    """
    Compute cumulative legislation and requirement counts by year and type.

    This uses the time series data where each row represents legislation
    in force at that point in time.
    """
    # Filter to year range
    df_filtered = df[(df["as_of_year"] >= year_start) & (df["as_of_year"] <= year_end)]

    if df_filtered.empty:
        return pd.DataFrame()

    # Choose requirement column based on methodology
    req_col = "bc_requirements" if methodology == "BC Method" else "regdata_requirements"

    # Group by year and type to get counts
    grouped = df_filtered.groupby(["as_of_year", "display_type"]).agg(
        leg_count=("register_id", "count"),
        req_count=(req_col, "sum"),
        titles=("title", lambda x: list(x.head(15)))  # Top 15 titles for hover
    ).reset_index()

    grouped.rename(columns={"as_of_year": "year"}, inplace=True)

    # Calculate year-on-year changes for requirements (total across types)
    total_by_year = grouped.groupby("year")["req_count"].sum().reset_index()
    total_by_year["req_yoy_change"] = total_by_year["req_count"].diff()
    total_by_year["req_yoy_pct"] = (total_by_year["req_yoy_change"] / total_by_year["req_count"].shift(1) * 100).round(1)

    # Merge back
    grouped = grouped.merge(total_by_year[["year", "req_yoy_change", "req_yoy_pct"]], on="year", how="left")

    return grouped


@st.cache_data(ttl=3600)
def get_new_legislation_by_year(
    df: pd.DataFrame,
    year_start: int,
    year_end: int
) -> pd.DataFrame:
    """Get legislation newly registered in each year (using making_year from base data)."""
    # This uses the base data, filtered by making_year
    df_filtered = df[(df["making_year"] >= year_start) & (df["making_year"] <= year_end)]

    return df_filtered


@st.cache_data(ttl=3600)
def get_legislation_detail_for_year_type(
    df: pd.DataFrame,
    year: int,
    leg_type: str,
    methodology: str = "BC Method"
) -> pd.DataFrame:
    """Get detailed legislation list for a specific year and type."""
    req_col = "bc_requirements" if methodology == "BC Method" else "regdata_requirements"

    # Filter from time series data
    filtered = df[
        (df["as_of_year"] == year) &
        (df["display_type"] == leg_type)
    ].copy()

    # Select and rename columns for display
    result = filtered[["title", "register_id", "anzsic_name", req_col]].copy()
    result.columns = ["Title", "Registration ID", "Administering Industry", "Requirement Count"]
    result = result.sort_values("Requirement Count", ascending=False)

    return result
