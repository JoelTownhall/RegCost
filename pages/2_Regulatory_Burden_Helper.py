"""
OIA Policy Toolkit — Page 2: Regulatory Burden Helper
Web form replicating the OIA Regulatory Burden Measurement Framework workbook.
"""
import io
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from utils.auth import check_auth, logout
from utils.ai_helper import get_rbmf_helper

st.set_page_config(
    page_title="Regulatory Burden Helper | OIA Policy Toolkit",
    page_icon="💰",
    layout="wide",
)

check_auth()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_TARIFF_WORK = 85.17
DEFAULT_TARIFF_LEISURE = 37.00
DEFAULT_COSTING_PERIOD = 10
STAKEHOLDERS = ["Business", "Individual", "Community organisation"]
COST_TYPES = ["Labour", "Capital / Other"]

# ---------------------------------------------------------------------------
# Session state initialisation
# ---------------------------------------------------------------------------

def _init_state():
    if "rbh_proposal" not in st.session_state:
        st.session_state.rbh_proposal = {
            "title": "", "agency": "", "contact_name": "",
            "contact_email": "", "date": str(date.today()), "description": "",
        }
    if "rbh_costing_period" not in st.session_state:
        st.session_state.rbh_costing_period = DEFAULT_COSTING_PERIOD
    if "rbh_admin" not in st.session_state:
        st.session_state.rbh_admin = _default_admin_df()
    if "rbh_substantive" not in st.session_state:
        st.session_state.rbh_substantive = _default_substantive_df()
    if "rbh_delay" not in st.session_state:
        st.session_state.rbh_delay = _default_delay_df()
    if "rbh_messages" not in st.session_state:
        st.session_state.rbh_messages = []
    if "rbh_chat" not in st.session_state:
        st.session_state.rbh_chat = None
    if "rbh_extraction_result" not in st.session_state:
        st.session_state.rbh_extraction_result = ""

_init_state()

# ---------------------------------------------------------------------------
# Default DataFrames
# ---------------------------------------------------------------------------

def _default_admin_df() -> pd.DataFrame:
    return pd.DataFrame([{
        "Activity description": "",
        "Who": "Business",
        "Entities affected": 100,
        "Frequency / year": 1.0,
        "Hours / activity": 1.0,
        "Hourly tariff ($)": DEFAULT_TARIFF_WORK,
        "Travel cost / activity ($)": 0.0,
    }])


def _default_substantive_df() -> pd.DataFrame:
    return pd.DataFrame([{
        "Activity description": "",
        "Who": "Business",
        "Entities affected": 100,
        "Cost type": "Labour",
        "Frequency / year": 1.0,
        "Hours / activity": 0.0,
        "Hourly tariff ($)": DEFAULT_TARIFF_WORK,
        "Direct cost / entity ($)": 0.0,
    }])


def _default_delay_df() -> pd.DataFrame:
    return pd.DataFrame([{
        "Activity description": "",
        "Who": "Business",
        "Entities affected": 100,
        "Average delay (days)": 30.0,
        "Daily cost / entity ($)": 0.0,
    }])

# ---------------------------------------------------------------------------
# Calculation helpers
# ---------------------------------------------------------------------------

