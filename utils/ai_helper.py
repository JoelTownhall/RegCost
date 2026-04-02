"""
Gemini AI integration for the OIA Policy Toolkit.
Handles reference document loading, IA report indexing, and multi-turn conversations.
"""
import os
import json
import re
from pathlib import Path
from typing import Optional

import streamlit as st
import pandas as pd

try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).parent.parent / ".env"
    load_dotenv(_env_path)
except ImportError:
    pass


def _get_api_key() -> str:
    """Get Gemini API key — checks st.secrets first (Streamlit Cloud), then env var."""
    try:
        return st.secrets.get("GOOGLE_API_KEY", "") or os.environ.get("GOOGLE_API_KEY", "")
    except Exception:
        return os.environ.get("GOOGLE_API_KEY", "")

# --- Paths ---
REFERENCE_DOCS_DIR = Path("reference_docs")
IA_REPORTS_DIR = REFERENCE_DOCS_DIR / "ia_reports"
IA_INDEX_PATH = REFERENCE_DOCS_DIR / "ia_index.json"
IA_FRAMEWORK_PDF = REFERENCE_DOCS_DIR / "ia_framework.pdf"
IA_USERS_GUIDE_PDF = REFERENCE_DOCS_DIR / "ia_framework_users_guide.pdf"
IA_ASSESSMENT_TABLE = REFERENCE_DOCS_DIR / "ia_assessment_table.xlsx"
REGCOST_WORKBOOK = REFERENCE_DOCS_DIR / "regcostworkbook.xlsx"

MODEL_NAME = "gemini-2.5-flash"

# Rating display config
RATING_CONFIG = {
    "Exemplary":      {"emoji": "🟢", "colour": "#1a7f37", "bg": "#d4f0dc"},
    "Good Practice":  {"emoji": "🔵", "colour": "#0550ae", "bg": "#d4e8ff"},
    "Adequate":       {"emoji": "🟡", "colour": "#7d4e00", "bg": "#fff4d4"},
    "Insufficient":   {"emoji": "🔴", "colour": "#d1242f", "bg": "#ffd4d4"},
    "Unknown":        {"emoji": "⚪", "colour": "#666",    "bg": "#f0f0f0"},
}

# The 7 IA Questions
IA_QUESTIONS = [
    "What is the policy problem you are trying to solve and what data is available?",
    "What are the objectives, why is government intervention needed to achieve them, and how will success be measured?",
    "What policy options are you considering?",
    "What is the likely net benefit of each option?",
    "Who did you consult and how did you incorporate their feedback?",
    "What is the best option from those you have considered and how will it be implemented?",
    "How will you evaluate your chosen option against the success metrics?",
]

IA_QUESTION_SHORT = [
    "Problem definition",
    "Objectives & intervention rationale",
    "Policy options",
    "Net benefit analysis",
    "Consultation",
    "Best option & implementation",
    "Evaluation",
]

BASE_SYSTEM_PROMPT = """You are an expert assistant helping Australian Public Service (APS) policy officers write Impact Analyses (IAs) under the Australian Government's Impact Analysis Framework, administered by the Office of Impact Analysis (OIA) within the Department of the Prime Minister and Cabinet.

Your role is to guide the user step-by-step through the 7 Impact Analysis questions:

1. What is the policy problem you are trying to solve and what data is available?
2. What are the objectives, why is government intervention needed to achieve them, and how will success be measured?
3. What policy options are you considering?
4. What is the likely net benefit of each option?
5. Who did you consult and how did you incorporate their feedback?
6. What is the best option from those you have considered and how will it be implemented?
7. How will you evaluate your chosen option against the success metrics?

For each question:
- Explain what OIA expects and what "exemplary" looks like
- Ask the user about their specific policy proposal
- Help them draft their response
- Point them to relevant sections of the Impact Analysis Framework guide
- Suggest where they can find good evidence examples from published IAs
- Flag common pitfalls that lead to "insufficient" assessments
- Remind them about proportionality — depth of analysis should match the scale of the proposal

You should also be knowledgeable about:
- The Regulatory Burden Measurement Framework (administrative costs, substantive compliance costs, delay costs)
- The default hourly tariff rates ($85.17/hr for work-related activities, $37/hr for leisure time)
- The 10-year default costing period
- The requirement for at least 3 options (including status quo and a non-regulatory option)
- The two-pass Final Assessment process
- When to contact OIA (helpdesk-OIA@pmc.gov.au or 02 6271 6270)

Be practical, specific, and encouraging. Many users are doing this for the first time. Use plain language. If the user's proposal seems minor, tell them it might not need a full IA and suggest they contact OIA for a preliminary assessment.

When recommending published IA examples, always note their OIA rating (Exemplary/Good Practice/Adequate/Insufficient) and briefly explain what makes them a good (or cautionary) example. Only actively recommend Exemplary and Good Practice IAs. If asked about an Insufficient-rated IA, note its shortcomings and suggest a better-rated alternative.

Reference the attached framework documents when answering questions."""

