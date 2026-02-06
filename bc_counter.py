"""
BC-style Requirements Counting Module.

Implements the British Columbia methodology for counting regulatory requirements:
- Count binding words: "must", "shall", "required"
- Exclude prohibitions: "must not", "shall not"
- Exclude discretionary language: "may"
"""
import re
import logging
from collections import defaultdict
from typing import Optional

import config

logger = logging.getLogger(__name__)


class BCRequirementsCounter:
    """
    Counts regulatory requirements using BC methodology.

    BC counts "regulatory requirements" as any action or step that must be
    taken under legislation, regulation, or policy.
    """

    def __init__(self):
        # Binding words to count (case-insensitive)
        self.binding_words = config.BC_BINDING_WORDS

        # Patterns to exclude (prohibitions and discretionary)
        self.exclusion_patterns = [
            r'\bmust\s+not\b',
            r'\bshall\s+not\b',
            r'\bmust\s+never\b',
            r'\bshall\s+never\b',
            r'\bnot\s+required\b',
            r'\bno\s+longer\s+required\b',
        ]

    def _preprocess_text(self, text: str) -> str:
        """Preprocess text for counting."""
        # Convert to lowercase for matching
        text = text.lower()

        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)

        return text

    def _mask_exclusions(self, text: str) -> str:
        """
        Replace exclusion patterns with placeholder to prevent counting.
        This handles "must not", "shall not", etc.
        """
        for pattern in self.exclusion_patterns:
            text = re.sub(pattern, '___EXCLUDED___', text, flags=re.IGNORECASE)
        return text

    def count_requirements(self, text: str) -> dict:
        """
        Count requirements in a piece of text using BC methodology.

        Returns:
            dict with counts per binding word and total
        """
        if not text:
            return {'total': 0, 'by_word': {}, 'details': []}

        # Preprocess
        processed_text = self._preprocess_text(text)

        # Mask exclusions first
        masked_text = self._mask_exclusions(processed_text)

        counts = {}
        details = []

        for word in self.binding_words:
            # Create pattern that matches the word as a complete word
            # This avoids matching "must" in "mustard" etc.
            pattern = rf'\b{word}\b'

            # Find all matches
            matches = list(re.finditer(pattern, masked_text, re.IGNORECASE))
            counts[word] = len(matches)

            # Store match positions for verification
            for match in matches:
                # Get context (50 chars before and after)
                start = max(0, match.start() - 50)
                end = min(len(masked_text), match.end() + 50)
                context = masked_text[start:end]
                details.append({
                    'word': word,
                    'position': match.start(),
                    'context': f"...{context}...",
                })

        total = sum(counts.values())

        return {
            'total': total,
            'by_word': counts,
            'details': details[:100],  # Limit details for memory
        }

    def analyze_regulation(self, regulation: dict) -> dict:
        """
        Analyze a single regulation and return counts.

        Args:
            regulation: dict with 'text', 'title', 'id', etc.

        Returns:
            dict with requirement counts and metadata
        """
        text = regulation.get('text', '')
        title = regulation.get('title', 'Unknown')
        reg_id = regulation.get('id', 'Unknown')

        counts = self.count_requirements(text)

        return {
            'id': reg_id,
            'title': title,
            'department': regulation.get('department', 'Unknown'),
            'year': regulation.get('year'),
            'text_length': len(text),
            'total_requirements': counts['total'],
            'counts_by_word': counts['by_word'],
        }

    def analyze_regulations(self, regulations: list) -> dict:
        """
        Analyze multiple regulations and aggregate results.

        Args:
            regulations: list of regulation dicts

        Returns:
            dict with total counts, per-regulation counts, and by-department aggregation
        """
        results = {
            'total_requirements': 0,
            'total_regulations': len(regulations),
            'regulations_analyzed': 0,
            'by_regulation': [],
            'by_department': defaultdict(lambda: {'count': 0, 'regulations': 0}),
            'by_word': defaultdict(int),
            'top_regulations': [],
        }

        for reg in regulations:
            try:
                analysis = self.analyze_regulation(reg)
                results['by_regulation'].append(analysis)
                results['total_requirements'] += analysis['total_requirements']
                results['regulations_analyzed'] += 1

                # Aggregate by department
                dept = analysis.get('department', 'Unknown')
                results['by_department'][dept]['count'] += analysis['total_requirements']
                results['by_department'][dept]['regulations'] += 1

                # Aggregate by word
                for word, count in analysis.get('counts_by_word', {}).items():
                    results['by_word'][word] += count

            except Exception as e:
                logger.error(f"Error analyzing regulation {reg.get('id')}: {e}")

        # Convert defaultdicts to regular dicts
        results['by_department'] = dict(results['by_department'])
        results['by_word'] = dict(results['by_word'])

        # Sort regulations by requirement count (descending)
        results['by_regulation'].sort(key=lambda x: x['total_requirements'], reverse=True)
        results['top_regulations'] = results['by_regulation'][:10]

        logger.info(f"BC Analysis complete: {results['total_requirements']} requirements "
                    f"in {results['regulations_analyzed']} regulations")

        return results


def count_bc_requirements(text: str) -> int:
    """Simple function to count BC requirements in text."""
    counter = BCRequirementsCounter()
    result = counter.count_requirements(text)
    return result['total']


if __name__ == "__main__":
    # Test the counter
    test_text = """
    The applicant must provide documentation within 30 days.
    A person shall not engage in activities without approval.
    The authority is required to consider all applications.
    You may submit additional materials if desired.
    The holder must comply with conditions.
    It shall be noted that compliance is mandatory.
    The required forms must be submitted.
    Applicants shall not misrepresent information.
    """

    counter = BCRequirementsCounter()
    result = counter.count_requirements(test_text)

    print(f"Total requirements: {result['total']}")
    print(f"By word: {result['by_word']}")
    print("\nDetails:")
    for detail in result['details'][:5]:
        print(f"  - '{detail['word']}' at position {detail['position']}")
