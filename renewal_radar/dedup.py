"""Duplicate / re-signed client resolution (PRD section 4.3)."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from renewal_radar.matching import normalize_name


@dataclass
class DedupResult:
    active: pd.DataFrame
    superseded: pd.DataFrame


def resolve_duplicate_contracts(billing_df: pd.DataFrame) -> DedupResult:
    """Group billing rows by resolved client identity and keep the latest.

    Grouped by normalized name rather than the raw client_name string. The
    sample data's re-signed client happens to use the exact same string both
    times, but PRD 4.3 says "resolved client identity" specifically (not
    "identical string"), and a client re-signing a year apart is exactly the
    kind of row where a second data-entry pass could introduce casing or
    punctuation drift.
    """
    df = billing_df.copy()
    df["client_key"] = df["client_name"].map(normalize_name)

    active_rows = []
    superseded_rows = []
    for _, group in df.groupby("client_key", sort=False):
        if len(group) == 1:
            active_rows.append(group.iloc[0])
            continue
        ordered = group.sort_values("contract_start", ascending=False)
        active_row = ordered.iloc[0]
        active_rows.append(active_row)
        for _, row in ordered.iloc[1:].iterrows():
            row = row.copy()
            row["active_client_name"] = active_row["client_name"]
            superseded_rows.append(row)

    active = pd.DataFrame(active_rows).drop(columns=["client_key"]).reset_index(drop=True)

    superseded_columns = list(billing_df.columns) + ["active_client_name"]
    superseded = (
        pd.DataFrame(superseded_rows, columns=superseded_columns).reset_index(drop=True)
        if superseded_rows
        else pd.DataFrame(columns=superseded_columns)
    )
    return DedupResult(active=active, superseded=superseded)