COMPILE_PROMPT = """Based on our conversation so far, please compile a complete structured draft Impact Analysis document.

Format it with clear headings for each of the 7 questions:

**Question 1: What is the policy problem you are trying to solve and what data is available?**
[Draft response]

**Question 2: What are the objectives, why is government intervention needed to achieve them, and how will success be measured?**
[Draft response]

...and so on through all 7 questions.

For each question:
- Write the best draft response you can based on what we've discussed
- Where more information is still needed, write [TODO: description of what's needed]
- Keep the language clear, evidence-based, and proportionate to the proposal's scale

End with a brief **Reviewer's Notes** section flagging the key gaps that need to be addressed before OIA submission."""


# ---------------------------------------------------------------------------
# Document text extraction (cached)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=None, show_spinner=False)
def _extract_pdf_text(path_str: str, max_pages: int = 60) -> str:
    """Extract text from a PDF."""
    try:
        import pdfplumber
        with pdfplumber.open(path_str) as pdf:
            pages = pdf.pages[:max_pages]
            return "\n\n".join(p.extract_text() or "" for p in pages)
    except Exception as e:
        return f"[PDF extraction failed for {Path(path_str).name}: {e}]"


@st.cache_data(ttl=None, show_spinner=False)
def load_framework_text() -> dict:
    """Load and cache text from the IA framework PDFs. Returns {key: text}."""
    docs = {}
    for path, key in [
        (IA_FRAMEWORK_PDF, "ia_framework"),
        (IA_USERS_GUIDE_PDF, "ia_users_guide"),
    ]:
        if path.exists():
            docs[key] = _extract_pdf_text(str(path))
    return docs


# ---------------------------------------------------------------------------
# IA report index
# ---------------------------------------------------------------------------

@st.cache_data(ttl=None, show_spinner=False)
def build_ia_index() -> list:
    """
    Build/load the index of IA reports with OIA assessment ratings.
    Returns list of dicts: filename, title, rating, department, year.
    """
    if IA_INDEX_PATH.exists():
        try:
            with open(IA_INDEX_PATH) as f:
                return json.load(f)
        except Exception:
            pass

    index = []
    ratings_map = {}  # title_lower -> {title, rating, department, year}

    # Load ratings from xlsx
    if IA_ASSESSMENT_TABLE.exists():
        try:
            df = pd.read_excel(IA_ASSESSMENT_TABLE)
            df.columns = df.columns.str.strip()
            col_map = _identify_assessment_columns(df)
            if col_map.get("title") and col_map.get("rating"):
                for _, row in df.iterrows():
                    title = str(row.get(col_map["title"], "")).strip()
                    rating = str(row.get(col_map["rating"], "")).strip()
                    dept = str(row.get(col_map.get("department", ""), "")).strip() if col_map.get("department") else ""
                    year = str(row.get(col_map.get("year", ""), "")).strip() if col_map.get("year") else ""
                    if title and rating and title != "nan":
                        ratings_map[title.lower()] = {
                            "title": title,
                            "rating": _normalise_rating(rating),
                            "department": dept if dept != "nan" else "",
                            "year": year if year != "nan" else "",
                        }
        except Exception:
            pass

    # Scan ia_reports directory
    if IA_REPORTS_DIR.exists():
        for fpath in sorted(IA_REPORTS_DIR.iterdir()):
            if fpath.suffix.lower() in (".pdf", ".doc", ".docx"):
                stem = fpath.stem
                title = _filename_to_title(stem)
                rating_info = ratings_map.get(title.lower()) or _fuzzy_rating_lookup(title, ratings_map)
                index.append({
                    "filename": fpath.name,
                    "title": rating_info["title"] if rating_info else title,
                    "rating": rating_info["rating"] if rating_info else "Unknown",
                    "department": rating_info.get("department", "") if rating_info else "",
                    "year": rating_info.get("year", "") if rating_info else "",
                })

    # Add ratings-only entries (no matching file found)
    indexed_titles = {e["title"].lower() for e in index}
    for title_lower, info in ratings_map.items():
        if title_lower not in indexed_titles:
            index.append({
                "filename": "",
                "title": info["title"],
                "rating": info["rating"],
                "department": info.get("department", ""),
                "year": info.get("year", ""),
            })

    # Save for next time
    try:
        IA_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(IA_INDEX_PATH, "w") as f:
            json.dump(index, f, indent=2)
    except Exception:
        pass

    return index