def _calc_admin(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["Cost / entity / year ($)"] = (
        df["Hours / activity"].fillna(0) * df["Hourly tariff ($)"].fillna(0)
        + df["Travel cost / activity ($)"].fillna(0)
    ) * df["Frequency / year"].fillna(0)
    df["Total annual cost ($)"] = df["Cost / entity / year ($)"] * df["Entities affected"].fillna(0)
    return df


def _calc_substantive(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    def row_cost(r):
        if r.get("Cost type", "Labour") == "Labour":
            return (
                r.get("Hours / activity", 0) * r.get("Hourly tariff ($)", 0)
                * r.get("Frequency / year", 0)
                * r.get("Entities affected", 0)
            )
        else:
            return r.get("Direct cost / entity ($)", 0) * r.get("Entities affected", 0)

    df["Total annual cost ($)"] = df.apply(row_cost, axis=1)
    return df


def _calc_delay(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["Total annual cost ($)"] = (
        df["Entities affected"].fillna(0)
        * df["Average delay (days)"].fillna(0)
        * df["Daily cost / entity ($)"].fillna(0)
    )
    return df


def _build_rbe_summary(admin_df, substantive_df, delay_df):
    """
    Build RBE summary dict: {category: {Business, Individuals, Community organisations, Total}}
    Values are in $ millions averaged over costing period.
    """
    period = st.session_state.rbh_costing_period or 10
    # Map display names to session state names
    who_map = {
        "Business": "Business",
        "Individual": "Individuals",
        "Community organisation": "Community organisations",
    }
    summary = {}

    def _aggregate(df, calc_fn, label):
        if df is None or df.empty:
            summary[label] = {"Business": 0, "Individuals": 0, "Community organisations": 0, "Total": 0}
            return
        calc = calc_fn(df)
        by_who = {}
        for _, r in calc.iterrows():
            who_key = who_map.get(r.get("Who", "Business"), "Business")
            by_who[who_key] = by_who.get(who_key, 0) + (r.get("Total annual cost ($)", 0) or 0)
        b = by_who.get("Business", 0) / 1_000_000
        i = by_who.get("Individuals", 0) / 1_000_000
        c = by_who.get("Community organisations", 0) / 1_000_000
        summary[label] = {"Business": b, "Individuals": i, "Community organisations": c, "Total": b + i + c}

    _aggregate(admin_df, _calc_admin, "Administrative costs")
    _aggregate(substantive_df, _calc_substantive, "Substantive compliance costs")
    _aggregate(delay_df, _calc_delay, "Delay costs")
    return summary


def _fmt_m(val: float) -> str:
    if val == 0:
        return "–"
    return f"${val:.3f}m"

# ---------------------------------------------------------------------------
# Text extraction from uploaded file
# ---------------------------------------------------------------------------

def _extract_file_text(uploaded_file) -> str:
    content = uploaded_file.read()
    ext = Path(uploaded_file.name).suffix.lower()
    try:
        if ext == ".pdf":
            import pdfplumber
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                return "\n\n".join(p.extract_text() or "" for p in pdf.pages[:30])
        elif ext in (".doc", ".docx"):
            from docx import Document
            doc = Document(io.BytesIO(content))
            return "\n".join(para.text for para in doc.paragraphs)
        elif ext in (".xlsx", ".xls"):
            df = pd.read_excel(io.BytesIO(content))
            return df.to_string()
    except Exception as e:
        return f"[Could not extract text: {e}]"
    return ""

# ---------------------------------------------------------------------------
# AI assistant initialisation
# ---------------------------------------------------------------------------

def _ensure_rbmf_chat():
    helper = get_rbmf_helper()
    if helper.is_available and st.session_state.rbh_chat is None:
        st.session_state.rbh_chat = helper.start_new_chat()
        st.session_state.rbh_messages = [{
            "role": "assistant",
            "content": (
                "Hi! I'm your Regulatory Burden Measurement Framework assistant. "
                "I can help you:\n"
                "- Classify costs (administrative vs substantive vs delay)\n"
                "- Apply the right tariff rates and methodology\n"
                "- Extract cost data from consultation reports\n\n"
                "Ask me anything, or use the **Upload Consultation Report** section "
                "below to extract data from a document automatically."
            ),
        }]

_ensure_rbmf_chat()

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("### ⚖️ OIA Policy Toolkit")
    st.markdown("---")
    st.page_link("app.py", label="🏠 Home", use_container_width=True)
    st.page_link("pages/1_Impact_Analysis_Helper.py", label="📋 Impact Analysis Helper", use_container_width=True)
    st.page_link("pages/2_Regulatory_Burden_Helper.py", label="💰 Regulatory Burden Helper", use_container_width=True)
    st.page_link("pages/3_Regulatory_Cost_Analysis.py", label="📊 Regulatory Cost Analysis", use_container_width=True)
    st.markdown("---")

    st.markdown("#### Quick Reference")
    st.markdown(f"""
| Tariff | Rate |
|--------|------|
| Work-related | **${DEFAULT_TARIFF_WORK}/hr** |
| Leisure/non-employment | **${DEFAULT_TARIFF_LEISURE}/hr** |

**Costing period:** {st.session_state.rbh_costing_period} years
**Cost categories:**
• Administrative costs
• Substantive compliance costs
• Delay costs
""")
    st.markdown("---")
    if st.button("Log out", use_container_width=True):
        logout()

# ---------------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------------

st.title("💰 Regulatory Burden Helper")
st.markdown(
    "Calculate regulatory costs using the OIA's Regulatory Burden Measurement Framework. "
    "Fill in the sections below — totals update automatically."
)

helper = get_rbmf_helper()
if not helper.is_available:
    st.warning(f"AI assistant not available: {helper.error_message} "
               "The cost calculator still works without AI.", icon="⚠️")

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📋 Proposal Details",
    "💼 Administrative Costs",
    "🏭 Substantive Compliance Costs",
    "⏱️ Delay Costs",
    "📊 Summary & Export",
])

# ── Tab 1: Proposal Details ──────────────────────────────────────────────────
with tab1:
    st.subheader("Proposal Details")
    st.markdown("Enter the basic information about your regulatory proposal.")

    c1, c2 = st.columns(2)
    with c1:
        st.session_state.rbh_proposal["title"] = st.text_input(
            "Proposal title *", value=st.session_state.rbh_proposal["title"],
            placeholder="e.g. Amendments to the Widgets Safety Regulations 2024",
        )
        st.session_state.rbh_proposal["agency"] = st.text_input(
            "Agency / Department", value=st.session_state.rbh_proposal["agency"],
            placeholder="e.g. Department of Industry",
        )
        st.session_state.rbh_proposal["contact_name"] = st.text_input(
            "Contact officer name", value=st.session_state.rbh_proposal["contact_name"],
        )
    with c2:
        st.session_state.rbh_proposal["contact_email"] = st.text_input(
            "Contact email", value=st.session_state.rbh_proposal["contact_email"],
            placeholder="name@agency.gov.au",
        )
        st.session_state.rbh_proposal["date"] = st.date_input(
            "Date", value=date.fromisoformat(st.session_state.rbh_proposal["date"]),
        ).isoformat()
        st.session_state.rbh_costing_period = st.number_input(
            "Costing period (years)",
            min_value=1, max_value=30,
            value=st.session_state.rbh_costing_period,
            help="Default is 10 years per OIA guidance.",
        )

    st.session_state.rbh_proposal["description"] = st.text_area(
        "Brief description of the proposal",
        value=st.session_state.rbh_proposal["description"],
        height=100,
        placeholder="Briefly describe the proposed regulation and who it affects.",
    )

# ── Tab 2: Administrative Costs ──────────────────────────────────────────────
with tab2:
    st.subheader("Administrative Costs")
    st.markdown(
        "**Administrative costs** are costs of demonstrating compliance to government — "
        "form-filling, record-keeping, reporting, registrations, licences, inspections. "
        "These do **not** change what the entity actually does."
    )
    st.caption(f"Default hourly tariff: ${DEFAULT_TARIFF_WORK}/hr (work-related) | ${DEFAULT_TARIFF_LEISURE}/hr (leisure/non-employment)")

    edited_admin = st.data_editor(
        st.session_state.rbh_admin,
        column_config={
            "Activity description": st.column_config.TextColumn("Activity description", width="large"),
            "Who": st.column_config.SelectboxColumn("Who", options=STAKEHOLDERS, width="medium"),
            "Entities affected": st.column_config.NumberColumn("Entities affected", min_value=0, format="%d"),
            "Frequency / year": st.column_config.NumberColumn("Frequency / year", min_value=0, format="%.1f"),
            "Hours / activity": st.column_config.NumberColumn("Hours / activity", min_value=0, format="%.2f"),
            "Hourly tariff ($)": st.column_config.NumberColumn("Hourly tariff ($)", min_value=0, format="$%.2f"),
            "Travel cost / activity ($)": st.column_config.NumberColumn("Travel cost ($)", min_value=0, format="$%.2f"),
        },
        num_rows="dynamic",
        use_container_width=True,
        key="admin_editor",
    )
    st.session_state.rbh_admin = edited_admin

    # Show calculated totals
    if not edited_admin.empty:
        calc_admin = _calc_admin(edited_admin)
        display_cols = [
            "Activity description", "Who", "Entities affected",
            "Cost / entity / year ($)", "Total annual cost ($)"
        ]
        st.markdown("**Calculated totals:**")
        st.dataframe(
            calc_admin[display_cols].style.format({
                "Cost / entity / year ($)": "${:,.2f}",
                "Total annual cost ($)": "${:,.2f}",
            }),
            use_container_width=True, hide_index=True,
        )
        total = calc_admin["Total annual cost ($)"].sum()
        st.metric("Total administrative costs (annual)", f"${total:,.2f}")

# ── Tab 3: Substantive Compliance Costs ──────────────────────────────────────
with tab3:
    st.subheader("Substantive Compliance Costs")
    st.markdown(
        "**Substantive compliance costs** are real changes to entity operations caused by the regulation — "
        "capital investment, hiring staff, changing processes, purchasing equipment. "
        "These change what the entity actually does."
    )

    edited_sub = st.data_editor(
        st.session_state.rbh_substantive,
        column_config={
            "Activity description": st.column_config.TextColumn("Activity description", width="large"),
            "Who": st.column_config.SelectboxColumn("Who", options=STAKEHOLDERS, width="medium"),
            "Entities affected": st.column_config.NumberColumn("Entities affected", min_value=0, format="%d"),
            "Cost type": st.column_config.SelectboxColumn("Cost type", options=COST_TYPES),
            "Frequency / year": st.column_config.NumberColumn("Frequency / year", min_value=0, format="%.1f",
                help="For Labour costs only"),
            "Hours / activity": st.column_config.NumberColumn("Hours / activity", min_value=0, format="%.2f",
                help="For Labour costs only"),
            "Hourly tariff ($)": st.column_config.NumberColumn("Hourly tariff ($)", min_value=0, format="$%.2f",
                help="For Labour costs only"),
            "Direct cost / entity ($)": st.column_config.NumberColumn("Direct cost / entity ($)", min_value=0,
                format="$%.2f", help="For Capital / Other costs only"),
        },
        num_rows="dynamic",
        use_container_width=True,
        key="substantive_editor",
    )
    st.session_state.rbh_substantive = edited_sub

    if not edited_sub.empty:
        calc_sub = _calc_substantive(edited_sub)
        st.markdown("**Calculated totals:**")
        st.dataframe(
            calc_sub[["Activity description", "Who", "Cost type", "Entities affected", "Total annual cost ($)"]
            ].style.format({"Total annual cost ($)": "${:,.2f}"}),
            use_container_width=True, hide_index=True,
        )
        total = calc_sub["Total annual cost ($)"].sum()
        st.metric("Total substantive compliance costs (annual)", f"${total:,.2f}")

# ── Tab 4: Delay Costs ───────────────────────────────────────────────────────
with tab4:
    st.subheader("Delay Costs")
    st.markdown(
        "**Delay costs** are costs imposed by government-imposed waiting periods — "
        "e.g. waiting for a licence, permit, or regulatory approval before commencing activity."
    )

    edited_delay = st.data_editor(
        st.session_state.rbh_delay,
        column_config={
            "Activity description": st.column_config.TextColumn("Activity description", width="large"),
            "Who": st.column_config.SelectboxColumn("Who", options=STAKEHOLDERS),
            "Entities affected": st.column_config.NumberColumn("Entities affected", min_value=0, format="%d"),
            "Average delay (days)": st.column_config.NumberColumn("Avg delay (days)", min_value=0, format="%.0f"),
            "Daily cost / entity ($)": st.column_config.NumberColumn("Daily cost / entity ($)", min_value=0,
                format="$%.2f", help="Estimated daily revenue or opportunity cost per entity"),
        },
        num_rows="dynamic",
        use_container_width=True,
        key="delay_editor",
    )
    st.session_state.rbh_delay = edited_delay

    if not edited_delay.empty:
        calc_delay = _calc_delay(edited_delay)
        st.markdown("**Calculated totals:**")
        st.dataframe(
            calc_delay[["Activity description", "Who", "Entities affected",
                         "Average delay (days)", "Total annual cost ($)"]
            ].style.format({"Total annual cost ($)": "${:,.2f}"}),
            use_container_width=True, hide_index=True,
        )
        total = calc_delay["Total annual cost ($)"].sum()
        st.metric("Total delay costs (annual)", f"${total:,.2f}")

# ── Tab 5: Summary & Export ───────────────────────────────────────────────────
with tab5:
    st.subheader("Regulatory Burden Estimate (RBE) Table")
    st.markdown(
        f"Average annual regulatory costs over the {st.session_state.rbh_costing_period}-year "
        "costing period, in real terms."
    )

    rbe = _build_rbe_summary(
        st.session_state.rbh_admin,
        st.session_state.rbh_substantive,
        st.session_state.rbh_delay,
    )

    # Build display DataFrame
    cats = ["Administrative costs", "Substantive compliance costs", "Delay costs"]
    stakeholder_cols = ["Business", "Individuals", "Community organisations", "Total"]
    rbe_rows = []
    for cat in cats:
        d = rbe.get(cat, {})
        rbe_rows.append({
            "Cost category": cat,
            **{k: _fmt_m(d.get(k, 0)) for k in stakeholder_cols},
        })
    # Total row
    totals = {}
    for s in stakeholder_cols:
        totals[s] = sum(rbe.get(c, {}).get(s, 0) for c in cats)
    rbe_rows.append({
        "Cost category": "**Total**",
        **{k: _fmt_m(totals[k]) for k in stakeholder_cols},
    })
    rbe_df = pd.DataFrame(rbe_rows)

    st.dataframe(rbe_df, use_container_width=True, hide_index=True)

    # Grand total callout
    grand = totals.get("Total", 0)
    if grand > 0:
        st.success(f"**Estimated total annual regulatory burden: ${grand:.3f}m** "
                   f"(${grand * st.session_state.rbh_costing_period:.2f}m over "
                   f"{st.session_state.rbh_costing_period} years)")

    st.divider()
    st.subheader("Finalise and Export")

    col_pdf, col_csv = st.columns(2)

    with col_pdf:
        st.markdown("**📄 Finalise and Save — a copy of report and underlying data goes to OIA**")
        if st.button("Generate PDF Report", type="primary", use_container_width=True):
            if not st.session_state.rbh_proposal.get("title"):
                st.error("Please enter a proposal title in the Proposal Details tab first.")
            else:
                with st.spinner("Generating PDF…"):
                    try:
                        from utils.pdf_generator import generate_rbe_report_pdf
                        # Build display versions with calculated columns
                        admin_out = _calc_admin(st.session_state.rbh_admin) if not st.session_state.rbh_admin.empty else st.session_state.rbh_admin
                        sub_out = _calc_substantive(st.session_state.rbh_substantive) if not st.session_state.rbh_substantive.empty else st.session_state.rbh_substantive
                        delay_out = _calc_delay(st.session_state.rbh_delay) if not st.session_state.rbh_delay.empty else st.session_state.rbh_delay

                        pdf_bytes = generate_rbe_report_pdf(
                            proposal=st.session_state.rbh_proposal,
                            admin_df=admin_out,
                            substantive_df=sub_out,
                            delay_df=delay_out,
                            rbe_summary=rbe,
                            costing_period=st.session_state.rbh_costing_period,
                        )
                        title_slug = (
                            st.session_state.rbh_proposal["title"][:40]
                            .replace(" ", "_").replace("/", "-")
                        )
                        st.download_button(
                            label="⬇️ Download PDF Report",
                            data=pdf_bytes,
                            file_name=f"RBE_Report_{title_slug}.pdf",
                            mime="application/pdf",
                            use_container_width=True,
                        )
                    except Exception as e:
                        st.error(f"PDF generation failed: {e}")

    with col_csv:
        st.markdown("**📊 Download underlying data as CSV**")
        if st.button("Prepare CSV Export", use_container_width=True):
            admin_out = _calc_admin(st.session_state.rbh_admin)
            sub_out = _calc_substantive(st.session_state.rbh_substantive)
            delay_out = _calc_delay(st.session_state.rbh_delay)

            admin_out["Cost category"] = "Administrative"
            sub_out["Cost category"] = "Substantive compliance"
            delay_out["Cost category"] = "Delay"

            all_costs = pd.concat([admin_out, sub_out, delay_out], ignore_index=True)
            csv_bytes = all_costs.to_csv(index=False).encode()
            st.download_button(
                label="⬇️ Download CSV",
                data=csv_bytes,
                file_name="RBE_Data.csv",
                mime="text/csv",
                use_container_width=True,
            )

# ---------------------------------------------------------------------------
# AI Assistant (below tabs, always visible)
# ---------------------------------------------------------------------------

st.divider()

with st.expander("🤖 AI Framework Assistant", expanded=False):
    ai_tab1, ai_tab2 = st.tabs(["💬 Ask a question", "📎 Upload consultation report"])

    with ai_tab1:
        st.markdown(
            "Ask anything about the Regulatory Burden Measurement Framework — "
            "cost classification, tariff rates, methodology, or how to handle specific situations."
        )

        for msg in st.session_state.rbh_messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        user_q = st.chat_input("Ask about the RBMF…", key="rbh_chat_input")
        if user_q:
            st.session_state.rbh_messages.append({"role": "user", "content": user_q})
            with st.chat_message("user"):
                st.markdown(user_q)

            if helper.is_available and st.session_state.rbh_chat is not None:
                with st.chat_message("assistant"):
                    placeholder = st.empty()
                    full = ""
                    try:
                        response = helper.send_message(st.session_state.rbh_chat, user_q)
                        for chunk in response:
                            if chunk.text:
                                full += chunk.text
                                placeholder.markdown(full + "▌")
                        placeholder.markdown(full)
                    except Exception as e:
                        full = f"⚠️ Error: {e}"
                        placeholder.error(full)
                    st.session_state.rbh_messages.append({"role": "assistant", "content": full})
            else:
                with st.chat_message("assistant"):
                    msg = "⚠️ AI not available — check your API key."
                    st.warning(msg)
                    st.session_state.rbh_messages.append({"role": "assistant", "content": msg})
            st.rerun()

    with ai_tab2:
        st.markdown(
            "Upload a consultation report, RIS, or stakeholder submission. "
            "The AI will extract quantitative cost data and suggest values to populate the form above."
        )

        uploaded = st.file_uploader(
            "Upload file (PDF, DOCX, XLSX)",
            type=["pdf", "doc", "docx", "xlsx"],
            key="rbh_upload",
        )

        if uploaded and st.button("Extract cost data with AI", type="primary"):
            if not helper.is_available:
                st.error("AI not available — check API key.")
            else:
                with st.spinner("Extracting text and analysing…"):
                    doc_text = _extract_file_text(uploaded)
                    if not doc_text.strip():
                        st.error("Could not extract text from this file.")
                    else:
                        extraction_prompt = f"""I have uploaded a consultation report. Please extract any quantitative data relevant to the Regulatory Burden Measurement Framework.

Document text (first 8000 chars):
---
{doc_text[:8000]}
---

Please:
1. Extract all mentions of: hours to comply, wage rates, number of affected entities, frequency of compliance activities, capital costs, equipment costs, delays
2. Present extracted data in a clear table with columns: Item | Value | Source quote | Suggested RBMF field
3. Note any assumptions or uncertainties
4. Suggest which cost category (Administrative / Substantive compliance / Delay) each item belongs to
5. Flag any data gaps that the user should follow up on"""

                        # Use a fresh one-shot request (don't pollute the chat history)
                        one_off_chat = helper.start_new_chat()
                        full = ""
                        try:
                            response = helper.send_message(one_off_chat, extraction_prompt)
                            for chunk in response:
                                if chunk.text:
                                    full += chunk.text
                        except Exception as e:
                            full = f"⚠️ Extraction failed: {e}"
                        st.session_state.rbh_extraction_result = full

        if st.session_state.rbh_extraction_result:
            st.markdown("### Extracted Data")
            st.markdown(st.session_state.rbh_extraction_result)
            st.info(
                "Review the extracted data above, then manually enter the relevant values "
                "into the cost tables in the tabs above.",
                icon="ℹ️",
            )
            if st.button("Clear extraction results"):
                st.session_state.rbh_extraction_result = ""
                st.rerun()
