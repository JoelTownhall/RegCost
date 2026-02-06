"""
Data collection module for Australian federal regulations.
Handles scraping/downloading from legislation.gov.au

Based on the browse/search page structure:
- Acts: /search/collection(Act)/status(InForce)/sort(title%20asc)
- Legislative Instruments: /search/collection(LegislativeInstrument)/status(InForce)/sort(title%20asc)
- Notifiable Instruments: /search/collection(NotifiableInstrument)/status(InForce)/sort(title%20asc)
"""
import json
import logging
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from urllib.parse import urljoin
from io import BytesIO

import requests
from bs4 import BeautifulSoup

try:
    import pdfplumber
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False
    print("Note: Install pdfplumber for PDF text extraction: pip install pdfplumber")

import config

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(config.LOGS_DIR / config.ERROR_LOG_FILENAME),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class LegislationScraper:
    """
    Scraper for Australian Federal Register of Legislation.

    Downloads Acts, Legislative Instruments, and Notifiable Instruments
    and extracts text for regulatory burden analysis.
    """

    BASE_URL = "https://www.legislation.gov.au"

    # Search URL patterns for each collection type
    SEARCH_PATTERNS = {
        'act': {
            'inforce': '/search/collection(Act)/status(InForce)/type(Principal)/sort(title%20asc)',
            'notinforce': '/search/collection(Act)/status(NotInForce)/type(Principal)/sort(title%20asc)',
        },
        'legislativeinstrument': {
            'inforce': '/search/collection(LegislativeInstrument)/status(InForce)/type(Principal)/sort(title%20asc)',
            'notinforce': '/search/collection(LegislativeInstrument)/status(NotInForce)/type(Principal)/sort(title%20asc)',
        },
        'notifiableinstrument': {
            'inforce': '/search/collection(NotifiableInstrument)/status(InForce)/type(Principal)/sort(title%20asc)',
            'notinforce': '/search/collection(NotifiableInstrument)/status(NotInForce)/type(Principal)/sort(title%20asc)',
        }
    }

    def __init__(self, output_dir: Optional[Path] = None, delay: float = 1.5):
        self.output_dir = output_dir or config.DATA_DIR
        self.delay = delay

        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (compatible; LegislationResearchBot/1.0)',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-AU,en;q=0.9',
        })

        # Setup directories
        self.dirs = {
            'acts': self.output_dir / 'acts',
            'instruments': self.output_dir / 'legislative_instruments',
            'notifiable': self.output_dir / 'notifiable_instruments',
            'metadata': self.output_dir / 'metadata',
            'pdfs': self.output_dir / 'pdfs',
        }
        for d in self.dirs.values():
            d.mkdir(parents=True, exist_ok=True)

        # Progress tracking
        self.index_file = self.output_dir / 'legislation_index.json'
        self.progress_file = self.output_dir / 'download_progress.json'
        self.index = self._load_index()
        self.progress = self._load_progress()

    def _load_index(self) -> Dict:
        if self.index_file.exists():
            with open(self.index_file, encoding='utf-8') as f:
                return json.load(f)
        return {'acts': {}, 'instruments': {}, 'notifiable': {}}

    def _save_index(self):
        with open(self.index_file, 'w', encoding='utf-8') as f:
            json.dump(self.index, f, indent=2)

    def _load_progress(self) -> Dict:
        if self.progress_file.exists():
            with open(self.progress_file, encoding='utf-8') as f:
                data = json.load(f)
                # Convert lists back to sets
                return {
                    'downloaded': set(data.get('downloaded', [])),
                    'failed': set(data.get('failed', []))
                }
        return {'downloaded': set(), 'failed': set()}

    def _save_progress(self):
        progress = {
            'downloaded': list(self.progress['downloaded']),
            'failed': list(self.progress['failed'])
        }
        with open(self.progress_file, 'w', encoding='utf-8') as f:
            json.dump(progress, f, indent=2)

    def _make_request(self, url: str, retries: int = 3) -> Optional[requests.Response]:
        """Make HTTP GET request with retry logic."""
        for attempt in range(retries):
            try:
                time.sleep(self.delay)
                response = self.session.get(url, timeout=30)

                if response.status_code == 200:
                    return response
                elif response.status_code == 429:
                    wait_time = int(response.headers.get('Retry-After', 60))
                    logger.warning(f"Rate limited. Waiting {wait_time}s...")
                    time.sleep(wait_time)
                elif response.status_code == 404:
                    return None
                else:
                    logger.warning(f"HTTP {response.status_code} for {url}")

            except requests.RequestException as e:
                logger.error(f"Request error (attempt {attempt+1}): {e}")
                time.sleep(5 * (attempt + 1))

        return None

    def scrape_search_page(self, url: str, page: int = 1) -> Tuple[List[Dict], int]:
        """Scrape a search results page and return items + total pages."""
        if page > 1:
            url = f"{url}/page({page})"

        full_url = urljoin(self.BASE_URL, url)
        logger.info(f"Fetching: {full_url}")

        response = self._make_request(full_url)
        if not response:
            return [], 0

        soup = BeautifulSoup(response.text, 'lxml' if 'lxml' in str(BeautifulSoup.__init__) else 'html.parser')
        items = []

        # Find legislation links - they have IDs like C2024A00001 or F2024L00001
        for link in soup.find_all('a', href=True):
            href = link['href']

            # Match legislation detail page URLs
            match = re.match(r'^/([CF]\d{4}[A-Z]\d+)', href)
            if match:
                register_id = match.group(1)
                title = link.get_text(strip=True)

                # Skip if it's just the ID with no title
                if title and title != register_id and len(title) > 5:
                    items.append({
                        'register_id': register_id,
                        'title': title,
                        'url': urljoin(self.BASE_URL, href)
                    })

        # Deduplicate
        seen = set()
        unique_items = []
        for item in items:
            if item['register_id'] not in seen:
                seen.add(item['register_id'])
                unique_items.append(item)

        # Get total pages from pagination
        total_pages = 1
        page_links = soup.find_all('a', href=re.compile(r'/page\(\d+\)'))
        for pl in page_links:
            m = re.search(r'/page\((\d+)\)', pl['href'])
            if m:
                total_pages = max(total_pages, int(m.group(1)))

        return unique_items, total_pages

    def get_legislation_details(self, register_id: str) -> Dict:
        """Get details and download links for a legislation item."""
        url = f"{self.BASE_URL}/{register_id}/latest"

        response = self._make_request(url)
        if not response:
            return {}

        soup = BeautifulSoup(response.text, 'html.parser')
        details = {
            'register_id': register_id,
            'download_links': {},
            'html_text': '',
        }

        # Extract any inline text content
        main_content = soup.find('main') or soup.find('article') or soup.find('div', class_=re.compile(r'content|body', re.I))
        if main_content:
            # Remove script and style
            for tag in main_content(['script', 'style', 'nav', 'header', 'footer']):
                tag.decompose()
            details['html_text'] = main_content.get_text(separator=' ', strip=True)

        # Find download links
        for a in soup.find_all('a', href=True):
            href = a['href'].lower()
            text = a.get_text(strip=True).lower()

            if '.pdf' in href or 'pdf' in text:
                if 'authorised' in text or 'download' in text or 'pdf' in text:
                    details['download_links']['pdf'] = urljoin(self.BASE_URL, a['href'])
            elif '.docx' in href or 'word' in text:
                details['download_links']['docx'] = urljoin(self.BASE_URL, a['href'])
            elif '.rtf' in href:
                details['download_links']['rtf'] = urljoin(self.BASE_URL, a['href'])

        # Look for text version link
        text_link = soup.find('a', href=re.compile(r'/text$', re.I))
        if text_link:
            details['text_url'] = urljoin(self.BASE_URL, text_link['href'])

        return details

    def download_pdf(self, url: str, filepath: Path) -> bool:
        """Download a PDF file."""
        if filepath.exists():
            logger.debug(f"Skipping (exists): {filepath}")
            return True

        try:
            time.sleep(self.delay)
            response = self.session.get(url, timeout=120, stream=True)
            response.raise_for_status()

            filepath.parent.mkdir(parents=True, exist_ok=True)

            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            logger.info(f"Downloaded: {filepath.name}")
            return True

        except Exception as e:
            logger.error(f"Download failed {url}: {e}")
            return False

    def extract_text_from_pdf(self, filepath: Path) -> str:
        """Extract text from a PDF file."""
        if not PDF_SUPPORT:
            logger.warning("PDF support not available. Install pdfplumber.")
            return ""

        try:
            text_parts = []
            with pdfplumber.open(filepath) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
            return "\n\n".join(text_parts)
        except Exception as e:
            logger.error(f"PDF extraction failed for {filepath}: {e}")
            return ""

    def fetch_html_text(self, register_id: str) -> str:
        """Try to fetch the HTML text version of legislation."""
        url = f"{self.BASE_URL}/{register_id}/latest/text"

        response = self._make_request(url)
        if not response:
            return ""

        soup = BeautifulSoup(response.text, 'html.parser')

        # Remove navigation elements
        for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
            tag.decompose()

        # Get main content
        main = soup.find('main') or soup.find('article') or soup.find('div', id='content') or soup
        text = main.get_text(separator=' ', strip=True)

        # Clean up excessive whitespace
        text = re.sub(r'\s+', ' ', text)

        return text if len(text) > 500 else ""

    def process_item(self, item: Dict, collection: str) -> Optional[Dict]:
        """Process a single legislation item - fetch text and metadata."""
        register_id = item['register_id']

        if register_id in self.progress['downloaded']:
            # Load existing data
            meta_path = self.dirs['metadata'] / f"{register_id}.json"
            if meta_path.exists():
                with open(meta_path, encoding='utf-8') as f:
                    return json.load(f)
            return None

        logger.info(f"Processing: {item.get('title', register_id)[:60]}...")

        # Get details
        details = self.get_legislation_details(register_id)

        text = ""

        # Strategy 1: Try HTML text version
        text = self.fetch_html_text(register_id)

        # Strategy 2: Download and extract PDF if HTML didn't work
        if not text and details.get('download_links', {}).get('pdf'):
            pdf_url = details['download_links']['pdf']
            pdf_path = self.dirs['pdfs'] / f"{register_id}.pdf"

            if self.download_pdf(pdf_url, pdf_path):
                text = self.extract_text_from_pdf(pdf_path)

        # Strategy 3: Use inline HTML text as fallback
        if not text and details.get('html_text'):
            text = details['html_text']

        if not text:
            logger.warning(f"Could not extract text for {register_id}")
            self.progress['failed'].add(register_id)
            self._save_progress()
            return None

        # Build result
        result = {
            'id': register_id,
            'register_id': register_id,
            'title': item.get('title', ''),
            'collection': collection,
            'url': item.get('url', f"{self.BASE_URL}/{register_id}"),
            'text': text,
            'text_length': len(text),
            'download_links': details.get('download_links', {}),
            'fetched_at': datetime.now().isoformat(),
        }

        # Extract year from register_id
        year_match = re.match(r'[CF](\d{4})', register_id)
        if year_match:
            result['year'] = int(year_match.group(1))

        # Determine department from title (heuristic)
        result['department'] = self._extract_department(item.get('title', ''))

        # Save metadata
        meta_path = self.dirs['metadata'] / f"{register_id}.json"
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        # Update progress
        self.progress['downloaded'].add(register_id)

        # Update index
        index_key = {
            'act': 'acts',
            'legislativeinstrument': 'instruments',
            'notifiableinstrument': 'notifiable'
        }.get(collection, 'instruments')

        self.index[index_key][register_id] = {
            'title': item.get('title', ''),
            'downloaded': True,
            'text_length': len(text)
        }

        self._save_progress()

        return result

    def _extract_department(self, title: str) -> str:
        """Extract administering department from title using heuristics."""
        title_lower = title.lower()

        department_keywords = {
            'Treasury': ['tax', 'financial', 'banking', 'superannuation', 'revenue', 'treasury'],
            'Health': ['health', 'therapeutic', 'medical', 'pharmaceutical', 'medicare', 'aged care'],
            'Education': ['education', 'school', 'university', 'tertiary', 'student'],
            'Defence': ['defence', 'military', 'veteran', 'armed forces'],
            'Home Affairs': ['migration', 'citizenship', 'border', 'immigration', 'customs', 'security'],
            'Agriculture': ['agriculture', 'biosecurity', 'fisheries', 'plant', 'animal', 'quarantine'],
            'Environment': ['environment', 'water', 'biodiversity', 'heritage', 'climate', 'emissions'],
            'Industry': ['industry', 'science', 'innovation', 'research', 'technology'],
            'Infrastructure': ['transport', 'infrastructure', 'aviation', 'maritime', 'road', 'rail'],
            'Attorney-General': ['criminal', 'legal', 'family law', 'court', 'judicial', 'bankruptcy'],
            'Social Services': ['social', 'disability', 'ndis', 'welfare', 'child support'],
            'Employment': ['employment', 'workplace', 'fair work', 'workers'],
        }

        for dept, keywords in department_keywords.items():
            if any(kw in title_lower for kw in keywords):
                return dept

        return 'Other'

    def scrape_collection(self, collection: str, status: str = 'inforce',
                          max_items: Optional[int] = None) -> List[Dict]:
        """Scrape all items from a collection."""
        logger.info(f"Scraping {collection} ({status})...")

        search_url = self.SEARCH_PATTERNS.get(collection, {}).get(status)
        if not search_url:
            logger.error(f"Unknown collection/status: {collection}/{status}")
            return []

        all_items = []
        results = []

        # Get first page
        items, total_pages = self.scrape_search_page(search_url, page=1)
        all_items.extend(items)
        logger.info(f"Found {total_pages} pages for {collection} ({status})")

        # Get remaining pages
        for page in range(2, total_pages + 1):
            if max_items and len(all_items) >= max_items:
                break
            items, _ = self.scrape_search_page(search_url, page=page)
            all_items.extend(items)
            logger.info(f"Collected {len(all_items)} items from {page} pages")

        # Limit if specified
        if max_items:
            all_items = all_items[:max_items]

        # Process items
        for i, item in enumerate(all_items):
            logger.info(f"Processing {i+1}/{len(all_items)}: {item.get('title', '')[:50]}")
            result = self.process_item(item, collection)
            if result:
                results.append(result)

            # Save periodically
            if (i + 1) % 20 == 0:
                self._save_index()

        self._save_index()
        return results

    def scrape_regulations(self, max_items: Optional[int] = None,
                           collections: Optional[List[str]] = None,
                           status: str = 'inforce') -> List[Dict]:
        """
        Main scraping method - fetches regulations and extracts text.

        Args:
            max_items: Maximum total items to scrape
            collections: List of collection types ('act', 'legislativeinstrument', 'notifiableinstrument')
            status: 'inforce' or 'notinforce'
        """
        if collections is None:
            collections = ['act', 'legislativeinstrument']

        all_results = []
        items_per_collection = max_items // len(collections) if max_items else None

        for collection in collections:
            try:
                results = self.scrape_collection(collection, status, items_per_collection)
                all_results.extend(results)
                logger.info(f"Completed {collection}: {len(results)} items")
            except KeyboardInterrupt:
                logger.info("Interrupted. Saving progress...")
                self._save_index()
                self._save_progress()
                raise
            except Exception as e:
                logger.error(f"Error scraping {collection}: {e}")
                continue

        return all_results

    def save_data(self, regulations: list, filepath: Optional[Path] = None):
        """Save scraped regulations to JSON file."""
        filepath = filepath or (config.DATA_DIR / config.DATA_FILENAME)

        data = {
            'scraped_at': datetime.now().isoformat(),
            'total_regulations': len(regulations),
            'regulations': regulations,
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved {len(regulations)} regulations to {filepath}")
        return filepath

    def load_data(self, filepath: Optional[Path] = None) -> list:
        """Load previously scraped regulations from JSON file."""
        filepath = filepath or (config.DATA_DIR / config.DATA_FILENAME)

        if not filepath.exists():
            logger.warning(f"No data file found at {filepath}")
            return []

        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        return data.get('regulations', [])

    def load_from_metadata(self) -> List[Dict]:
        """Load all regulations from individual metadata files."""
        regulations = []
        meta_dir = self.dirs['metadata']

        for meta_file in meta_dir.glob('*.json'):
            try:
                with open(meta_file, encoding='utf-8') as f:
                    reg = json.load(f)
                    if reg.get('text'):
                        regulations.append(reg)
            except Exception as e:
                logger.error(f"Error loading {meta_file}: {e}")

        logger.info(f"Loaded {len(regulations)} regulations from metadata files")
        return regulations


def generate_sample_data(num_samples: int = 100) -> list:
    """
    Generate sample regulation data for testing when scraping fails.
    """
    import random

    logger.info(f"Generating {num_samples} sample regulations for testing...")

    departments = [
        "Treasury", "Health", "Education", "Defence", "Home Affairs",
        "Agriculture", "Environment", "Industry", "Infrastructure", "Attorney-General's",
    ]

    name_templates = [
        "{dept} ({topic}) Regulations {year}",
        "{dept} {topic} Rules {year}",
        "{topic} ({dept}) Instrument {year}",
        "Financial Framework ({topic}) Determination {year}",
    ]

    topics = [
        "Reporting", "Compliance", "Licensing", "Registration",
        "Assessment", "Approval", "Certification", "Standards",
        "Fees", "Procedures", "Administration", "Management",
    ]

    text_templates = [
        "The applicant must provide all required documentation within 30 days.",
        "A person shall not engage in the regulated activity without a valid licence.",
        "The authority is required to consider all submissions received.",
        "It is prohibited to disclose confidential information.",
        "The licensee must maintain accurate records.",
        "Where the conditions are met, approval shall be granted.",
        "The required information must be submitted in the prescribed form.",
        "A person may not operate without the necessary authorisation.",
        "The holder shall comply with all conditions of the approval.",
        "The Minister must publish the determination within 14 days.",
        "Applicants are required to demonstrate financial viability.",
        "The use of prohibited substances is strictly forbidden.",
        "All parties must adhere to the prescribed standards.",
        "The regulator shall assess each application on its merits.",
        "Required qualifications must be obtained before commencement.",
        "The authority may not unreasonably withhold consent.",
        "Operators must ensure compliance with safety requirements.",
        "The prescribed fees shall be paid prior to processing.",
        "It is prohibited to make false or misleading statements.",
        "The applicant must notify the authority of any changes.",
    ]

    regulations = []

    for i in range(num_samples):
        dept = random.choice(departments)
        topic = random.choice(topics)
        year = random.randint(2000, 2024)
        name_template = random.choice(name_templates)

        title = name_template.format(dept=dept, topic=topic, year=year)

        num_paragraphs = random.randint(20, 100)
        paragraphs = [random.choice(text_templates) for _ in range(num_paragraphs)]

        filler = [
            "This regulation applies to all relevant persons.",
            "The purpose of this instrument is to prescribe standards.",
            "Definitions are provided in Schedule 1.",
            "This regulation commences on the day after registration.",
            "Part 2 sets out the application process.",
            "Part 3 deals with compliance and enforcement.",
        ]
        paragraphs.extend(random.sample(filler, min(len(filler), 3)))
        random.shuffle(paragraphs)

        text = "\n\n".join(paragraphs)

        regulations.append({
            'id': f"F{year}L{str(i).zfill(5)}",
            'register_id': f"F{year}L{str(i).zfill(5)}",
            'title': title,
            'text': text,
            'text_length': len(text),
            'department': dept,
            'year': year,
            'collection': 'legislativeinstrument',
            'is_sample': True,
            'fetched_at': datetime.now().isoformat(),
        })

    logger.info(f"Generated {len(regulations)} sample regulations")
    return regulations


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Download Australian Federal Legislation')
    parser.add_argument('--output', '-o', default='./data', help='Output directory')
    parser.add_argument('--collection', '-c',
                       choices=['act', 'legislativeinstrument', 'notifiableinstrument', 'all'],
                       default='all', help='Collection to download')
    parser.add_argument('--max', '-m', type=int, default=100, help='Max items to download')
    parser.add_argument('--sample', action='store_true', help='Generate sample data instead')

    args = parser.parse_args()

    if args.sample:
        regulations = generate_sample_data(args.max)
        scraper = LegislationScraper()
        scraper.save_data(regulations)
    else:
        scraper = LegislationScraper(output_dir=Path(args.output))

        collections = None if args.collection == 'all' else [args.collection]
        regulations = scraper.scrape_regulations(
            max_items=args.max,
            collections=collections
        )

        if regulations:
            scraper.save_data(regulations)
        else:
            print("No regulations scraped. Generating sample data...")
            regulations = generate_sample_data(args.max)
            scraper.save_data(regulations)
