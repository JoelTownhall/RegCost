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
    highlight_top_n: int = 5,
    display_mode: str = "Requirements"
) -> go.Figure:
    """
    Create horizontal bar chart showing requirements or legislation by ANZSIC industry.

    Args:
        df: Time series DataFrame with legislation data
        year: Year to display
        methodology: "BC Method" or "RegData Method"
        include_cross_cutting: Whether to include cross-cutting regulation
        highlight_top_n: Number of top industries to highlight
        display_mode: "Requirements" for requirement counts, "Legislation" for legislation counts

    Returns:
        Plotly Figure object
    """
    # Handle methodology name variations
    if methodology in ["Mercatus Method", "RegData Method"]:
        req_col = "regdata_requirements"
    else:
        req_col = "bc_requirements"

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

    if display_mode == "Legislation":
        return _create_legislation_count_chart(df_year, year, highlight_top_n)
    else:
        return _create_requirements_count_chart(df_year, year, methodology, req_col, highlight_top_n)


def _create_requirements_count_chart(
    df_year: pd.DataFrame,
    year: int,
    methodology: str,
    req_col: str,
    highlight_top_n: int
) -> go.Figure:
    """Create horizontal bar chart showing requirements by industry."""
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


def _create_legislation_count_chart(
    df_year: pd.DataFrame,
    year: int,
    highlight_top_n: int
) -> go.Figure:
    """Create stacked horizontal bar chart showing legislation count by industry, split by Primary/Secondary."""
    # Colors for Primary and Secondary
    PRIMARY_COLOR = "#1f4e79"
    SECONDARY_COLOR = "#2e86ab"

    # Aggregate by ANZSIC and type (Primary/Secondary)
    grouped = df_year.groupby(["anzsic_code", "anzsic_name", "type"]).agg(
        leg_count=("register_id", "count"),
    ).reset_index()

    # Pivot to get Primary and Secondary as separate columns
    pivot = grouped.pivot_table(
        index=["anzsic_code", "anzsic_name"],
        columns="type",
        values="leg_count",
        fill_value=0
    ).reset_index()

    # Ensure both Primary and Secondary columns exist
    if "Primary" not in pivot.columns:
        pivot["Primary"] = 0
    if "Secondary" not in pivot.columns:
        pivot["Secondary"] = 0

    # Calculate total for sorting
    pivot["total"] = pivot["Primary"] + pivot["Secondary"]

    # Calculate percentage
    total_leg = pivot["total"].sum()
    pivot["pct_of_total"] = (pivot["total"] / total_leg * 100).round(1) if total_leg > 0 else 0

    # Sort by total legislation count
    pivot = pivot.sort_values("total", ascending=True)

    # Create labels with ANZSIC code
    pivot["label"] = pivot.apply(
        lambda row: f"{row['anzsic_code']}: {row['anzsic_name']}", axis=1
    )

    # Build hover text for Primary
    hover_primary = []
    for _, row in pivot.iterrows():
        hover_primary.append(
            f"<b>{row['anzsic_name']}</b><br>"
            f"Primary: {format_number(row['Primary'])}<br>"
            f"Secondary: {format_number(row['Secondary'])}<br>"
            f"Total: {format_number(row['total'])}<br>"
            f"Share of Total: {row['pct_of_total']:.1f}%"
        )

    # Build hover text for Secondary
    hover_secondary = []
    for _, row in pivot.iterrows():
        hover_secondary.append(
            f"<b>{row['anzsic_name']}</b><br>"
            f"Primary: {format_number(row['Primary'])}<br>"
            f"Secondary: {format_number(row['Secondary'])}<br>"
            f"Total: {format_number(row['total'])}<br>"
            f"Share of Total: {row['pct_of_total']:.1f}%"
        )

    # Create figure with stacked bars
    fig = go.Figure()

    # Primary legislation bar
    fig.add_trace(go.Bar(
        y=pivot["label"],
        x=pivot["Primary"],
        orientation="h",
        name="Primary",
        marker_color=PRIMARY_COLOR,
        hovertemplate="%{customdata}<extra></extra>",
        customdata=hover_primary,
    ))

    # Secondary legislation bar
    fig.add_trace(go.Bar(
        y=pivot["label"],
        x=pivot["Secondary"],
        orientation="h",
        name="Secondary",
        marker_color=SECONDARY_COLOR,
        hovertemplate="%{customdata}<extra></extra>",
        customdata=hover_secondary,
    ))

    # Update layout
    fig.update_layout(
        title=dict(
            text=f"Legislation by Industry ({year})",
            font=dict(size=16),
        ),
        xaxis_title="Number of Legislation",
        yaxis_title="",
        plot_bgcolor="white",
        height=max(400, len(pivot) * 30),  # Dynamic height
        margin=dict(l=250),  # Space for long labels
        barmode="stack",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
    )

    fig.update_xaxes(showgrid=True, gridcolor="#eee")
    fig.update_yaxes(showgrid=False)

    return fig


def get_industry_detail(
    df: pd.DataFrame,
    year: int,
    anzsic_code: str,
    methodology: str = "BC Method",
    top_n: int = 50
) -> pd.DataFrame:
    """
    Get legislation for a specific industry, showing Primary/Secondary type.

    Args:
        df: Time series DataFrame
        year: Selected year
        anzsic_code: ANZSIC division code
        methodology: Counting methodology
        top_n: Number of top legislation to return

    Returns:
        DataFrame with legislation details (Title, Type, Requirement Count)
    """
    # Handle methodology name variations
    if methodology in ["Mercatus Method", "RegData Method"]:
        req_col = "regdata_requirements"
    else:
        req_col = "bc_requirements"

    # Filter
    filtered = df[
        (df["as_of_year"] == year) &
        (df["anzsic_code"] == anzsic_code)
    ].copy()

    if filtered.empty:
        return pd.DataFrame()

    # Select and format columns - use 'type' for Primary/Secondary
    result = filtered[["title", "type", req_col]].copy()
    result.columns = ["Title", "Type", "Requirement Count"]
    result = result.sort_values("Requirement Count", ascending=False).head(top_n)

    return result


def get_available_industries(df: pd.DataFrame, year: int) -> list:
    """Get list of ANZSIC codes with data for the given year."""
    df_year = df[df["as_of_year"] == year]
    return sorted(df_year["anzsic_code"].unique().tolist())
