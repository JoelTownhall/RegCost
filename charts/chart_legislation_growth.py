"""Chart 1: Growth in Legislation and Legislative Requirements."""

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import streamlit as st

from config.colours import LEG_COLOURS
from utils.helpers import truncate_list, format_number, format_percentage


def create_legislation_growth_chart(
    df: pd.DataFrame,
    year_start: int,
    year_end: int,
    methodology: str = "BC Method"
) -> go.Figure:
    """
    Create dual-axis chart showing cumulative legislation (bars) and requirements (line).

    Args:
        df: Time series DataFrame with legislation data
        year_start: Start year for display
        year_end: End year for display
        methodology: "BC Method" or "RegData Method"

    Returns:
        Plotly Figure object
    """
    req_col = "bc_requirements" if methodology == "BC Method" else "regdata_requirements"

    # Filter to year range
    df_filtered = df[(df["as_of_year"] >= year_start) & (df["as_of_year"] <= year_end)]

    if df_filtered.empty:
        fig = go.Figure()
        fig.add_annotation(text="No data available for selected year range",
                          xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        return fig

    # Standardize type names
    df_filtered = df_filtered.copy()
    df_filtered["display_type"] = df_filtered["subtype"].map({
        "Act": "Act",
        "Legislative instrument": "Legislative Instrument",
        "Notifiable instrument": "Notifiable Instrument",
    }).fillna(df_filtered["subtype"])

    # Aggregate by year and type
    grouped = df_filtered.groupby(["as_of_year", "display_type"]).agg(
        leg_count=("register_id", "count"),
        req_count=(req_col, "sum"),
        titles=("title", lambda x: list(x.head(15)))
    ).reset_index()

    # Pivot for stacked bars
    pivot_counts = grouped.pivot(index="as_of_year", columns="display_type", values="leg_count").fillna(0)
    pivot_titles = grouped.pivot(index="as_of_year", columns="display_type", values="titles")

    # Total requirements by year (for line chart)
    total_reqs = grouped.groupby("as_of_year")["req_count"].sum().reset_index()
    total_reqs["yoy_change"] = total_reqs["req_count"].diff()
    total_reqs["yoy_pct"] = (total_reqs["yoy_change"] / total_reqs["req_count"].shift(1) * 100).round(1)

    # Create figure with secondary y-axis
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # Add stacked bars for each legislation type
    leg_types = ["Act", "Legislative Instrument", "Notifiable Instrument"]
    for leg_type in leg_types:
        if leg_type not in pivot_counts.columns:
            continue

        # Build hover text
        hover_texts = []
        for year in pivot_counts.index:
            count = int(pivot_counts.loc[year, leg_type])
            titles_list = pivot_titles.loc[year, leg_type] if leg_type in pivot_titles.columns else []
            if isinstance(titles_list, list) and len(titles_list) > 0:
                titles_str = truncate_list(titles_list, 10)
            else:
                titles_str = "No titles"
            hover_texts.append(
                f"<b>{leg_type}</b><br>"
                f"Year: {year}<br>"
                f"Count: {format_number(count)}<br>"
                f"<br>Legislation:<br>{titles_str}"
            )

        fig.add_trace(
            go.Bar(
                name=leg_type,
                x=pivot_counts.index,
                y=pivot_counts[leg_type],
                marker_color=LEG_COLOURS.get(leg_type, "#999"),
                hovertemplate="%{customdata}<extra></extra>",
                customdata=hover_texts,
            ),
            secondary_y=False,
        )

    # Add line for cumulative requirements
    hover_reqs = []
    for _, row in total_reqs.iterrows():
        yoy = format_percentage(row["yoy_pct"]) if pd.notna(row["yoy_pct"]) else "N/A"
        change = format_number(row["yoy_change"]) if pd.notna(row["yoy_change"]) else "N/A"
        hover_reqs.append(
            f"<b>Requirements</b><br>"
            f"Year: {int(row['as_of_year'])}<br>"
            f"Total: {format_number(row['req_count'])}<br>"
            f"YoY Change: {change} ({yoy})"
        )

    fig.add_trace(
        go.Scatter(
            name="Requirements",
            x=total_reqs["as_of_year"],
            y=total_reqs["req_count"],
            mode="lines+markers",
            line=dict(color="#c0392b", width=3),
            marker=dict(size=6),
            hovertemplate="%{customdata}<extra></extra>",
            customdata=hover_reqs,
        ),
        secondary_y=True,
    )

    # Update layout
    fig.update_layout(
        barmode="stack",
        title=dict(
            text=f"Cumulative Legislation and Requirements ({methodology})",
            font=dict(size=16),
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5,
        ),
        hovermode="x unified",
        plot_bgcolor="white",
    )

    fig.update_xaxes(
        title_text="Year",
        showgrid=True,
        gridcolor="#eee",
    )

    fig.update_yaxes(
        title_text="Number of Legislation",
        showgrid=True,
        gridcolor="#eee",
        secondary_y=False,
    )

    fig.update_yaxes(
        title_text="Number of Requirements",
        showgrid=False,
        secondary_y=True,
    )

    return fig


def render_legislation_detail_table(
    df: pd.DataFrame,
    year: int,
    leg_type: str,
    methodology: str = "BC Method"
) -> pd.DataFrame:
    """
    Get legislation details for display in expandable table.

    Args:
        df: Time series DataFrame
        year: Selected year
        leg_type: Selected legislation type
        methodology: Counting methodology

    Returns:
        DataFrame for display
    """
    req_col = "bc_requirements" if methodology == "BC Method" else "regdata_requirements"

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
