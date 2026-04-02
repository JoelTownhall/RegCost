# IA Reports Directory

Place all ~800 published Impact Analysis report files here.

**Source:** https://drive.google.com/drive/folders/1Ok9PGlhGR7Di1awt5pFrNd4aX21c_Hg6

## Accepted file formats

- `.pdf` — PDF versions of published IAs
- `.doc` / `.docx` — Word document versions of published IAs

## What happens with these files

On first run, the Impact Analysis Helper will:
1. Scan this directory and build an index of all IA reports
2. Cross-reference filenames with `ia_assessment_table.xlsx` to map each IA to its IALA rating
3. Store the index as `reference_docs/ia_index.json` for fast future loading

The index maps each report to:
- Its OIA assessment rating (Exemplary / Good Practice / Adequate / Insufficient)
- Extracted title and key topics
- Relevant policy area / department

This allows the AI to recommend Exemplary and Good Practice IAs as reference examples
when guiding users through the 7 IA questions, without sending all 800 reports to the API.
