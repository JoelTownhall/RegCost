# Reference Documents

This directory holds the reference documents used by the OIA Policy Toolkit AI features.

**All source files are in the Google Drive folder:**
https://drive.google.com/drive/folders/1Ok9PGlhGR7Di1awt5pFrNd4aX21c_Hg6

## Files to place here (in `reference_docs/`)

| File | Description | Used by |
|------|-------------|---------|
| `ia_framework.pdf` | Australian Government Guide to Policy Impact Analysis (high-level) | Page 1: Impact Analysis Helper |
| `ia_framework_users_guide.pdf` | IA Framework Users Guide (detailed process, scenarios, edge cases) | Page 1: Impact Analysis Helper |
| `ia_assessment_table.xlsx` | OIA assessment ratings table (Exemplary / Good Practice / Adequate / Insufficient) | Page 1: Impact Analysis Helper |
| `regcostworkbook.xlsx` | OIA Regulatory Burden Measurement Framework workbook | Page 2: Regulatory Burden Helper |

## Files to place in `reference_docs/ia_reports/`

Place all ~800 published Impact Analysis reports (.doc, .pdf) in the `ia_reports/` subdirectory.
These are the full corpus of published IAs from the OIA website and form the evidence base
for the AI assistant's recommendations.

The app will:
1. On first run, build a lightweight index (filename → rating → topic) from these files
2. Use keyword search to find relevant IAs when the AI wants to cite an example
3. Extract and send relevant sections to the API as context

## Startup checks

The app will warn you on startup if any of these files are missing. The AI features
will be limited or unavailable until the reference documents are in place.