def _identify_assessment_columns(df: pd.DataFrame) -> dict:
    """Identify which columns map to title, rating, department, year."""
    col_map = {}
    cols_lower = {c.lower(): c for c in df.columns}

    search_patterns = {
        "title":      ["title", "ia name", "ia title", "report", "document", "name"],
        "rating":     ["rating", "assessment", "outcome", "quality", "tier", "result"],
        "department": ["department", "agency", "portfolio", "minister"],
        "year":       ["year", "date"],
    }
    for field, patterns in search_patterns.items():
        for pattern in patterns:
            for col_lower, col in cols_lower.items():
                if pattern in col_lower:
                    col_map[field] = col
                    break
            if field in col_map:
                break
    return col_map


def _normalise_rating(raw: str) -> str:
    r = raw.lower().strip()
    if "exemplary" in r or "best practice" in r:
        return "Exemplary"
    if "good" in r:
        return "Good Practice"
    if "adequate" in r or "satisfactory" in r:
        return "Adequate"
    if "insufficient" in r or "inadequate" in r or "poor" in r:
        return "Insufficient"
    return raw.strip() or "Unknown"


def _filename_to_title(stem: str) -> str:
    title = re.sub(r"[-_]+", " ", stem)
    return re.sub(r"\s+", " ", title).strip().title()


def _fuzzy_rating_lookup(title: str, ratings_map: dict) -> Optional[dict]:
    title_words = set(w for w in title.lower().split() if len(w) > 3)
    best, best_score = None, 0
    for key, info in ratings_map.items():
        key_words = set(w for w in key.split() if len(w) > 3)
        score = len(title_words & key_words)
        if score > best_score and score >= 3:
            best_score = score
            best = info
    return best


