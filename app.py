"""
RegCost: Australia's Regulatory Burden
Main Streamlit application entry point.
"""

import streamlit as st
import pandas as pd

from data.fetch_legislation import (
    load_legislation_base,
    load_legislation_timeseries,
)
from data.fetch_abs import load_economic_indicators
from charts.chart_legislation_growth import (
    create_legislation_growth_chart,
    render_legislation_detail_table,
)
from charts.chart_industry_impacts import (
    create_industry_impacts_chart,
    get_industry_detail,
    get_available_industries,
)
from charts.chart_regulation_vs_economy import (
    create_headline_chart,
    create_industry_chart,
)
from config.anzsic import ANZSIC_DIVISIONS, get_anzsic_label

# Page configuration
st.set_page_config(
    page_title="RegCost: Australia's Regulatory Burden",
    page_icon=":scroll:",
    layout="wide",
)

# --- Load Data ---
@st.cache_data(ttl=3600)
def load_all_data():
    """Load all required datasets."""
    leg_base = load_legislation_base()
    leg_ts = load_legislation_timeseries()
    econ = load_economic_indicators()
    return leg_base, leg_ts, econ

leg_base_df, leg_ts_df, econ_df = load_all_data()

# Determine year range from data
if not leg_ts_df.empty:
    min_year = int(leg_ts_df["as_of_year"].min())
    max_year = int(leg_ts_df["as_of_year"].max())
else:
    min_year, max_year = 2000, 2025

# --- Sidebar ---
with st.sidebar:
    st.header("Settings")

    methodology = st.radio(
        "Counting Methodology",
        ["BC Method", "RegData Method"],
        help="BC: counts 'must', 'shall', 'required'. RegData: adds 'may not', 'prohibited'."
    )

    year_range = st.slider(
        "Year Range",
        min_value=min_year,
        max_value=max_year,
        value=(max(2000, min_year), max_year),
    )

    with st.expander("About RegCost"):
        st.markdown("""
        **RegCost** measures the stock of Australian federal legislation and
        the binding requirements within it.

        **Data Sources:**
        - Federal Register of Legislation (legislation.gov.au)
        - Australian Bureau of Statistics (economic indicators)

        **Methodology:**
        - **BC Method**: Counts occurrences of "must", "shall", "required"
          (excluding "must not", "shall not") - based on British Columbia approach
        - **RegData Method**: Counts "shall", "must", "may not", "required",
          "prohibited" - based on Mercatus Center methodology

        **Limitations:**
        - Repeal data is not currently incorporated; counts show gross cumulative totals
        - Industry classification is approximate, based on administering department
          and keyword matching
        """)

# --- Header ---
st.title("RegCost: Australia's Regulatory Burden")
st.markdown("*Measuring the stock of federal legislative requirements*")
st.divider()

# --- Chart 1: Growth in Legislation and Requirements ---
st.header("Growth in Legislation and Requirements")
st.markdown("""
This chart shows the cumulative count of in-force federal legislation (bars)
and the total number of binding requirements within that legislation (line).
""")

if not leg_ts_df.empty:
    fig1 = create_legislation_growth_chart(
        leg_ts_df,
        year_start=year_range[0],
        year_end=year_range[1],
        methodology=methodology,
    )
    st.plotly_chart(fig1, width="stretch")

    # Detail table selector
    col1, col2 = st.columns(2)
    with col1:
        years_available = sorted(leg_ts_df[
            (leg_ts_df["as_of_year"] >= year_range[0]) &
            (leg_ts_df["as_of_year"] <= year_range[1])
        ]["as_of_year"].unique())
        if years_available:
            selected_year = st.selectbox(
                "Select year for details",
                years_available,
                index=len(years_available) - 1,
                key="chart1_year"
            )
    with col2:
        leg_types = ["Act", "Legislative Instrument", "Notifiable Instrument"]
        selected_type = st.selectbox(
            "Select legislation type",
            leg_types,
            key="chart1_type"
        )

    with st.expander(f"View {selected_type}s in {selected_year}"):
        detail_df = render_legislation_detail_table(
            leg_ts_df, selected_year, selected_type, methodology
        )
        if not detail_df.empty:
            st.dataframe(detail_df, width="stretch", hide_index=True)
        else:
            st.info("No legislation found for this selection.")
