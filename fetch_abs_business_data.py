"""
fetch_abs_business_data.py
─────────────────────────────────────────────────────────────────────────────
Reads ABS Excel files from the local 'ABS Data Manual/' folder and outputs
clean CSVs to 'output/'.  Checkpoint CSVs in 'output/checks/' let you verify
key intermediate steps manually.

Source files used
─────────────────
  8165DC01.xlsx            Business counts + entry/exit rates + survival rates,
                           by ANZSIC Division, June 2021–2025  (ABS 8165.0)

  8165DC02.xlsx            Business counts + employment-size breakdown,
                           by ANZSIC Class (4-digit), June 2024 & 2025

  81550DO001_202324.xlsx   Wages, employment and Industry Value Added (IVA)
                           by ANZSIC Subdivision, 2021-22 to 2023-24 (ABS 8155.0)

Output CSVs  (in output/)
─────────────────────────
  abs_division_counts.csv    Entry/exit counts by division x year  (2022-2025)
  abs_division_survival.csv  4-year survival rates by division  (June 2021 cohort)
  abs_business_counts.csv    Total businesses by ANZSIC class x year  (2024, 2025)
  abs_employment_dist.csv    Employment-size bands by ANZSIC class x year
  abs_wage_share.csv         Labour share (wages / IVA) by subdivision x year

Competition-policy interpretation
───────────────────────────────────
  - Entry/exit rates: high rates = contestable market; low + shrinking = rising barriers
  - Survival rates: low 4-yr survival suggests intense competition in that division
  - Labour share (wages / IVA): a declining trend signals profits capturing more of
    value added -- a soft indicator of weakening competitive pressure on firms
"""

import re
import logging
import pandas as pd
from pathlib import Path

# ── Directories ──────────────────────────────────────────────────────────────

DATA_DIR   = Path("ABS Data Manual")
OUTPUT_DIR = Path("output")
CHECKS_DIR = OUTPUT_DIR / "checks"

OUTPUT_DIR.mkdir(exist_ok=True)
CHECKS_DIR.mkdir(exist_ok=True)

# ── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("RegCost")


# ════════════════════════════════════════════════════════════════════════════
# HELPERS
# ════════════════════════════════════════════════════════════════════════════

def save_checkpoint(df: pd.DataFrame, filename: str, note: str = "") -> None:
    """Write a DataFrame to output/checks/ with a metadata comment header."""
    path = CHECKS_DIR / filename
    with open(path, "w", newline="", encoding="utf-8") as f:
        f.write(f"# {note} | {len(df)} rows\n")
        df.to_csv(f, index=False)
    log.info(f"    Checkpoint -> {path}  ({len(df)} rows)")


def is_year_label(val) -> bool:
    """Return True if val looks like a financial-year string, e.g. '2021-22'."""
    return bool(re.match(r"^\d{4}-\d{2}$", str(val).strip()))


def fy_to_year(s: str) -> int:
    """Convert '2022-23' to 2023  (the calendar year of the June year-end)."""
    return int(str(s).split("-")[0]) + 1


def to_float(val):
    """Convert a cell value to float; return None if not numeric."""
    try:
        return float(str(val).replace(",", "").strip())
    except (ValueError, TypeError):
        return None


# ════════════════════════════════════════════════════════════════════════════
# DATASET 1a  --  8165DC01 Table 1: Division entry/exit counts (2022-2025)
# ════════════════════════════════════════════════════════════════════════════

# The 19 ANZSIC Divisions we want (excludes 'Currently Unknown' aggregate)
DIVISIONS = {
    "Agriculture, Forestry and Fishing",
    "Mining",
    "Manufacturing",
    "Electricity, Gas, Water and Waste Services",
    "Construction",
    "Wholesale Trade",
    "Retail Trade",
    "Accommodation and Food Services",
    "Transport, Postal and Warehousing",
    "Information Media and Telecommunications",
    "Financial and Insurance Services",
    "Rental, Hiring and Real Estate Services",
    "Professional, Scientific and Technical Services",
    "Administrative and Support Services",
    "Public Administration and Safety",
    "Education and Training",
    "Health Care and Social Assistance",
    "Arts and Recreation Services",
    "Other Services",
}


