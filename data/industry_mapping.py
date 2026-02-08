"""Industry mapping configuration - Department to ANZSIC and keyword mappings."""

# Department/Agency to ANZSIC division mapping
# This maps the administering body to the primary industry they regulate
DEPARTMENT_TO_ANZSIC = {
    # Agriculture and primary industries
    "Department of Agriculture": "A",
    "Department of Agriculture, Water and the Environment": "A",
    "Agriculture": "A",
    "Fisheries": "A",
    "Forestry": "A",

    # Mining and resources
    "Department of Resources": "B",
    "Department of Industry, Science, Energy and Resources": "B",
    "Geoscience Australia": "B",

    # Manufacturing
    "Department of Industry": "C",

    # Utilities
    "Department of Climate Change, Energy, the Environment and Water": "D",
    "Clean Energy Regulator": "D",
    "Australian Energy Regulator": "D",

    # Construction
    "Australian Building and Construction Commission": "E",
    "ABCC": "E",

    # Trade
    "Department of Foreign Affairs and Trade": "F",
    "Austrade": "F",

    # Transport
    "Department of Infrastructure, Transport, Regional Development": "I",
    "Department of Transport": "I",
    "Civil Aviation Safety Authority": "I",
    "CASA": "I",
    "Australian Maritime Safety Authority": "I",
    "AMSA": "I",

    # Telecommunications
    "Department of Communications": "J",
    "Australian Communications and Media Authority": "J",
    "ACMA": "J",

    # Financial services
    "Treasury": "K",
    "Australian Prudential Regulation Authority": "K",
    "APRA": "K",
    "Australian Securities and Investments Commission": "K",
    "ASIC": "K",
    "Reserve Bank of Australia": "K",
    "RBA": "K",

    # Real estate
    "Australian Valuation Office": "L",

    # Professional services
    "IP Australia": "M",

    # Public administration
    "Attorney-General's Department": "O",
    "Department of Defence": "O",
    "Department of Home Affairs": "O",
    "Australian Federal Police": "O",
    "AFP": "O",
    "Australian Border Force": "O",
    "ABF": "O",
    "Department of Veterans' Affairs": "O",
    "DVA": "O",

    # Education
    "Department of Education": "P",
    "Department of Education, Skills and Employment": "P",
    "Tertiary Education Quality and Standards Agency": "P",
    "TEQSA": "P",

    # Health
    "Department of Health": "Q",
    "Department of Health and Aged Care": "Q",
    "Therapeutic Goods Administration": "Q",
    "TGA": "Q",
    "Australian Health Practitioner Regulation Agency": "Q",
    "AHPRA": "Q",

    # Arts and recreation
    "Department of Infrastructure, Transport, Regional Development, Communications and the Arts": "R",
    "Screen Australia": "R",
    "Australia Council": "R",

    # Cross-cutting regulators
    "Safe Work Australia": "X",
    "Comcare": "X",
    "Fair Work Commission": "X",
    "Fair Work Ombudsman": "X",
    "Australian Competition and Consumer Commission": "X",
    "ACCC": "X",
    "Office of the Australian Information Commissioner": "X",
    "OAIC": "X",
    "Australian Taxation Office": "X",
    "ATO": "X",
}

# Keyword to ANZSIC mapping for title-based classification
KEYWORD_TO_ANZSIC = {
    # Agriculture
    "agriculture": "A",
    "farming": "A",
    "livestock": "A",
    "fisheries": "A",
    "forestry": "A",
    "wheat": "A",
    "wool": "A",
    "dairy": "A",
    "meat": "A",

    # Mining
    "mining": "B",
    "petroleum": "B",
    "oil": "B",
    "gas": "B",
    "minerals": "B",
    "coal": "B",
    "offshore": "B",

    # Manufacturing
    "manufacturing": "C",
    "industrial": "C",

    # Utilities
    "electricity": "D",
    "energy": "D",
    "water": "D",
    "waste": "D",
    "renewable": "D",
    "carbon": "D",
    "emissions": "D",

    # Construction
    "building": "E",
    "construction": "E",

    # Trade
    "customs": "F",
    "export": "F",
    "import": "F",
    "tariff": "F",
    "trade": "F",

    # Retail
    "retail": "G",
    "consumer": "G",

    # Accommodation
    "tourism": "H",
    "hospitality": "H",

    # Transport
    "aviation": "I",
    "aircraft": "I",
    "airline": "I",
    "airport": "I",
    "maritime": "I",
    "shipping": "I",
    "navigation": "I",
    "road": "I",
    "transport": "I",
    "rail": "I",

    # Telecommunications
    "telecommunications": "J",
    "broadcasting": "J",
    "radio": "J",
    "spectrum": "J",
    "media": "J",

    # Financial
    "banking": "K",
    "financial": "K",
    "insurance": "K",
    "superannuation": "K",
    "credit": "K",
    "securities": "K",
    "corporations": "K",

    # Real estate
    "property": "L",
    "real estate": "L",

    # Professional services
    "patent": "M",
    "trademark": "M",
    "intellectual property": "M",

    # Administrative
    "administrative": "N",

    # Public administration
    "defence": "O",
    "military": "O",
    "police": "O",
    "security": "O",
    "border": "O",
    "migration": "O",
    "immigration": "O",
    "citizenship": "O",
    "veteran": "O",
    "electoral": "O",
    "parliament": "O",

    # Education
    "education": "P",
    "university": "P",
    "school": "P",
    "training": "P",
    "tertiary": "P",

    # Health
    "health": "Q",
    "medical": "Q",
    "pharmaceutical": "Q",
    "therapeutic": "Q",
    "aged care": "Q",
    "disability": "Q",
    "hospital": "Q",

    # Arts
    "arts": "R",
    "cultural": "R",
    "heritage": "R",
    "sport": "R",
    "racing": "R",
    "gambling": "R",

    # Other services
    "charity": "S",
    "community": "S",
}

# Cross-cutting legislation keywords (applies to all industries)
CROSS_CUTTING_KEYWORDS = [
    "taxation",
    "tax",
    "workplace",
    "employment",
    "fair work",
    "occupational health",
    "work health",
    "privacy",
    "competition",
    "consumer protection",
    "corporations law",
    "company",
    "ato",
]


def classify_by_title(title: str) -> str:
    """
    Classify legislation by its title using keyword matching.

    Returns ANZSIC code or 'U' for unclassified.
    """
    title_lower = title.lower()

    # Check for cross-cutting keywords first
    for keyword in CROSS_CUTTING_KEYWORDS:
        if keyword in title_lower:
            return "X"

    # Check industry keywords
    for keyword, anzsic in KEYWORD_TO_ANZSIC.items():
        if keyword in title_lower:
            return anzsic

    return "U"  # Unclassified
