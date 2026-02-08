"""
Exploring Regulations in Australia
Main Streamlit application entry point.
"""

import streamlit as st
import pandas as pd

from data.fetch_legislation import (
    load_legislation_base,
    load_legislation_timeseries,
)
from data.fetch_abs import load_economic_indicators, load_industry_stats
from charts.chart_legislation_growth import (
    create_legislation_growth_chart,
    get_legislation_requirements_detail,
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
    page_title="Exploring Regulations in Australia",
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
    industry_stats = load_industry_stats()
    return leg_base, leg_ts, econ, industry_stats

leg_base_df, leg_ts_df, econ_df, industry_stats_df = load_all_data()

# Fixed year range: 2005-2025
MIN_YEAR = 2005
MAX_YEAR = 2025

# --- Sidebar ---
with st.sidebar:
    st.header("Settings")

    year_range = st.slider(
        "Year Range",
        min_value=MIN_YEAR,
        max_value=MAX_YEAR,
        value=(MIN_YEAR, MAX_YEAR),
    )

    with st.expander("About Exploring Regulations in Australia"):
        st.markdown("""
        **Exploring Regulations in Australia** measures the stock of Australian
        federal legislation and the binding requirements within it.

        **Note:** This is a project for a vibe-coding club and has not been
        closely checked. Use with appropriate caution.

        **Data Sources:**
        - Federal Register of Legislation (legislation.gov.au)
        - Australian Bureau of Statistics (economic indicators)

        **Counting Methodologies:**
        - **BC Method**: Counts occurrences of "must", "shall", "required"
          (excluding "must not", "shall not") - based on British Columbia approach
        - **Mercatus Method**: Counts "shall", "must", "may not", "required",
          "prohibited" - based on Mercatus Center RegData methodology

        **Limitations:**
        - Repeal data is not currently incorporated; counts show gross cumulative totals
        - Industry classification is approximate, based on administering department
          and keyword matching
        """)

# --- Header ---
st.title("Exploring Regulations in Australia")
st.markdown("*Assessing the growth in regulations by industry and over time in macroeconomic context*")
st.divider()

# --- Chart 1: Growth in Legislation and Requirements ---
st.header("Growth in the number of primary and secondary legislation in Australia, and related requirements")
st.markdown("""
This chart shows the cumulative count of in-force federal legislation (bars, stacked by primary/secondary)
and the total number of binding requirements within that legislation (line).
""")

if not leg_ts_df.empty:
    # Chart options BELOW the description
    st.subheader("Chart Options")
    col1, col2, col3 = st.columns(3)

    with col1:
        methodology = st.radio(
            "Counting Method",
            ["BC Method", "Mercatus Method"],
            help="BC: counts 'must', 'shall', 'required'. Mercatus: adds 'may not', 'prohibited'.",
            horizontal=True,
            key="chart1_methodology"
        )

    with col2:
        exclude_tco = st.checkbox(
            "Exclude Tariff Concession Orders",
            value=False,
            help="Exclude TCOs from the count (6,541 documents)",
            key="chart1_exclude_tco"
        )

    with col3:
        exclude_aviation = st.checkbox(
            "Exclude Aviation-specific legislation",
            value=False,
            help="Exclude Aviation Airworthiness Directives and related instruments (~9,300 documents)",
            key="chart1_exclude_aviation"
        )

    # Apply filters to the data
    filtered_ts_df = leg_ts_df.copy()
    if exclude_tco:
        filtered_ts_df = filtered_ts_df[~filtered_ts_df["subtype"].str.contains("Tariff Concession", case=False, na=False)]
    if exclude_aviation:
        filtered_ts_df = filtered_ts_df[~filtered_ts_df["subtype"].str.startswith("Aviation", na=False)]

    # Filter to year range
    filtered_ts_df = filtered_ts_df[
        (filtered_ts_df["as_of_year"] >= year_range[0]) &
        (filtered_ts_df["as_of_year"] <= year_range[1])
    ]

    fig1 = create_legislation_growth_chart(
        filtered_ts_df,
        year_start=year_range[0],
        year_end=year_range[1],
        methodology=methodology,
    )
    st.plotly_chart(fig1, width="stretch")

    # Explorer section
    st.subheader("Explore Requirements by Legislation")

    years_available = sorted(filtered_ts_df["as_of_year"].unique())
    if years_available:
        selected_year = st.selectbox(
            "Select year to explore",
            years_available,
            index=len(years_available) - 1,
            key="chart1_year"
        )

        # Get requirements detail, ranked from most to least
        detail_df = get_legislation_requirements_detail(
            filtered_ts_df,
            selected_year,
            methodology
        )

        if not detail_df.empty:
            st.markdown(f"**Legislation in {selected_year}, ranked by requirement count:**")
            st.dataframe(
                detail_df,
                width="stretch",
                hide_index=True,
                height=400
            )

            # Summary stats
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Legislation", f"{len(detail_df):,}")
            with col2:
                st.metric("Total Requirements", f"{detail_df['Requirement Count'].sum():,}")
            with col3:
                avg_reqs = detail_df['Requirement Count'].mean()
                st.metric("Avg Requirements/Legislation", f"{avg_reqs:.1f}")
        else:
            st.info("No legislation found for this selection.")
else:
    st.warning("Legislation data not available. Please ensure data files exist in the output/ directory.")

st.divider()

# --- Chart 2: Regulations by Industry ---
st.header("Chart 2: Regulations by Industry")
st.markdown("""
This chart shows how regulatory requirements are distributed across the 19 ANZSIC
industry divisions, including cross-cutting regulation. Industries are ranked by total requirement count.
""")

if not leg_ts_df.empty:
    # Controls
    col1, col2 = st.columns([1, 2])
    with col1:
        display_year = st.selectbox(
            "Display year",
            sorted(leg_ts_df["as_of_year"].unique(), reverse=True),
            index=0,
            key="chart2_year"
        )
    with col2:
        methodology_c2 = st.radio(
            "Counting Method",
            ["BC Method", "Mercatus Method"],
            horizontal=True,
            key="chart2_methodology"
        )

    fig2 = create_industry_impacts_chart(
        leg_ts_df,
        year=display_year,
        methodology=methodology_c2,
        include_cross_cutting=True,  # Always include cross-cutting
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

        with st.expander(f"Legislation for {get_anzsic_label(selected_industry)}"):
            # Show industry stats at the top
            if not industry_stats_df.empty:
                industry_year_stats = industry_stats_df[
                    (industry_stats_df["anzsic_code"] == selected_industry) &
                    (industry_stats_df["year"] == display_year)
                ]
                if not industry_year_stats.empty:
                    stats_row = industry_year_stats.iloc[0]
                    col1, col2 = st.columns(2)
                    with col1:
                        gva = stats_row.get("gva_millions", 0)
                        st.metric("Gross Value Added", f"${gva:,.0f}M" if pd.notna(gva) else "N/A")
                    with col2:
                        firms = stats_row.get("firm_count", 0)
                        st.metric("Number of Firms", f"{firms:,.0f}" if pd.notna(firms) else "N/A")
                    st.divider()

            # Show legislation detail
            industry_detail = get_industry_detail(
                leg_ts_df, display_year, selected_industry, methodology_c2
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

col1, col2, col3 = st.columns([1, 1, 2])
with col1:
    base_year_3a = st.number_input(
        "Base year (= 100)",
        min_value=year_range[0],
        max_value=year_range[1] - 2,
        value=max(2005, year_range[0]),
        key="chart3a_base"
    )
with col2:
    show_annotations = st.checkbox(
        "Show regulatory events",
        value=False,
        help="Mark key regulatory policy changes on the chart"
    )
with col3:
    methodology_c3 = st.radio(
        "Counting Method",
        ["BC Method", "Mercatus Method"],
        horizontal=True,
        key="chart3_methodology"
    )

if not leg_ts_df.empty:
    fig3a = create_headline_chart(
        leg_ts_df,
        econ_df,
        year_start=year_range[0],
        year_end=year_range[1],
        base_year=int(base_year_3a),
        methodology=methodology_c3,
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
            value=max(2005, year_range[0]),
            key="chart3b_base"
        )

        fig3b = create_industry_chart(
            leg_ts_df,
            econ_df,
            anzsic_code=selected_industry_3b,
            year_start=year_range[0],
            year_end=year_range[1],
            base_year=int(base_year_3b),
            methodology=methodology_c3,
        )
        st.plotly_chart(fig3b, width="stretch")
    else:
        st.info("No industry-level data available.")

# --- Footer ---
st.divider()
st.caption(
    "Data sources: Federal Register of Legislation, Australian Bureau of Statistics. "
    "Methodology based on British Columbia requirements counting and "
    "Mercatus Center RegData approach. "
    "This is a vibe-coding club project - use with caution."
)