def parse_dc01_counts() -> pd.DataFrame:
    """
    Parse 8165DC01.xlsx Table 1 -- Businesses by Industry Division.

    Layout: rows grouped by financial year.  Each group starts with a year
    label row ('2021-22', '2022-23', ...) followed by one row per division.

    Column mapping (0-indexed):
      0  = division name (or year label, or 'All Industries')
      1  = Operating at start of financial year
      4  = Entries -- Total
      7  = Exits -- Total
      8  = Operating at end of financial year
      10 = Percentage change
      11 = Entry rate (%)
      12 = Exit rate (%)
    """
    log.info("  Parsing DC01 Table 1 (division counts 2022-2025) ...")
    raw = pd.read_excel(DATA_DIR / "8165DC01.xlsx",
                        sheet_name="Table 1", header=None)

    rows, cur_year = [], None

    for _, row in raw.iterrows():
        label = str(row.iloc[0]).strip()

        # Year-label row: set the current year context and move on
        if is_year_label(label):
            cur_year = fy_to_year(label)
            continue

        # Division data row: must be a known division with a numeric start count
        if label in DIVISIONS and cur_year is not None:
            op_start = to_float(row.iloc[1])
            if op_start is None:
                continue
            rows.append({
                "division":      label,
                "year":          cur_year,
                "op_start":      op_start,
                "entries_total": to_float(row.iloc[4]),
                "exits_total":   to_float(row.iloc[7]),
                "op_end":        to_float(row.iloc[8]),
                "pct_change":    to_float(row.iloc[10]),
                "entry_rate":    to_float(row.iloc[11]),
                "exit_rate":     to_float(row.iloc[12]),
                "data_source":   "ABS 8165.0 DC01 Table 1",
            })

    df = pd.DataFrame(rows).dropna(subset=["op_start"])
    log.info(f"    {len(df)} rows | {df['division'].nunique()} divisions | "
             f"years {sorted(df['year'].unique())}")
    save_checkpoint(df, "check_01_dc01_division_counts.csv",
                    "Division entry/exit counts from 8165DC01 Table 1")
    return df


# ════════════════════════════════════════════════════════════════════════════
# DATASET 1b  --  8165DC01 Table 2: Division survival rates (June 2021 cohort)
# ════════════════════════════════════════════════════════════════════════════

def parse_dc01_survival() -> pd.DataFrame:
    """
    Parse 8165DC01.xlsx Table 2 -- Survival of Businesses by Industry Division.

    Cohort table: businesses operating at June 2021, tracked to June 2025.
    One row per division (no year grouping needed).

    Column mapping (0-indexed):
      0  = division name
      1  = Operating in June 2021 (cohort size)
      2  = Survived to June 2022  |  3  = Survival rate 1-year (%)
      4  = Survived to June 2023  |  5  = Survival rate 2-year (%)
      6  = Survived to June 2024  |  7  = Survival rate 3-year (%)
      8  = Survived to June 2025  |  9  = Survival rate 4-year (%)
    """
    log.info("  Parsing DC01 Table 2 (division survival, June 2021 cohort) ...")
    raw = pd.read_excel(DATA_DIR / "8165DC01.xlsx",
                        sheet_name="Table 2", header=None)

    rows = []
    for _, row in raw.iterrows():
        label  = str(row.iloc[0]).strip()
        cohort = to_float(row.iloc[1])

        # Skip headers, blank rows, aggregates, and tiny values
        if cohort is None or cohort < 100:
            continue
        if "All Industries" in label or "Currently" in label:
            continue

        # A real division row has a survival rate in col 3
        sr1 = to_float(row.iloc[3])
        if sr1 is None:
            continue

        rows.append({
            "division":       label,
            "cohort_jun2021": cohort,
            "surv_jun2022":   to_float(row.iloc[2]),
            "surv_rate_1yr":  sr1,
            "surv_jun2023":   to_float(row.iloc[4]),
            "surv_rate_2yr":  to_float(row.iloc[5]),
            "surv_jun2024":   to_float(row.iloc[6]),
            "surv_rate_3yr":  to_float(row.iloc[7]),
            "surv_jun2025":   to_float(row.iloc[8]),
            "surv_rate_4yr":  to_float(row.iloc[9]),
            "data_source":    "ABS 8165.0 DC01 Table 2",
        })

    df = pd.DataFrame(rows).dropna(subset=["surv_rate_1yr"])
    log.info(f"    {len(df)} division rows")
    save_checkpoint(df, "check_02_dc01_survival.csv",
                    "Division survival rates from 8165DC01 Table 2")
    return df


# ════════════════════════════════════════════════════════════════════════════
# DATASET 2  --  8165DC02: ANZSIC Class counts + employment-size breakdown
# ════════════════════════════════════════════════════════════════════════════

