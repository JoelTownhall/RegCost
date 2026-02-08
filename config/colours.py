"""Colour palette definitions for RegCost charts."""

# Legislation type colours (consistent across all charts)
LEG_COLOURS = {
    "Act": "#1f4e79",
    "Legislative Instrument": "#2e86ab",
    "Notifiable Instrument": "#a4c3d2",
}

# Macro indicator colours for Chart 3
MACRO_COLOURS = {
    "Legislation": "#1f4e79",
    "Requirements": "#c0392b",
    "Real GDP": "#27ae60",
    "Employment": "#8e44ad",
    "Productivity": "#f39c12",
    "Investment": "#2c3e50",
}

# Industry chart colours
INDUSTRY_HIGHLIGHT = "#1f4e79"
INDUSTRY_DEFAULT = "#a4c3d2"

# Colourblind-friendly palette for multi-series charts
ACCESSIBLE_PALETTE = [
    "#1f4e79",  # Dark blue
    "#c0392b",  # Red
    "#27ae60",  # Green
    "#8e44ad",  # Purple
    "#f39c12",  # Orange
    "#2c3e50",  # Dark grey
    "#16a085",  # Teal
    "#e74c3c",  # Light red
]
