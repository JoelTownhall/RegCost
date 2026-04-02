"""
OIA Policy Toolkit — Landing Page and Entry Point.
"""
import streamlit as st
from utils.auth import check_auth, logout
from utils.styles import apply_custom_css

st.set_page_config(
    page_title="OIA Policy Toolkit",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

check_auth()
apply_custom_css()

# --- Sidebar ---
with st.sidebar:
    st.markdown("### ⚖️ OIA Policy Toolkit")
    st.markdown("---")
    st.page_link("app.py", label="🏠 Home", use_container_width=True)
    st.page_link("pages/1_Impact_Analysis_Helper.py", label="📋 Impact Analysis Helper", use_container_width=True)
    st.page_link("pages/2_Regulatory_Burden_Helper.py", label="💰 Regulatory Burden Helper", use_container_width=True)
    st.page_link("pages/3_Regulatory_Cost_Analysis.py", label="📊 Regulatory Cost Analysis", use_container_width=True)
    st.markdown("---")
    if st.button("Log out", use_container_width=True):
        logout()

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
    <h1>⚖️ OIA Policy Toolkit</h1>
    <p>AI-powered tools to help Australian Public Service policy officers with Impact Analysis
    and regulatory burden assessment under the Australian Government's Impact Analysis Framework.</p>
</div>
""", unsafe_allow_html=True)

# --- Three tool cards ---
col1, col2, col3 = st.columns(3, gap="large")

with col1:
    st.markdown("""
    <div class="tool-card">
        <h3>📋 Impact Analysis Helper</h3>
        <p>Get AI-guided help writing your Impact Analysis, step by step through the 7 IA questions.
        Draws on the OIA's Impact Analysis Framework and corpus of published IAs to give contextual,
        expert guidance tailored to your proposal.</p>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    st.page_link(
        "pages/1_Impact_Analysis_Helper.py",
        label="Open Impact Analysis Helper →",
        use_container_width=True,
    )

with col2:
    st.markdown("""
    <div class="tool-card">
        <h3>💰 Regulatory Burden Helper</h3>
        <p>Calculate regulatory costs interactively using the OIA's Regulatory Burden Measurement
        Framework. Replaces the Excel workbook with a web form that auto-calculates totals and
        generates a formatted PDF report.</p>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    st.page_link(
        "pages/2_Regulatory_Burden_Helper.py",
        label="Open Regulatory Burden Helper →",
        use_container_width=True,
    )

with col3:
    st.markdown("""
    <div class="tool-card">
        <h3>📊 Regulatory Cost Analysis</h3>
        <p>Explore trends in Australia's regulatory burden with interactive charts. Track the
        growth of federal legislation by industry over time and see how it compares to
        key economic indicators.</p>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    st.page_link(
        "pages/3_Regulatory_Cost_Analysis.py",
        label="Open Regulatory Cost Analysis →",
        use_container_width=True,
    )

# --- Footer ---
st.markdown("<br>", unsafe_allow_html=True)
st.divider()
st.caption(
    "OIA Policy Toolkit | Office of Impact Analysis, Department of the Prime Minister and Cabinet | "
    "helpdesk-OIA@pmc.gov.au | 02 6271 6270"
)
