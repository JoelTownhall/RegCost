"""Chart 2: Industry Impacts - Requirements by ANZSIC Division."""

import plotly.graph_objects as go
import pandas as pd
import streamlit as st

from config.colours import INDUSTRY_HIGHLIGHT, INDUSTRY_DEFAULT
from config.anzsic import ANZSIC_DIVISIONS
from utils.helpers import format_number


def create_industry_impacts_chart(
    df: pd.DataFrame,
    year: int,
    methodology: str = "BC Method",
    include_cross_cutting: bool = True,
    highlight_top_n: int = 5
) -> go.Figure:
    """
    Create horizontal bar chart showing requirements by ANZSIC industry.

    Args:
        df: Time series DataFrame with legislation data
        year: Year to display
        methodology: "BC Method" or "RegData Method"
        include_cross_cutting: Whether to include cross-cutting regulation
        highlight_top_n: Number of top industries to highlight

    Returns:
        Plotly Figure object
    """
    req_col = "bc_requirements" if methodology == "BC Method" else "regdata_requirements"

    # Filter to specified year
    df_year = df[df["as_of_year"] == year].copy()

    if df_year.empty:
        fig = go.Figure()
        fig.add_annotation(text="No data available for selected year",
                          xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        return fig

    # Optionally exclude cross-cutting
    if not include_cross_cutting:
        df_year = df_year[df_year["anzsic_code"] != "X"]

    # Aggregate by ANZSIC
    grouped = df_year.groupby(["anzsic_code", "anzsic_name"]).agg(
        leg_count=("register_id", "count"),
        req_count=(req_col, "sum"),
    ).reset_index()

    # Calculate percentage
    total_reqs = grouped["req_count"].sum()
    grouped["pct_of_total"] = (grouped["req_count"] / total_reqs * 100).round(1) if total_reqs > 0 else 0

    # Sort by requirement count
    grouped = grouped.sort_values("req_count", ascending=True)  # ascending for horizontal bars

    # Create labels with ANZSIC code
    grouped["label"] = grouped.apply(
        lambda row: f"{row['anzsic_code']}: {row['anzsic_name']}", axis=1
    )

    # Determine colors (highlight top N)
    n_bars = len(grouped)
    colors = [INDUSTRY_DEFAULT] * n_bars
    for i in range(min(highlight_top_n, n_bars)):
        colors[n_bars - 1 - i] = INDUSTRY_HIGHLIGHT  # Top bars are at the end after sorting

    # Build hover text
    hover_texts = []
    for _, row in grouped.iterrows():
        hover_texts.append(
            f"<b>{row['anzsic_name']}</b><br>"
            f"Requirements: {format_number(row['req_count'])}<br>"
            f"Legislation: {format_number(row['leg_count'])}<br>"
            f"Share of Total: {row['pct_of_total']:.1f}%"
        )

    # Create figure
    fig = go.Figure()

    fig.add_trace(go.Bar(
        y=grouped["label"],
        x=grouped["req_count"],
        orientation="h",
        marker_color=colors,
        hovertemplate="%{customdata}<extra></extra>",
        customdata=hover_texts,
    ))

    # Update layout
    fig.update_layout(
        title=dict(
            text=f"Requirements by Industry ({year}, {methodology})",
            font=dict(size=16),
        ),
        xaxis_title="Number of Requirements",
        yaxis_title="",
        plot_bgcolor="white",
        height=max(400, len(grouped) * 30),  # Dynamic height
        margin=dict(l=250),  # Space for long labels
    )

    fig.update_xaxes(showgrid=True, gridcolor="#eee")
    fig.update_yaxes(showgrid=False)

    return fig


def get_industry_detail(
    df: pd.DataFrame,
    year: int,
    anzsic_code: str,
    methodology: str = "BC Method",
    top_n: int = 20
) -> pd.DataFrame:
    """
    Get top legislation for a specific industry.

    Args:
        df: Time series DataFrame
        year: Selected year
        anzsic_code: ANZSIC division code
        methodology: Counting methodology
        top_n: Number of top legislation to return

    Returns:
        DataFrame with top legislation details
    """
    req_col = "bc_requirements" if methodology == "BC Method" else "regdata_requirements"

    # Standardize type names
    df = df.copy()
    df["display_type"] = df["subtype"].map({
        "Act": "Act",
        "Legislative instrument": "Legislative Instrument",
        "Notifiable instrument": "Notifiable Instrument",
    }).fillna(df["subtype"])

    # Filter
    filtered = df[
        (df["as_of_year"] == year) &
        (df["anzsic_code"] == anzsic_code)
    ]

    # Select and format columns
    result = filtered[["title", "display_type", "making_year", req_col]].copy()
    result.columns = ["Title", "Type", "Year Registered", "Requirement Count"]
    result = result.sort_values("Requirement Count", ascending=False).head(top_n)

    return result


def get_available_industries(df: pd.DataFrame, year: int) -> list:
    """Get list of ANZSIC codes with data for the given year."""
    df_year = df[df["as_of_year"] == year]
    return sorted(df_year["anzsic_code"].unique().tolist())
