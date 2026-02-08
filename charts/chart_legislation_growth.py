"""Chart 1: Growth in Legislation and Legislative Requirements."""

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import streamlit as st

from utils.helpers import truncate_list, format_number, format_percentage


# Colours for Primary/Secondary legislation
COLOURS = {
    "Primary": "#1f4e79",      # Dark blue for Acts
    "Secondary": "#2e86ab",    # Lighter blue for Instruments
}


def create_legislation_growth_chart(
    df: pd.DataFrame,
    year_start: int,
    year_end: int,
    methodology: str = "BC Method"
) -> go.Figure:
    """
    Create grouped stacked bar chart showing:
    - Stacked bar 1: Legislation counts (Primary + Secondary)
    - Stacked bar 2: Requirements counts (Primary + Secondary)

    Both grouped by year.

    Args:
        df: Time series DataFrame with legislation data
        year_start: Start year for display
        year_end: End year for display
        methodology: "BC Method" or "Mercatus Method"

    Returns:
        Plotly Figure object
    """
    # Handle methodology name variations
    if methodology == "Mercatus Method":
        req_col = "regdata_requirements"
    else:
        req_col = "bc_requirements"

    # Filter to year range
    df_filtered = df[(df["as_of_year"] >= year_start) & (df["as_of_year"] <= year_end)]

    if df_filtered.empty:
        fig = go.Figure()
        fig.add_annotation(text="No data available for selected year range",
                          xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        return fig

    df_filtered = df_filtered.copy()

    # Aggregate by year and type (Primary/Secondary)
    grouped = df_filtered.groupby(["as_of_year", "type"]).agg(
        leg_count=("register_id", "count"),
        req_count=(req_col, "sum"),
    ).reset_index()

    # Get unique years
    years = sorted(grouped["as_of_year"].unique())

    # Prepare data for each type
    primary_data = grouped[grouped["type"] == "Primary"].set_index("as_of_year")
    secondary_data = grouped[grouped["type"] == "Secondary"].set_index("as_of_year")

    # Create arrays for plotting
    primary_leg = [primary_data.loc[y, "leg_count"] if y in primary_data.index else 0 for y in years]
    secondary_leg = [secondary_data.loc[y, "leg_count"] if y in secondary_data.index else 0 for y in years]
    primary_req = [primary_data.loc[y, "req_count"] if y in primary_data.index else 0 for y in years]
    secondary_req = [secondary_data.loc[y, "req_count"] if y in secondary_data.index else 0 for y in years]

    # Create figure with secondary y-axis
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # Add legislation bars (left Y-axis, offset to the left)
    fig.add_trace(
        go.Bar(
            name="Primary Legislation",
            x=years,
            y=primary_leg,
            marker_color=COLOURS["Primary"],
            offsetgroup=0,
            legendgroup="legislation",
            legendgrouptitle_text="Legislation Count",
            hovertemplate="<b>Primary Legislation</b><br>Year: %{x}<br>Count: %{y:,}<extra></extra>",
        ),
        secondary_y=False,
    )

    fig.add_trace(
        go.Bar(
            name="Secondary Legislation",
            x=years,
            y=secondary_leg,
            marker_color=COLOURS["Secondary"],
            offsetgroup=0,
            base=primary_leg,  # Stack on top of primary
            legendgroup="legislation",
            hovertemplate="<b>Secondary Legislation</b><br>Year: %{x}<br>Count: %{y:,}<extra></extra>",
        ),
        secondary_y=False,
    )

    # Add requirements bars (right Y-axis, offset to the right)
    fig.add_trace(
        go.Bar(
            name="Primary Requirements",
            x=years,
            y=primary_req,
            marker_color=COLOURS["Primary"],
            marker_pattern_shape="/",  # Add pattern to distinguish from legislation
            offsetgroup=1,
            legendgroup="requirements",
            legendgrouptitle_text="Requirements Count",
            hovertemplate="<b>Primary Requirements</b><br>Year: %{x}<br>Count: %{y:,}<extra></extra>",
        ),
        secondary_y=True,
    )

    fig.add_trace(
        go.Bar(
            name="Secondary Requirements",
            x=years,
            y=secondary_req,
            marker_color=COLOURS["Secondary"],
            marker_pattern_shape="/",  # Add pattern to distinguish from legislation
            offsetgroup=1,
            base=primary_req,  # Stack on top of primary
            legendgroup="requirements",
            hovertemplate="<b>Secondary Requirements</b><br>Year: %{x}<br>Count: %{y:,}<extra></extra>",
        ),
        secondary_y=True,
    )

    # Update layout
    fig.update_layout(
        barmode="group",
        title=dict(
            text=f"Legislation and Requirements by Type ({methodology})",
            font=dict(size=16),
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5,
            groupclick="toggleitem",
        ),
        hovermode="x unified",
        plot_bgcolor="white",
        bargap=0.15,
        bargroupgap=0.1,
    )

    fig.update_xaxes(
        title_text="Year",
        showgrid=True,
        gridcolor="#eee",
        dtick=2,  # Show every 2 years
    )

    # Update left Y-axis (legislation count)
    fig.update_yaxes(
        title_text="Count of Legislation",
        showgrid=True,
        gridcolor="#eee",
        secondary_y=False,
    )

    # Update right Y-axis (requirements count)
    fig.update_yaxes(
        title_text="Count of Requirements",
        showgrid=True,
        gridcolor="#eee",
        secondary_y=True,
    )

    return fig


def get_legislation_requirements_detail(
    df: pd.DataFrame,
    year: int,
    methodology: str = "BC Method"
) -> pd.DataFrame:
    """
    Get all legislation for a year, ranked by requirement count (most to least).

    Args:
        df: Time series DataFrame
        year: Selected year
        methodology: Counting methodology

    Returns:
        DataFrame for display with columns: Title, Type, Subtype, Requirements
    """
    # Handle methodology name variations
    if methodology == "Mercatus Method":
        req_col = "regdata_requirements"
    else:
        req_col = "bc_requirements"

    # Filter to specified year
    filtered = df[df["as_of_year"] == year].copy()

    if filtered.empty:
        return pd.DataFrame()

    # Select columns for display
    result = filtered[["title", "type", "subtype", "register_id", req_col]].copy()
    result.columns = ["Title", "Type", "Subtype", "Register ID", "Requirement Count"]

    # Sort by requirement count descending
    result = result.sort_values("Requirement Count", ascending=False)

    return result


def render_legislation_detail_table(
    df: pd.DataFrame,
    year: int,
    leg_type: str,
    methodology: str = "BC Method"
) -> pd.DataFrame:
    """
    Get legislation details for display in expandable table.
    (Legacy function for compatibility)

    Args:
        df: Time series DataFrame
        year: Selected year
        leg_type: Selected legislation type
        methodology: Counting methodology

    Returns:
        DataFrame for display
    """
    # Handle methodology name variations
    if methodology == "Mercatus Method":
        req_col = "regdata_requirements"
    else:
        req_col = "bc_requirements"

    # Standardize type names
    df = df.copy()
    df["display_type"] = df["subtype"].map({
        "Act": "Act",
        "Legislative instrument": "Legislative Instrument",
        "Notifiable instrument": "Notifiable Instrument",
    }).fillna(df["subtype"])

    filtered = df[
        (df["as_of_year"] == year) &
        (df["display_type"] == leg_type)
    ]

    result = filtered[["title", "register_id", "anzsic_name", req_col]].copy()
    result.columns = ["Title", "Registration ID", "Industry", "Requirement Count"]
    result = result.sort_values("Requirement Count", ascending=False)

    return result
