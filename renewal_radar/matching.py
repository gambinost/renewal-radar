"""Name matching between billing and project exports (PRD section 4.1)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from rapidfuzz import fuzz

# Suffixes explicitly called out in the PRD. Kept short and literal rather than
# a generic "strip anything after a comma" rule, since a wrong guess here would
# silently mangle a real word in a client's name (e.g. "Company" the actual name).
LEGAL_SUFFIXES = {"ltd", "inc", "co", "llc", "group", "company"}

# PRD 4.1: two bands, not one cutoff.
AUTO_MATCH_THRESHOLD = 90.0
REVIEW_THRESHOLD = 70.0

_PUNCTUATION_RE = re.compile(r"[^a-z0-9\s]")


class MatchBand(str, Enum):
    AUTO = "auto"
    REVIEW = "review"
    NONE = "none"


@dataclass(frozen=True)
class MatchResult:
    billing_name: str
    project_name: str
    score: float
    band: MatchBand


def normalize_name(name: str) -> str:
    """Lowercase, strip legal suffixes, strip punctuation, collapse whitespace."""
    lowered = name.lower()
    # Punctuation becomes a space rather than being deleted outright, so
    # "Fresh&Co" and "Fresh & Co" normalize to the same token boundaries.
    cleaned = _PUNCTUATION_RE.sub(" ", lowered)
    tokens = [t for t in cleaned.split() if t not in LEGAL_SUFFIXES]
    return " ".join(tokens)


def name_similarity(name_a: str, name_b: str) -> float:
    """Normalize first, then fuzzy-match what's left (PRD 4.1 steps 1-2).

    token_set_ratio (not a plain ratio) so that word order and one name
    containing extra tokens the other lacks (e.g. "Fresh Co Marketing" vs
    "Fresh and Co Marketing") don't tank the score for what's otherwise a
    clean match.
    """
    return fuzz.token_set_ratio(normalize_name(name_a), normalize_name(name_b))


def classify_band(score: float) -> MatchBand:
    if score >= AUTO_MATCH_THRESHOLD:
        return MatchBand.AUTO
    if score >= REVIEW_THRESHOLD:
        return MatchBand.REVIEW
    return MatchBand.NONE


def match_clients(billing_names: list[str], project_names: list[str]) -> list[MatchResult]:
    """Best-scoring one-to-one pairing between two name lists.

    Deliberately a global greedy assignment (highest-scoring pair across the
    whole grid claimed first) rather than "for each billing name, take its own
    best-scoring project row" independently. That naive per-row version is
    only safe if no third name can outscore the truly-correct pair for either
    side; the PRD's own "different companies, similar names" case exists
    specifically to test that. Sorting all candidate pairs globally and
    letting a name be claimed at most once means a merely-similar imposter
    can't steal a project row out from under the client's real match.
    """
    candidates: list[tuple[float, str, str]] = []
    for billing_name in billing_names:
        for project_name in project_names:
            score = name_similarity(billing_name, project_name)
            if score >= REVIEW_THRESHOLD:
                candidates.append((score, billing_name, project_name))

    # Stable sort on score alone preserves original (billing, project) order
    # for ties, which keeps results deterministic across runs.
    candidates.sort(key=lambda item: item[0], reverse=True)

    matched_billing: set[str] = set()
    matched_project: set[str] = set()
    results: list[MatchResult] = []
    for score, billing_name, project_name in candidates:
        if billing_name in matched_billing or project_name in matched_project:
            continue
        matched_billing.add(billing_name)
        matched_project.add(project_name)
        results.append(
            MatchResult(
                billing_name=billing_name,
                project_name=project_name,
                score=score,
                band=classify_band(score),
            )
        )
    return results