else:
    st.warning("Legislation data not available. Please ensure data files exist in the output/ directory.")

st.divider()

# --- Chart 2: Industry Impacts ---
st.header("Industry Impacts")
st.markdown("""
This chart shows how regulatory requirements are distributed across the 19 ANZSIC
industry divisions. Industries are ranked by total requirement count.
""")

if not leg_ts_df.empty:
    # Controls
    col1, col2 = st.columns([1, 3])
    with col1:
        include_cross_cutting = st.checkbox(
            "Include cross-cutting regulation",
            value=True,
            help="Include legislation that applies across all industries (e.g., tax, WHS, corporations law)"
        )
        display_year = st.selectbox(
            "Display year",
            sorted(leg_ts_df["as_of_year"].unique(), reverse=True),
            index=0,
            key="chart2_year"
        )

    fig2 = create_industry_impacts_chart(
        leg_ts_df,
        year=display_year,
        methodology=methodology,
        include_cross_cutting=include_cross_cutting,
    )
    st.plotly_chart(fig2, width="stretch")

    # Industry detail selector
    available_industries = get_available_industries(leg_ts_df, display_year)
    if available_industries:
        selected_industry = st.selectbox(
            "Select industry for details",
            available_industries,
            format_func=lambda x: get_anzsic_label(x),
            key="chart2_industry"
        )

        with st.expander(f"Top legislation for {get_anzsic_label(selected_industry)}"):
            industry_detail = get_industry_detail(
                leg_ts_df, display_year, selected_industry, methodology
            )
            if not industry_detail.empty:
                st.dataframe(industry_detail, width="stretch", hide_index=True)
            else:
                st.info("No legislation found for this industry.")

st.divider()

# --- Chart 3: Regulation vs Economic Performance ---
st.header("Regulation vs Economic Performance")
st.markdown("""
These charts compare the growth trajectory of legislation and requirements against
key economic indicators, all indexed to 100 at a common base year.
""")

# Chart 3a: Headline
st.subheader("Australia - Headline")

col1, col2 = st.columns([1, 3])
with col1:
    base_year_3a = st.number_input(
        "Base year (= 100)",
        min_value=year_range[0],
        max_value=year_range[1] - 2,
        value=max(2000, year_range[0]),
        key="chart3a_base"
    )
    show_annotations = st.checkbox(
        "Show regulatory events",
        value=False,
        help="Mark key regulatory policy changes on the chart"
    )

if not leg_ts_df.empty:
    fig3a = create_headline_chart(
        leg_ts_df,
        econ_df,
        year_start=year_range[0],
        year_end=year_range[1],
        base_year=int(base_year_3a),
        methodology=methodology,
        show_annotations=show_annotations,
    )
    st.plotly_chart(fig3a, width="stretch")

    if econ_df.empty:
        st.info("Economic data not available. Only legislation metrics are shown.")

# Chart 3b: By Industry
st.subheader("By Industry")

col1, col2 = st.columns([1, 3])
with col1:
    # Filter to industries that have data
    industries_with_data = []
    if not econ_df.empty and "anzsic_code" in econ_df.columns:
        industries_with_data = sorted(econ_df["anzsic_code"].dropna().unique().tolist())
    elif not leg_ts_df.empty:
        industries_with_data = sorted(leg_ts_df["anzsic_code"].dropna().unique().tolist())

    if industries_with_data:
        selected_industry_3b = st.selectbox(
            "Select industry",
            industries_with_data,
            format_func=lambda x: get_anzsic_label(x),
            key="chart3b_industry"
        )

        base_year_3b = st.number_input(
            "Base year (= 100)",
            min_value=year_range[0],
            max_value=year_range[1] - 2,
            value=max(2000, year_range[0]),
            key="chart3b_base"
        )

        fig3b = create_industry_chart(
            leg_ts_df,
            econ_df,
            anzsic_code=selected_industry_3b,
            year_start=year_range[0],
            year_end=year_range[1],
            base_year=int(base_year_3b),
            methodology=methodology,
        )
        st.plotly_chart(fig3b, width="stretch")
    else:
        st.info("No industry-level data available.")

# --- Footer ---
st.divider()
st.caption(
    "Data sources: Federal Register of Legislation, Australian Bureau of Statistics. "
    "Methodology based on British Columbia requirements counting and "
    "Mercatus Center RegData approach."
)