def get_ia_index_summary(index: list, top_n: int = 25) -> str:
    """Text summary of top-rated IAs for inclusion in the system prompt."""
    exemplary = [e for e in index if e["rating"] == "Exemplary"]
    good = [e for e in index if e["rating"] == "Good Practice"]

    lines = ["\n\n## Published IA Reference Examples (OIA-rated)"]
    if exemplary:
        lines.append("\n### Exemplary IAs:")
        for e in exemplary[:top_n]:
            dept = f" ({e['department']})" if e.get("department") else ""
            yr = f" [{e['year']}]" if e.get("year") else ""
            lines.append(f"- {e['title']}{dept}{yr}")
    if good:
        lines.append("\n### Good Practice IAs:")
        for e in good[:top_n]:
            dept = f" ({e['department']})" if e.get("department") else ""
            yr = f" [{e['year']}]" if e.get("year") else ""
            lines.append(f"- {e['title']}{dept}{yr}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# GeminiHelper
# ---------------------------------------------------------------------------

@st.cache_resource(show_spinner=False)
def get_gemini_helper():
    """Shared GeminiHelper instance (cached across reruns)."""
    return GeminiHelper()


RBMF_SYSTEM_PROMPT = """You are an expert on the Australian Government's Regulatory Burden Measurement Framework (RBMF), administered by the Office of Impact Analysis (OIA) within the Department of the Prime Minister and Cabinet.

Your role is to help APS policy officers:
1. Calculate regulatory costs correctly using the RBMF methodology
2. Classify costs into the right category (administrative costs, substantive compliance costs, delay costs)
3. Extract quantitative cost data from consultation reports and RIS documents
4. Apply the correct tariff rates and costing conventions
5. Present estimates proportionately — depth of analysis should match scale of impact

## Key RBMF Parameters
- **Default hourly tariff (work-related activities, businesses/employees):** $85.17/hour
- **Default hourly tariff (leisure time / individuals not in employment):** $37/hour
- **Default costing period:** 10 years
- **Presentation:** Average annual regulatory costs in real terms (constant prices)
- **Unit:** Report in dollars; express in millions ($m) in the RBE table

## Cost Categories
- **Administrative costs:** Costs of demonstrating compliance to government — form-filling, record-keeping, reporting, registrations, inspections, licences. These do NOT change the substance of what the entity does.
- **Substantive compliance costs:** Real changes to business/individual operations — capital investment, hiring staff, changing processes, purchasing equipment. These change what the entity actually does.
- **Delay costs:** Costs imposed on entities by government-imposed waiting periods — e.g. waiting for a licence approval, assessment, or approval before commencing activity.

## What to EXCLUDE from RBMF
- Taxes, levies, and tax-like charges
- Pure opportunity costs (unless major and directly caused by the regulation)
- Government's own enforcement costs
- Costs arising solely from international obligations
- One-off transitional/adjustment costs (unless major)

## Stakeholder Types
- **Business:** Corporations, sole traders, partnerships, trusts
- **Individuals:** Private citizens, consumers, patients, job seekers
- **Community organisations:** NFPs, charities, clubs, churches, peak bodies

## Consultation Report Extraction
When given consultation report text, extract:
- Hours to comply with each activity (distinguish from tariff-related and non-tariff)
- Wage rates or hourly costs cited by respondents
- Number of affected entities (total, or by type)
- Frequency of compliance activities per year
- Capital costs, equipment costs, or other direct costs
- Any delays imposed and their duration/cost

Present extracted data in a clean table and suggest which RBMF fields they map to.

Be practical, specific, and concise. Flag assumptions and suggest when OIA should be consulted directly (helpdesk-OIA@pmc.gov.au | 02 6271 6270)."""


@st.cache_resource(show_spinner=False)
def get_rbmf_helper():
    """Shared RBMF-focused GeminiHelper instance."""
    return GeminiHelper(system_prompt=RBMF_SYSTEM_PROMPT)


class GeminiHelper:
    """Wrapper around the Gemini API for IA assistance."""

    def __init__(self, system_prompt: str = None):
        self.api_key = _get_api_key()
        self._model = None
        self._error = None

        if not GENAI_AVAILABLE:
            self._error = "google-generativeai package not installed. Run: pip install google-generativeai"
            return
        if not self.api_key:
            self._error = "GOOGLE_API_KEY not set. Add it to your .env file."
            return

        try:
            genai.configure(api_key=self.api_key)
            instruction = system_prompt if system_prompt else self._build_system_instruction()
            self._model = genai.GenerativeModel(
                model_name=MODEL_NAME,
                system_instruction=instruction,
            )
        except Exception as e:
            self._error = f"Could not initialise Gemini model: {e}"

    @property
    def is_available(self) -> bool:
        return self._model is not None

    @property
    def error_message(self) -> str:
        return self._error or ""

    def _build_system_instruction(self) -> str:
        parts = [BASE_SYSTEM_PROMPT]
        docs = load_framework_text()
        if docs.get("ia_framework"):
            parts.append("\n\n## Impact Analysis Framework\n\n" + docs["ia_framework"][:40_000])
        if docs.get("ia_users_guide"):
            parts.append("\n\n## IA Framework Users Guide\n\n" + docs["ia_users_guide"][:40_000])
        try:
            index = build_ia_index()
            if index:
                parts.append(get_ia_index_summary(index))
        except Exception:
            pass
        return "\n".join(parts)

    def start_new_chat(self):
        """Return a new ChatSession (stores its own history internally)."""
        if not self.is_available:
            return None
        return self._model.start_chat(history=[])

    def send_message(self, chat, message: str):
        """Send message, return streaming response iterator (or raise)."""
        if not self.is_available or chat is None:
            return None
        return chat.send_message(message, stream=True)

    def compile_ia_draft(self, chat) -> str:
        """Ask the AI to compile the conversation into a structured IA draft."""
        if not self.is_available or chat is None:
            return ""
        try:
            response = chat.send_message(COMPILE_PROMPT, stream=False)
            return response.text
        except Exception as e:
            return f"Error generating draft: {e}"


def check_reference_docs() -> dict:
    """
    Check which reference documents exist.
    Returns dict of {name: bool} and a list of warning strings.
    """
    checks = {
        "ia_framework.pdf": IA_FRAMEWORK_PDF.exists(),
        "ia_framework_users_guide.pdf": IA_USERS_GUIDE_PDF.exists(),
        "ia_assessment_table.xlsx": IA_ASSESSMENT_TABLE.exists(),
        "regcostworkbook.xlsx": REGCOST_WORKBOOK.exists(),
        "ia_reports/ (any files)": IA_REPORTS_DIR.exists() and any(
            f.suffix.lower() in (".pdf", ".doc", ".docx")
            for f in IA_REPORTS_DIR.iterdir()
        ) if IA_REPORTS_DIR.exists() else False,
    }
    return checks
