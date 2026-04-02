"""
IALA Policy Toolkit — Page 1: Impact Analysis Helper
AI-guided assistant for writing Impact Analyses through the 7 IA questions.
"""
import streamlit as st

from utils.auth import check_auth, logout
from utils.ai_helper import (
    IA_QUESTIONS,
    IA_QUESTION_SHORT,
    RATING_CONFIG,
    get_gemini_helper,
    build_ia_index,
)
from utils.pirates import render_pirate_robot

st.set_page_config(
    page_title="Impact Analysis Helper | IALA Policy Toolkit",
    page_icon="📋",
    layout="wide",
)

check_auth()

# ---------------------------------------------------------------------------
# Session state initialisation
# ---------------------------------------------------------------------------

def _init_state():
    defaults = {
        "ia_messages": [],       # [{role, content}]
        "ia_chat": None,         # genai.ChatSession
        "ia_started": False,
        "ia_proposal": "",
        "ia_current_q": 1,       # 1–7
        "ia_q_complete": {i: False for i in range(1, 8)},
        "ia_generating_draft": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()

# ---------------------------------------------------------------------------
# Helper: start / reset conversation
# ---------------------------------------------------------------------------

def _start_new_ia():
    helper = get_gemini_helper()
    st.session_state.ia_chat = helper.start_new_chat()
    st.session_state.ia_messages = []
    st.session_state.ia_started = False
    st.session_state.ia_proposal = ""
    st.session_state.ia_current_q = 1
    st.session_state.ia_q_complete = {i: False for i in range(1, 8)}

    if helper.is_available:
        greeting = (
            "Ahoy! I'm your Impact Analysis assistant from the Impact Analysis Lord Admiralty. "
            "I'll guide you step by step through the 7 IALA Impact Analysis questions.\n\n"
            "To get started: **what policy proposal are you working on?** Give me a brief "
            "description — the problem you're trying to solve, roughly which agency is leading it, "
            "and whether it involves any regulation. I'll then help you work out the appropriate "
            "depth of analysis and begin drafting your IA. ⚓"
        )
    else:
        greeting = (
            "⚠️ The AI assistant is not available right now (check your API key in `.env`). "
            "You can still use the 7-question tracker on the left to structure your IA, "
            "but AI guidance won't be available until the API key is configured."
        )
    st.session_state.ia_messages.append({"role": "assistant", "content": greeting})


# Auto-start on first load
if not st.session_state.ia_messages:
    _start_new_ia()

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("### 🏴‍☠️ IALA Policy Toolkit")
    st.markdown("---")
    st.page_link("app.py", label="🏠 Home", use_container_width=True)
    st.page_link("pages/1_Impact_Analysis_Helper.py", label="📋 Impact Analysis Helper", use_container_width=True)
    st.page_link("pages/2_Regulatory_Burden_Helper.py", label="💰 Regulatory Burden Helper", use_container_width=True)
    st.page_link("pages/3_Regulatory_Cost_Analysis.py", label="📊 Regulatory Cost Analysis", use_container_width=True)

    st.markdown("---")
    render_pirate_robot(location="inline")
    st.markdown("---")
    st.markdown("#### 📋 IA Questions Progress")

    for i in range(1, 8):
        done = st.session_state.ia_q_complete.get(i, False)
        is_current = (st.session_state.ia_current_q == i)
        icon = "✅" if done else ("▶️" if is_current else "⬜")
        label_style = "**" if is_current else ""
        label = f"{icon} Q{i}: {IA_QUESTION_SHORT[i-1]}"

        if st.button(label, key=f"q_nav_{i}", use_container_width=True):
            st.session_state.ia_current_q = i
            # Inject a context message to refocus the AI
            if st.session_state.ia_chat is not None and get_gemini_helper().is_available:
                context_msg = f"[User has navigated to Question {i}: {IA_QUESTIONS[i-1]}. Please refocus the conversation on this question.]"
                st.session_state.ia_messages.append({"role": "user", "content": f"Let's move to Question {i}."})
                try:
                    helper = get_gemini_helper()
                    response = helper.send_message(st.session_state.ia_chat, context_msg)
                    if response:
                        full = ""
                        for chunk in response:
                            if chunk.text:
                                full += chunk.text
                        st.session_state.ia_messages.append({"role": "assistant", "content": full})
                except Exception:
                    pass
            st.rerun()

    # Mark current question complete
    st.markdown("---")
    current_q = st.session_state.ia_current_q
    already_done = st.session_state.ia_q_complete.get(current_q, False)
    toggle_label = f"{'✅ Mark Q{} incomplete'.format(current_q) if already_done else '⬜ Mark Q{} complete'.format(current_q)}"
    if st.button(toggle_label, use_container_width=True):
        st.session_state.ia_q_complete[current_q] = not already_done
        st.rerun()

    st.markdown("---")
    if st.button("🔄 Start New IA", use_container_width=True):
        _start_new_ia()
        st.rerun()

    st.markdown("---")
    if st.button("Log out", use_container_width=True):
        logout()

# ---------------------------------------------------------------------------
# Main area — header
# ---------------------------------------------------------------------------

st.title("📋 Impact Analysis Helper")
st.markdown(
    "This tool guides you through the 7 IALA Impact Analysis questions using AI. "
    "Use the question tracker on the left to navigate. When you're done, download a Word draft."
)

# Startup warnings for missing reference docs
helper = get_gemini_helper()
if not helper.is_available:
    st.error(f"**AI not available:** {helper.error_message}", icon="🔑")

# Current question banner
q_idx = st.session_state.ia_current_q - 1
st.info(
    f"**Currently on Question {st.session_state.ia_current_q} of 7:** {IA_QUESTIONS[q_idx]}",
    icon="📌",
)

st.divider()

# ---------------------------------------------------------------------------
# Chat interface
# ---------------------------------------------------------------------------

chat_col, ref_col = st.columns([2, 1])

with chat_col:
    # Render message history
    for msg in st.session_state.ia_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat input
    user_input = st.chat_input(
        "Type your message here… (e.g. describe your proposal, ask a question, request a draft)"
    )

    if user_input:
        # Show user message immediately
        st.session_state.ia_messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        # Get AI response
        if helper.is_available and st.session_state.ia_chat is not None:
            with st.chat_message("assistant"):
                placeholder = st.empty()
                full_response = ""
                try:
                    response = helper.send_message(st.session_state.ia_chat, user_input)
                    if response:
                        for chunk in response:
                            if chunk.text:
                                full_response += chunk.text
                                placeholder.markdown(full_response + "▌")
                        placeholder.markdown(full_response)
                except Exception as e:
                    full_response = f"⚠️ Error communicating with AI: {e}"
                    placeholder.error(full_response)

                st.session_state.ia_messages.append({"role": "assistant", "content": full_response})
        else:
            with st.chat_message("assistant"):
                msg = "⚠️ AI is not available. Please check your API key configuration."
                st.warning(msg)
                st.session_state.ia_messages.append({"role": "assistant", "content": msg})

        st.rerun()

    # Buttons below chat
    st.markdown("---")
    col_dl, col_clear = st.columns(2)
    with col_dl:
        if st.button("📄 Download Draft IA (Word)", use_container_width=True, type="primary"):
            if not helper.is_available or st.session_state.ia_chat is None:
                st.error("AI not available — cannot compile draft.")
            elif len(st.session_state.ia_messages) < 3:
                st.warning("Have a conversation first before downloading a draft.")
            else:
                with st.spinner("Compiling your IA draft…"):
                    draft_text = helper.compile_ia_draft(st.session_state.ia_chat)
                    try:
                        from utils.pdf_generator import generate_ia_draft_docx
                        docx_bytes = generate_ia_draft_docx(
                            st.session_state.ia_proposal or "Policy proposal (see chat)",
                            draft_text,
                        )
                        st.download_button(
                            label="⬇️ Download now",
                            data=docx_bytes,
                            file_name="Impact_Analysis_Draft.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            use_container_width=True,
                        )
                    except Exception as e:
                        st.error(f"Could not generate document: {e}")
    with col_clear:
        if st.button("🗑️ Clear conversation", use_container_width=True):
            _start_new_ia()
            st.rerun()

    col_upload, col_search = st.columns(2)
    with col_upload:
        uploaded_ia = st.file_uploader(
            "📤 Upload your draft IA",
            type=["pdf", "docx", "doc"],
            key="ia_upload",
            help="Upload a draft IA document for the AI to review and give feedback on",
        )
        if uploaded_ia and st.button("Analyse uploaded draft", use_container_width=True):
            if not helper.is_available:
                st.error("AI not available.")
            else:
                with st.spinner("Reading your draft…"):
                    try:
                        import io
                        file_bytes = uploaded_ia.read()
                        if uploaded_ia.name.endswith(".pdf"):
                            import pdfplumber
                            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                                doc_text = "\n\n".join(p.extract_text() or "" for p in pdf.pages[:20])
                        else:
                            from docx import Document
                            doc = Document(io.BytesIO(file_bytes))
                            doc_text = "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
                        prompt = (
                            f"The user has uploaded their draft Impact Analysis document. "
                            f"Please review it against the IALA Impact Analysis Framework and provide "
                            f"constructive feedback on each of the 7 IA questions. Here is the document:\n\n"
                            f"{doc_text[:12000]}"
                        )
                        st.session_state.ia_messages.append({"role": "user", "content": f"[Uploaded draft IA: {uploaded_ia.name}]"})
                        response = helper.send_message(st.session_state.ia_chat, prompt)
                        full_response = ""
                        if response:
                            for chunk in response:
                                if chunk.text:
                                    full_response += chunk.text
                        st.session_state.ia_messages.append({"role": "assistant", "content": full_response})
                        st.rerun()
                    except Exception as e:
                        st.error(f"Could not read document: {e}")

    with col_search:
        st.info(
            "🔍 To browse published Impact Analyses, visit the Australian Government's "
            "Impact Analysis register via the Department of the Prime Minister and Cabinet website.",
            icon="📚",
        )

# ---------------------------------------------------------------------------
# Reference examples panel
# ---------------------------------------------------------------------------

with ref_col:
    st.markdown("#### 📚 Reference Examples")

    try:
        index = build_ia_index()
    except Exception as _e:
        index = []
        st.caption(f"Index error: {_e}")

    if not index:
        from utils.ai_helper import IA_INDEX_PATH
        st.info(
            "No IA index yet. Place `ia_assessment_table.xlsx` and IA report files "
            "in `reference_docs/` to enable this panel.",
            icon="📂",
        )
        st.caption(f"Looking for index at: `{IA_INDEX_PATH}` — exists: {IA_INDEX_PATH.exists()}")
    else:
        # Filters
        rating_filter = st.multiselect(
            "Filter by rating",
            options=["Exemplary", "Good Practice", "Adequate", "Insufficient"],
            default=["Exemplary", "Good Practice"],
            key="ref_rating_filter",
        )
        keyword = st.text_input("Search", placeholder="e.g. environment, health, tax", key="ref_search")

        # Apply filters
        filtered = [
            e for e in index
            if (not rating_filter or e["rating"] in rating_filter)
            and (not keyword or keyword.lower() in e["title"].lower()
                 or keyword.lower() in e.get("department", "").lower())
        ]

        st.caption(f"Showing {len(filtered)} of {len(index)} IAs")

        # Rating summary bar
        for rating in ["Exemplary", "Good Practice", "Adequate", "Insufficient"]:
            cfg = RATING_CONFIG[rating]
            count = sum(1 for e in index if e["rating"] == rating)
            if count:
                st.markdown(
                    f'<span style="background:{cfg["bg"]};color:{cfg["colour"]};'
                    f'padding:2px 8px;border-radius:4px;font-size:0.8rem;margin-right:4px">'
                    f'{cfg["emoji"]} {rating}: {count}</span>',
                    unsafe_allow_html=True,
                )
        st.markdown("<br>", unsafe_allow_html=True)

        # IA list
        for entry in filtered[:50]:
            cfg = RATING_CONFIG.get(entry["rating"], RATING_CONFIG["Unknown"])
            dept_str = f" · {entry['department']}" if entry.get("department") else ""
            year_str = f" · {entry['year']}" if entry.get("year") else ""

            href = entry.get("href", "")
            title_html = (
                f'<a href="{href}" target="_blank" style="color:inherit;text-decoration:none">'
                f'{entry["title"]}</a>' if href else entry["title"]
            )
            st.markdown(
                f'<div style="border:1px solid {cfg["colour"]}33;border-radius:6px;'
                f'padding:8px 10px;margin-bottom:6px;background:{cfg["bg"]}22">'
                f'<span style="background:{cfg["bg"]};color:{cfg["colour"]};'
                f'font-size:0.75rem;padding:1px 6px;border-radius:3px;font-weight:600">'
                f'{cfg["emoji"]} {entry["rating"]}</span><br>'
                f'<span style="font-size:0.85rem;font-weight:500">{title_html}</span>'
                f'<br><span style="font-size:0.75rem;color:#666">{dept_str}{year_str}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

        if len(filtered) > 50:
            st.caption(f"Showing first 50 — refine your search to see others.")
