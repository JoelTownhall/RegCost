"""ANZSIC division codes and names."""

# The 19 ANZSIC divisions plus cross-cutting and unclassified
ANZSIC_DIVISIONS = {
    "A": "Agriculture, Forestry and Fishing",
    "B": "Mining",
    "C": "Manufacturing",
    "D": "Electricity, Gas, Water and Waste Services",
    "E": "Construction",
    "F": "Wholesale Trade",
    "G": "Retail Trade",
    "H": "Accommodation and Food Services",
    "I": "Transport, Postal and Warehousing",
    "J": "Information Media and Telecommunications",
    "K": "Financial and Insurance Services",
    "L": "Rental, Hiring and Real Estate Services",
    "M": "Professional, Scientific and Technical Services",
    "N": "Administrative and Support Services",
    "O": "Public Administration and Safety",
    "P": "Education and Training",
    "Q": "Health Care and Social Assistance",
    "R": "Arts and Recreation Services",
    "S": "Other Services",
    "X": "Cross-cutting (All Industries)",
    "U": "Unclassified",
}

# Ordered list for display (sorted by code, with cross-cutting and unclassified at end)
ANZSIC_ORDER = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "X", "U"]

def get_anzsic_label(code: str) -> str:
    """Get display label for ANZSIC code (e.g., 'A: Agriculture, Forestry and Fishing')."""
    name = ANZSIC_DIVISIONS.get(code, "Unknown")
    return f"{code}: {name}"

def get_all_labels() -> list:
    """Get all ANZSIC labels in display order."""
    return [get_anzsic_label(code) for code in ANZSIC_ORDER if code in ANZSIC_DIVISIONS]
