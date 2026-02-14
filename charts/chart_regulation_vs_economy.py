"""Chart 3: Regulation vs Economic Performance."""

import plotly.graph_objects as go
import pandas as pd
import streamlit as st

from config.colours import MACRO_COLOURS, ACCESSIBLE_PALETTE
from config.annotations import get_event_annotations, get_vline_shapes
from config.anzsic import ANZSIC_DIVISIONS
from utils.helpers import format_number


def create_headline_chart(
    leg_df: pd.DataFrame,
    econ_df: pd.DataFrame,
    year_start: int,
    year_end: int,
    base_year: int,
    methodology: str = "BC Method",
) -> go.Figure:
    """
    Create indexed line chart comparing regulation growth to economic indicators.

    Args:
        leg_df: Time series DataFrame with legislation data
        econ_df: Economic indicators DataFrame
        year_start: Start year for display
        year_end: End year for display
        base_year: Year to use as index base (= 100)
        methodology: "BC Method" or "RegData Method"

    Returns:
        Plotly Figure object
    """
    # Handle methodology name variations
    if methodology in ["Mercatus Method", "RegData Method"]:
        req_col = "regdata_requirements"
    else:
        req_col = "bc_requirements"

    # Aggregate legislation data by year
    leg_by_year = leg_df[
        (leg_df["as_of_year"] >= year_start) &
        (leg_df["as_of_year"] <= year_end)
    ].groupby("as_of_year").agg(
        leg_count=("register_id", "count"),
        req_count=(req_col, "sum")
    ).reset_index()
    leg_by_year.rename(columns={"as_of_year": "year"}, inplace=True)

    # Get economic indicators (aggregate across industries)
    if not econ_df.empty and "anzsic_code" in econ_df.columns:
        econ_total = econ_df.groupby("year").agg({
            "gva_millions": "sum",
            "hours_worked_millions": "sum",
        }).reset_index()
        econ_total["productivity"] = econ_total["gva_millions"] / econ_total["hours_worked_millions"]
    else:
        econ_total = pd.DataFrame(columns=["year", "gva_millions", "productivity"])

    # Merge datasets
    combined = leg_by_year.merge(econ_total, on="year", how="outer")
    combined = combined.sort_values("year")
    combined = combined[(combined["year"] >= year_start) & (combined["year"] <= year_end)]

    if combined.empty:
        fig = go.Figure()
        fig.add_annotation(text="No data available for selected year range",
                          xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        return fig

    # Index to base year
    combined = index_to_base(combined, base_year, [
        "leg_count", "req_count", "gva_millions", "productivity"
    ])

    # Create figure
    fig = go.Figure()

    # Define series to plot: Legislation, Requirements, GVA, GVA per hour
    series_config = [
        ("leg_count_idx", "Legislation Count", MACRO_COLOURS.get("Legislation", "#1f77b4")),
        ("req_count_idx", "Requirements Count", MACRO_COLOURS.get("Requirements", "#ff7f0e")),
        ("gva_millions_idx", "Real GVA", MACRO_COLOURS.get("Real GDP", "#2ca02c")),
        ("productivity_idx", "GVA per hour worked", MACRO_COLOURS.get("Productivity", "#9467bd")),
    ]

    for col, name, color in series_config:
        if col not in combined.columns:
            continue

        # Build hover text
        hover_texts = []
        for _, row in combined.iterrows():
            idx_val = row.get(col, None)
            raw_col = col.replace("_idx", "")
            raw_val = row.get(raw_col, None)
            if pd.notna(idx_val):
                hover_texts.append(
                    f"<b>{name}</b><br>"
                    f"Year: {int(row['year'])}<br>"
                    f"Index: {idx_val:.1f}<br>"
                    f"Value: {format_number(raw_val) if pd.notna(raw_val) else 'N/A'}"
                )
            else:
                hover_texts.append(f"<b>{name}</b><br>Year: {int(row['year'])}<br>No data")

        fig.add_trace(go.Scatter(
            x=combined["year"],
            y=combined[col],
            mode="lines+markers",
            name=name,
            line=dict(color=color, width=2),
            marker=dict(size=5),
            hovertemplate="%{customdata}<extra></extra>",
            customdata=hover_texts,
        ))

    # Add reference line at 100
    fig.add_hline(y=100, line_dash="dash", line_color="#ccc", annotation_text=f"Base year ({base_year})")

    # Always show COVID response annotation
    fig.add_vline(
        x=2020,
        line_dash="dash",
        line_color="#999",
        annotation_text="COVID response",
        annotation_position="top",
        annotation_font=dict(size=10, color="#666"),
    )

    # Update layout
    fig.update_layout(
        title=dict(
            text=f"Regulation in a Macro Economic Context (Indexed to {base_year} = 100)",
            font=dict(size=16),
        ),
        xaxis_title="Year",
        yaxis_title="Index (Base Year = 100)",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5,
        ),
        hovermode="x unified",
        plot_bgcolor="white",
        margin=dict(l=20, r=20, t=60, b=20),
    )

    fig.update_xaxes(showgrid=True, gridcolor="#eee", fixedrange=True)
    fig.update_yaxes(showgrid=True, gridcolor="#eee", automargin=True, fixedrange=True)

    return fig