def parse_dc02_class_counts() -> pd.DataFrame:
    """
    Parse 8165DC02.xlsx Tables 1 (June 2025) and 2 (June 2024).

    Each table has one row per state x class, plus a national 'Total' row
    (state column = NaN) for each class.  We keep only the national totals.

    Column mapping (0-indexed) -- confirmed from data inspection:
      0   State name  (NaN for national total rows)
      1   ANZSIC class code  (numeric; 111 means class 0111)
      2   Class label  (e.g. 'Total Nursery Production (Under Cover)')
      3-8   Operating at START: Non-emp, 1-4, 5-19, 20-199, 200+, Total
      9-14  Entries: Non-emp, 1-4, 5-19, 20-199, 200+, Total
      15-20 Exits: Non-emp, 1-4, 5-19, 20-199, 200+, Total
      21-26 Net movement of surviving businesses: Non-emp ... Total
      27  Operating at END -- Non-employing
      28  Operating at END -- 1-4 employees
      29  Operating at END -- 5-19 employees
      30  Operating at END -- 20-199 employees
      31  Operating at END -- 200+ employees
      32  Operating at END -- Total  (headline business count)
      33  Change (number)
      34  Percentage change
      35  Entry rate (%)
      36  Exit rate (%)

    ANZSIC codes appear without leading zeros (111 not 0111).
    We zero-pad to 4 digits and also derive the 3-digit Group code
    by dropping the last digit  (e.g. 0111 -> 011).
    """
    log.info("  Parsing DC02 (ANZSIC class counts + employment size, 2024 & 2025) ...")
    xl = pd.ExcelFile(DATA_DIR / "8165DC02.xlsx")

    frames = []
    for sheet, year in [("Table 1", 2025), ("Table 2", 2024)]:
        raw = pd.read_excel(xl, sheet_name=sheet, header=None)

        for _, row in raw.iterrows():
            state = row.iloc[0]
            code  = row.iloc[1]
            label = str(row.iloc[2]).strip()

            # National total rows: state=NaN, code is numeric, label starts 'Total '
            if not (pd.isna(state) and not pd.isna(code) and label.startswith("Total ")):
                continue

            code_num = to_float(code)
            if code_num is None:
                continue

            # Pad to 4-digit ANZSIC class; first 3 digits = group code
            class_code = str(int(code_num)).zfill(4)   # e.g. '0111'
            group_code = class_code[:3]                 # e.g. '011'
            class_name = label[6:]                      # strip 'Total ' prefix

            # Operating-at-end employment breakdown (cols 27-32)
            total = to_float(row.iloc[32])
            if total is None or total < 0:
                continue

            frames.append({
                "anzsic_class_code": class_code,
                "anzsic_class_name": class_name,
                "anzsic_group_code": group_code,
                "year":              year,
                "non_employing":     to_float(row.iloc[27]),
                "emp_1_4":           to_float(row.iloc[28]),
                "emp_5_19":          to_float(row.iloc[29]),
                "emp_20_199":        to_float(row.iloc[30]),
                "emp_200plus":       to_float(row.iloc[31]),
                "total_businesses":  total,
                "entry_rate":        to_float(row.iloc[35]),
                "exit_rate":         to_float(row.iloc[36]),
                "data_source":       f"ABS 8165.0 DC02 Table {'1' if year == 2025 else '2'}",
            })

    df = pd.DataFrame(frames)
    log.info(f"    {len(df)} rows | {df['anzsic_class_code'].nunique()} classes | "
             f"years {sorted(df['year'].unique())}")
    save_checkpoint(df, "check_03_dc02_class_counts.csv",
                    "ANZSIC class counts + employment size from 8165DC02")
    return df


# ════════════════════════════════════════════════════════════════════════════
# DATASET 3  --  81550DO001: Labour share (wages / IVA) by subdivision
# ════════════════════════════════════════════════════════════════════════════

