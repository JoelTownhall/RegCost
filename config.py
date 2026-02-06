"""
Configuration settings for the Australian Regulatory Burden Analysis tool.
"""
import os
from pathlib import Path

# Base paths
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
LOGS_DIR = BASE_DIR / "logs"

# Create directories if they don't exist
for dir_path in [DATA_DIR, OUTPUT_DIR, LOGS_DIR]:
    dir_path.mkdir(exist_ok=True)

# Data source configuration
LEGISLATION_BASE_URL = "https://www.legislation.gov.au"
LEGISLATION_API_URL = "https://api.prod.legislation.gov.au/v1"

# Scraping configuration
REQUEST_TIMEOUT = 30  # seconds
REQUEST_DELAY = 1.0  # seconds between requests (be respectful)
MAX_RETRIES = 3
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Scope configuration - limit to manageable subset
# Set to None to process all available regulations
MAX_REGULATIONS = 500  # Start with 500 for manageable analysis
FOCUS_DEPARTMENTS = None  # Set to list of department names to filter, e.g., ["Treasury", "Health"]

# BC Methodology configuration
BC_BINDING_WORDS = ["must", "shall", "required"]
BC_EXCLUSION_PATTERNS = [
    r"\bmust\s+not\b",
    r"\bshall\s+not\b",
    r"\bmay\b",
]

# RegData/QuantGov Methodology configuration
REGDATA_RESTRICTION_WORDS = ["shall", "must", "may not", "required", "prohibited"]

# Output configuration
REPORT_FILENAME = "regulatory_burden_report.pdf"
DATA_FILENAME = "regulations_data.json"
ERROR_LOG_FILENAME = "processing_errors.log"

# Report styling
REPORT_TITLE = "Australian Federal Regulatory Burden Stock Assessment"
REPORT_FONT_FAMILY = "Helvetica"
CHART_COLORS = {
    "bc_method": "#2E86AB",  # Blue
    "regdata_method": "#A23B72",  # Magenta
}