def create_industry_chart(
    leg_df: pd.DataFrame,
    econ_df: pd.DataFrame,
    anzsic_code: str,
    year_start: int,
    year_end: int,
    base_year: int,
    methodology: str = "BC Method"
) -> go.Figure:
    """
    Create indexed line chart for a specific industry.

    Args:
        leg_df: Time series DataFrame with legislation data
        econ_df: Economic indicators DataFrame
        anzsic_code: ANZSIC division code
        year_start: Start year
        year_end: End year
        base_year: Index base year
        methodology: Counting methodology

    Returns:
        Plotly Figure object
    """
    # Handle methodology name variations
    if methodology in ["Mercatus Method", "RegData Method"]:
        req_col = "regdata_requirements"
    else:
        req_col = "bc_requirements"
    industry_name = ANZSIC_DIVISIONS.get(anzsic_code, "Unknown")

    # Get industry legislation and requirements by year
    industry_leg = leg_df[
        (leg_df["anzsic_code"] == anzsic_code) &
        (leg_df["as_of_year"] >= year_start) &
        (leg_df["as_of_year"] <= year_end)
    ].groupby("as_of_year").agg(
        leg_count=("register_id", "count"),
        req_count=(req_col, "sum")
    ).reset_index()
    industry_leg.rename(columns={"as_of_year": "year"}, inplace=True)

    # Get industry economic data
    industry_econ = econ_df[
        (econ_df["anzsic_code"] == anzsic_code) &
        (econ_df["year"] >= year_start) &
        (econ_df["year"] <= year_end)
    ][["year", "gva_millions", "hours_worked_millions"]].copy()

    # Calculate productivity (GVA per hour worked)
    if "hours_worked_millions" in industry_econ.columns and "gva_millions" in industry_econ.columns:
        industry_econ["productivity"] = industry_econ["gva_millions"] / industry_econ["hours_worked_millions"]

    # Merge
    combined = industry_leg.merge(industry_econ, on="year", how="outer")
    combined = combined.sort_values("year")

    if combined.empty:
        fig = go.Figure()
        fig.add_annotation(text=f"No data available for {industry_name}",
                          xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        return fig

    # Index to base year
    combined = index_to_base(combined, base_year, [
        "leg_count", "req_count", "gva_millions", "productivity"
    ])

    # Create figure
    fig = go.Figure()

    series_config = [
        ("leg_count_idx", "Legislation Count", ACCESSIBLE_PALETTE[0]),
        ("req_count_idx", "Requirements Count", ACCESSIBLE_PALETTE[1]),
        ("gva_millions_idx", "Industry GVA", ACCESSIBLE_PALETTE[2]),
        ("productivity_idx", "GVA per hour worked", ACCESSIBLE_PALETTE[3]),
    ]

    for col, name, color in series_config:
        if col not in combined.columns:
            continue

        fig.add_trace(go.Scatter(
            x=combined["year"],
            y=combined[col],
            mode="lines+markers",
            name=name,
            line=dict(color=color, width=2),
            marker=dict(size=5),
        ))

    # Add reference line
    fig.add_hline(y=100, line_dash="dash", line_color="#ccc")

    # Always show COVID response annotation
    fig.add_vline(
        x=2020,
        line_dash="dash",
        line_color="#999",
        annotation_text="COVID response",
        annotation_position="top",
        annotation_font=dict(size=10, color="#666"),
    )

    fig.update_layout(
        title=dict(
            text=f"{anzsic_code}: {industry_name} - Macro Context (Indexed to {base_year} = 100)",
            font=dict(size=16),
        ),
        xaxis_title="Year",
        yaxis_title="Index (Base Year = 100)",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5,
        ),
        hovermode="x unified",
        plot_bgcolor="white",
        margin=dict(l=20, r=20, t=60, b=20),
    )

    fig.update_xaxes(showgrid=True, gridcolor="#eee", fixedrange=True)
    fig.update_yaxes(showgrid=True, gridcolor="#eee", automargin=True, fixedrange=True)

    return fig


