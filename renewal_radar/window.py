"""45-day renewal window classification (PRD section 4.4)."""

from __future__ import annotations

import datetime as dt

import pandas as pd

WINDOW_DAYS = 45

LAPSED = "lapsed"
RENEWING = "renewing"
LATER = "later"
UNKNOWN = "unknown"


def days_until_renewal(contract_end, today: dt.date) -> int | None:
    """None means "no contract_end", never a guessed/defaulted number (PRD 4.2)."""
    if pd.isna(contract_end):
        return None
    end_date = pd.Timestamp(contract_end).normalize()
    return (end_date - pd.Timestamp(today)).days


def classify_window(days: int | None) -> str:
    """0 and 45 are both inclusive per PRD 4.4 ("0 <= days <= 45")."""
    if days is None:
        return UNKNOWN
    if days < 0:
        return LAPSED
    if days <= WINDOW_DAYS:
        return RENEWING
    return LATER
