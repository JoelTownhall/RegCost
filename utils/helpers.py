"""Shared utility functions for RegCost app."""

import pandas as pd
from typing import List, Optional


def truncate_list(items: List[str], max_items: int = 10) -> str:
    """Truncate a list of items for display, showing count of remaining."""
    if len(items) <= max_items:
        return "<br>".join(items)

    truncated = items[:max_items]
    remaining = len(items) - max_items
    return "<br>".join(truncated) + f"<br>... and {remaining} more"


def format_number(value: float, decimals: int = 0) -> str:
    """Format a number with comma separators."""
    if pd.isna(value):
        return "N/A"
    if decimals == 0:
        return f"{int(value):,}"
    return f"{value:,.{decimals}f}"


def format_percentage(value: float, decimals: int = 1) -> str:
    """Format a value as a percentage."""
    if pd.isna(value):
        return "N/A"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.{decimals}f}%"


def get_year_range(df: pd.DataFrame, year_col: str = "year") -> tuple:
    """Get min and max years from a DataFrame."""
    if df.empty or year_col not in df.columns:
        return (2000, 2025)
    return (int(df[year_col].min()), int(df[year_col].max()))


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safely divide two numbers, returning default if denominator is zero."""
    if pd.isna(denominator) or denominator == 0:
        return default
    return numerator / denominator