def create_regulation_vs_productivity_scatter(
    leg_df: pd.DataFrame,
    econ_df: pd.DataFrame,
    year_start: int = 2010,
    year_end: int = 2024,
    methodology: str = "BC Method",
) -> go.Figure:
    """
    Create scatter plot: % change in requirements vs % change in GVA per hour worked.
    Each point is an industry.
    """
    if methodology in ["Mercatus Method", "RegData Method"]:
        req_col = "regdata_requirements"
    else:
        req_col = "bc_requirements"

    # Get requirements by industry for start and end years
    def get_industry_reqs(df, year):
        return df[df["as_of_year"] == year].groupby("anzsic_code").agg(
            req_count=(req_col, "sum")
        ).reset_index()

    reqs_start = get_industry_reqs(leg_df, year_start)
    reqs_end = get_industry_reqs(leg_df, year_end)

    reqs = reqs_start.merge(reqs_end, on="anzsic_code", suffixes=("_start", "_end"))
    reqs["req_pct_change"] = ((reqs["req_count_end"] - reqs["req_count_start"]) / reqs["req_count_start"] * 100)

    # Get GVA per hour worked by industry for start and end years
    def get_industry_productivity(df, year):
        yr = df[df["year"] == year][["anzsic_code", "gva_millions", "hours_worked_millions"]].copy()
        yr["productivity"] = yr["gva_millions"] / yr["hours_worked_millions"]
        return yr[["anzsic_code", "productivity"]]

    prod_start = get_industry_productivity(econ_df, year_start)
    prod_end = get_industry_productivity(econ_df, year_end)

    prod = prod_start.merge(prod_end, on="anzsic_code", suffixes=("_start", "_end"))
    prod["prod_pct_change"] = ((prod["productivity_end"] - prod["productivity_start"]) / prod["productivity_start"] * 100)

    # Merge
    combined = reqs.merge(prod, on="anzsic_code")
    combined["anzsic_name"] = combined["anzsic_code"].map(ANZSIC_DIVISIONS)

    if combined.empty:
        fig = go.Figure()
        fig.add_annotation(text="No data available",
                          xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        return fig

    # Build hover text
    hover_texts = []
    for _, row in combined.iterrows():
        hover_texts.append(
            f"<b>{row['anzsic_code']}: {row['anzsic_name']}</b><br>"
            f"Requirements change: {row['req_pct_change']:+.1f}%<br>"
            f"GVA/hour change: {row['prod_pct_change']:+.1f}%"
        )

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=combined["req_pct_change"],
        y=combined["prod_pct_change"],
        mode="markers+text",
        text=combined["anzsic_code"],
        textposition="top center",
        textfont=dict(size=10),
        marker=dict(
            size=12,
            color=ACCESSIBLE_PALETTE[0],
            opacity=0.8,
        ),
        hovertemplate="%{customdata}<extra></extra>",
        customdata=hover_texts,
    ))

    # Add reference lines at 0
    fig.add_hline(y=0, line_dash="dash", line_color="#ccc")
    fig.add_vline(x=0, line_dash="dash", line_color="#ccc")

    fig.update_layout(
        title=dict(
            text=f"Regulation Growth vs Productivity Growth ({year_start}-{year_end})",
            font=dict(size=16),
        ),
        xaxis_title=f"Change in Requirements (%, {year_start}-{year_end})",
        yaxis_title=f"Change in GVA per Hour Worked (%, {year_start}-{year_end})",
        plot_bgcolor="white",
        hovermode="closest",
        showlegend=False,
        margin=dict(l=20, r=20, t=60, b=20),
    )

    fig.update_xaxes(showgrid=True, gridcolor="#eee", fixedrange=True, automargin=True)
    fig.update_yaxes(showgrid=True, gridcolor="#eee", fixedrange=True, automargin=True)

    return fig


def index_to_base(df: pd.DataFrame, base_year: int, columns: list) -> pd.DataFrame:
    """Index specified columns to 100 at base year."""
    result = df.copy()

    for col in columns:
        if col not in df.columns:
            continue

        base_row = df[df["year"] == base_year]
        if base_row.empty:
            # Use first year with data as fallback
            valid_rows = df[df[col].notna()]
            if valid_rows.empty:
                continue
            base_row = valid_rows.iloc[[0]]

        base_value = base_row[col].iloc[0]
        if pd.isna(base_value) or base_value == 0:
            continue

        result[f"{col}_idx"] = (df[col] / base_value * 100).round(1)

    return result
