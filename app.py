"""
RegCost — Landing Page
"""
import streamlit as st
from utils.styles import apply_custom_css

st.set_page_config(
    page_title="RegCost — Australian Regulatory Analysis",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

apply_custom_css()

# --- Sidebar ---
with st.sidebar:
    st.markdown("### 📊 RegCost")
    st.markdown("---")
    st.page_link("app.py", label="🏠 Home", use_container_width=True)
    st.page_link("pages/3_Regulatory_Cost_Analysis.py", label="📊 Regulatory Cost Analysis", use_container_width=True)
    st.page_link("pages/4_Data.py", label="📈 Economic Data", use_container_width=True)

# --- Hero ---
st.markdown("""
    <style>
    .hero-banner {
        background: linear-gradient(135deg, #1f4e79 0%, #2e75b6 100%);
        color: white;
        padding: 48px 40px;
        border-radius: 12px;
        margin-bottom: 32px;
    }
    .hero-banner h1 { color: white; margin-bottom: 8px; font-size: 2.4rem; }
    .hero-banner p { color: rgba(255,255,255,0.85); font-size: 1.05rem; margin: 0; }

    .tool-card {
        border: 1px solid #dce3ea;
        border-radius: 10px;
        padding: 28px 24px;
        background: white;
        height: 100%;
        transition: box-shadow 0.2s;
    }
    .tool-card:hover { box-shadow: 0 4px 16px rgba(31,78,121,0.12); }
    .tool-card h3 { color: #1f4e79; margin-bottom: 12px; }
    .tool-card p { color: #444; font-size: 0.9rem; line-height: 1.5; }
    </style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hero-banner">
    <h1>📊 RegCost</h1>
    <p>Interactive tools for exploring Australia's federal regulatory landscape —
    tracking the stock of legislation, regulatory requirements, and economic context
    by industry over time.</p>
</div>
""", unsafe_allow_html=True)

col1, col2 = st.columns(2, gap="large")

with col1:
    st.markdown("""
    <div class="tool-card">
        <h3>📊 Regulatory Cost Analysis</h3>
        <p>Explore trends in Australia's regulatory burden with interactive charts.
        Track the growth of federal legislation and requirements by industry over time
        and compare against key economic indicators.</p>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    st.page_link(
        "pages/3_Regulatory_Cost_Analysis.py",
        label="Open Regulatory Cost Analysis →",
        use_container_width=True,
    )

with col2:
    st.markdown("""
    <div class="tool-card">
        <h3>📈 Economic Data</h3>
        <p>Explore ABS business counts, firm survival rates, employment distribution,
        and wage share data by ANZSIC industry division and subdivision.</p>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    st.page_link(
        "pages/4_Data.py",
        label="Open Economic Data →",
        use_container_width=True,
    )

st.markdown("<br>", unsafe_allow_html=True)
st.divider()
st.caption(
    "RegCost | Data sources: Federal Register of Legislation, Australian Bureau of Statistics"
)
