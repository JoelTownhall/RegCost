"""
RegData-style Restrictions Counting Module.

Implements the Mercatus Center/QuantGov methodology for counting regulatory restrictions:
- Count restriction words: "shall", "must", "may not", "required", "prohibited"

Note: This is a simplified implementation. The full QuantGov library uses more
sophisticated NLP techniques and can map restrictions to industries.
"""
import re
import logging
from collections import defaultdict
from typing import Optional

import config

logger = logging.getLogger(__name__)


class RegDataRestrictionsCounter:
    """
    Counts regulatory restrictions using RegData/QuantGov methodology.

    The Mercatus Center approach counts specific restriction words that
    indicate binding regulatory requirements or prohibitions.
    """

    def __init__(self):
        # Restriction words to count (case-insensitive)
        # Note: "may not" is counted as a prohibition (unlike BC method)
        self.restriction_words = config.REGDATA_RESTRICTION_WORDS

        # Multi-word patterns that should be counted as single restrictions
        self.multi_word_patterns = [
            (r'\bmay\s+not\b', 'may not'),
        ]

    def _preprocess_text(self, text: str) -> str:
        """Preprocess text for counting."""
        # Convert to lowercase for matching
        text = text.lower()

        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)

        return text

    def count_restrictions(self, text: str) -> dict:
        """
        Count restrictions in a piece of text using RegData methodology.

        Returns:
            dict with counts per restriction word and total
        """
        if not text:
            return {'total': 0, 'by_word': {}, 'details': []}

        # Preprocess
        processed_text = self._preprocess_text(text)

        counts = {}
        details = []

        # First, count multi-word patterns and mask them
        masked_text = processed_text
        for pattern, word in self.multi_word_patterns:
            matches = list(re.finditer(pattern, masked_text, re.IGNORECASE))
            counts[word] = len(matches)

            for match in matches:
                start = max(0, match.start() - 50)
                end = min(len(masked_text), match.end() + 50)
                context = masked_text[start:end]
                details.append({
                    'word': word,
                    'position': match.start(),
                    'context': f"...{context}...",
                })

            # Mask the multi-word pattern to avoid double counting
            masked_text = re.sub(pattern, '___COUNTED___', masked_text, flags=re.IGNORECASE)

        # Count single words
        single_words = [w for w in self.restriction_words if ' ' not in w]

        for word in single_words:
            pattern = rf'\b{word}\b'
            matches = list(re.finditer(pattern, masked_text, re.IGNORECASE))
            counts[word] = len(matches)

            for match in matches:
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
            dict with restriction counts and metadata
        """
        text = regulation.get('text', '')
        title = regulation.get('title', 'Unknown')
        reg_id = regulation.get('id', 'Unknown')

        counts = self.count_restrictions(text)

        return {
            'id': reg_id,
            'title': title,
            'department': regulation.get('department', 'Unknown'),
            'year': regulation.get('year'),
            'text_length': len(text),
            'total_restrictions': counts['total'],
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
            'total_restrictions': 0,
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
                results['total_restrictions'] += analysis['total_restrictions']
                results['regulations_analyzed'] += 1

                # Aggregate by department
                dept = analysis.get('department', 'Unknown')
                results['by_department'][dept]['count'] += analysis['total_restrictions']
                results['by_department'][dept]['regulations'] += 1

                # Aggregate by word
                for word, count in analysis.get('counts_by_word', {}).items():
                    results['by_word'][word] += count

            except Exception as e:
                logger.error(f"Error analyzing regulation {reg.get('id')}: {e}")

        # Convert defaultdicts to regular dicts
        results['by_department'] = dict(results['by_department'])
        results['by_word'] = dict(results['by_word'])

        # Sort regulations by restriction count (descending)
        results['by_regulation'].sort(key=lambda x: x['total_restrictions'], reverse=True)
        results['top_regulations'] = results['by_regulation'][:10]

        logger.info(f"RegData Analysis complete: {results['total_restrictions']} restrictions "
                    f"in {results['regulations_analyzed']} regulations")

        return results


def count_regdata_restrictions(text: str) -> int:
    """Simple function to count RegData restrictions in text."""
    counter = RegDataRestrictionsCounter()
    result = counter.count_restrictions(text)
    return result['total']


# Try to import and use QuantGov if available
def try_quantgov_analysis(text: str) -> Optional[dict]:
    """
    Attempt to use the QuantGov library for analysis.
    Falls back to None if not available.
    """
    try:
        import quantgov
        # QuantGov has its own analysis methods
        # This is a placeholder for integration
        return None
    except ImportError:
        logger.debug("QuantGov library not available, using simple counting")
        return None


if __name__ == "__main__":
    # Test the counter
    test_text = """
    The applicant must provide documentation within 30 days.
    A person shall not engage in activities without approval.
    The authority is required to consider all applications.
    You may not submit false information.
    The holder must comply with conditions.
    It shall be noted that compliance is mandatory.
    The required forms must be submitted.
    Such conduct is prohibited under this regulation.
    Applicants may not misrepresent their qualifications.
    """

    counter = RegDataRestrictionsCounter()
    result = counter.count_restrictions(test_text)

    print(f"Total restrictions: {result['total']}")
    print(f"By word: {result['by_word']}")
    print("\nDetails:")
    for detail in result['details'][:5]:
        print(f"  - '{detail['word']}' at position {detail['position']}")