def parse_wage_share() -> pd.DataFrame:
    """
    Parse 81550DO001_202324.xlsx Table_1 -- Key data by industry division
    and subdivision.

    The spreadsheet uses a hierarchical text layout (no true multi-index):
      Division header row  (e.g. 'Agriculture, forestry and fishing')
        Subdivision row    (e.g. '01 Agriculture')
          Year row         (e.g. '2021-22')   <-- data lives here
          Year row         '2022-23'
          Year row         '2023-24'
        Total row          (e.g. 'Total agriculture ...')  -- skip
        Subdivision row    (e.g. '02 Aquaculture')
          ...

    Column mapping (0-indexed):
      0  Label (division / subdivision / year string / total)
      1  Employment at end of June ('000)
      2  Wages and salaries ($m)
      8  Industry value added -- IVA ($m)

    Labour share = wages_$m / IVA_$m x 100  (%)

    Interpretation: a falling labour share over time indicates profits
    are capturing an increasing share of value added -- a soft signal
    of weakening competitive pressure on firms in that subdivision.
    """
    log.info("  Parsing DO001 (wages + IVA by subdivision, 2021-22 to 2023-24) ...")
    raw = pd.read_excel(DATA_DIR / "81550DO001_202324.xlsx",
                        sheet_name="Table_1", header=None)

    # Subdivision rows start with a 2-digit code, e.g. '01 Agriculture'
    SUBDIV_PAT = re.compile(r"^(\d{2})\s+(.+)$")

    rows            = []
    cur_division    = None
    cur_subdiv_code = None
    cur_subdiv_name = None

    for _, row in raw.iterrows():
        label = str(row.iloc[0]).strip()

        if label in ("", "nan"):
            continue

        # Year row: extract wages + IVA for the current subdivision
        if is_year_label(label):
            wages = to_float(row.iloc[2])
            iva   = to_float(row.iloc[8])
            emp   = to_float(row.iloc[1])
            if cur_subdiv_code and wages is not None and iva is not None and iva > 0:
                rows.append({
                    "division":         cur_division,
                    "subdivision_code": cur_subdiv_code,
                    "subdivision_name": cur_subdiv_name,
                    "year":             fy_to_year(label),
                    "wages_m":          wages,
                    "iva_m":            iva,
                    "employment_000":   emp,
                    # Labour share: fraction of value added going to workers
                    "labour_share_pct": round(wages / iva * 100, 2),
                    "data_source":      "ABS 8155.0 DO001",
                })
            continue

        # Subdivision row: '01 Agriculture', '02 Aquaculture', etc.
        m = SUBDIV_PAT.match(label)
        if m:
            cur_subdiv_code = m.group(1)
            cur_subdiv_name = m.group(2)
            continue

        # Total row: marks end of a subdivision block -- skip
        if label.lower().startswith("total "):
            continue

        # Division header row: alpha text, no leading digit, not a year
        if not label[0].isdigit():
            cur_division    = label
            cur_subdiv_code = None
            cur_subdiv_name = None

    df = pd.DataFrame(rows)
    log.info(f"    {len(df)} rows | {df['subdivision_code'].nunique()} subdivisions | "
             f"years {sorted(df['year'].unique())}")
    save_checkpoint(df, "check_04_wage_share.csv",
                    "Subdivision labour share from 81550DO001 Table_1")
    return df


# ════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════

def main():
    log.info("RegCost -- ABS business data (reading from ABS Data Manual/)")
    log.info(f"Output: {OUTPUT_DIR}  |  Checkpoints: {CHECKS_DIR}")
    log.info("")

    log.info("Step 1 of 4: Division entry/exit counts (DC01 Table 1) ...")
    df_div_counts   = parse_dc01_counts()

    log.info("Step 2 of 4: Division survival rates (DC01 Table 2) ...")
    df_div_survival = parse_dc01_survival()

    log.info("Step 3 of 4: ANZSIC class counts + employment size (DC02) ...")
    df_class        = parse_dc02_class_counts()

    log.info("Step 4 of 4: Wage share (DO001) ...")
    df_ws           = parse_wage_share()

    # ── Save output CSVs ─────────────────────────────────────────────────────
    log.info("")
    log.info("=" * 60)
    log.info("SAVING OUTPUT FILES")
    log.info("=" * 60)

    outputs = {
        "abs_division_counts.csv":   df_div_counts,
        "abs_division_survival.csv": df_div_survival,
        # Business counts: one row per class x year, headline total only
        "abs_business_counts.csv":   df_class[[
            "anzsic_class_code", "anzsic_class_name", "anzsic_group_code",
            "year", "total_businesses", "entry_rate", "exit_rate", "data_source"
        ]],
        # Employment distribution: full size-band breakdown per class x year
        "abs_employment_dist.csv":   df_class[[
            "anzsic_class_code", "anzsic_class_name", "anzsic_group_code",
            "year", "non_employing", "emp_1_4", "emp_5_19",
            "emp_20_199", "emp_200plus", "total_businesses", "data_source"
        ]],
        "abs_wage_share.csv":        df_ws,
    }

    for fname, df in outputs.items():
        path = OUTPUT_DIR / fname
        df.to_csv(path, index=False)
        src = df["data_source"].unique().tolist() if "data_source" in df.columns else []
        log.info(f"  {fname:<42} {len(df):>6} rows   {src}")

    # ── Sanity checks ─────────────────────────────────────────────────────────
    log.info("")
    log.info("=" * 60)
    log.info("SANITY CHECKS")
    log.info("=" * 60)

    n_classes  = df_class["anzsic_class_code"].nunique()
    total_2025 = df_class[df_class["year"] == 2025]["total_businesses"].sum()
    log.info(f"  Business counts 2025: {n_classes} classes, "
             f"{total_2025:,.0f} total firms  (expect ~500 classes, ~2.6M firms)")

    log.info(f"  Division counts years: {sorted(df_div_counts['year'].unique())}")
    log.info(f"  Survival cohort divisions: {df_div_survival['division'].nunique()}")

    if not df_ws.empty:
        avg_ls = df_ws[df_ws["year"] == 2024]["labour_share_pct"].mean()
        log.info(f"  Labour share 2023-24 avg: {avg_ls:.1f}%  (expect ~40-60%)")

    log.info("")
    log.info("Done.  Review output/checks/ then run:  streamlit run app.py")


if __name__ == "__main__":
    main()
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           