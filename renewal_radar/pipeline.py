"""Wires matching, dedup, and window logic into the three UI sections (PRD section 5)."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import pandas as pd

from renewal_radar.dedup import resolve_duplicate_contracts
from renewal_radar.matching import MatchBand, MatchResult, match_clients
from renewal_radar.window import LAPSED, RENEWING, UNKNOWN, classify_window, days_until_renewal

REPORT_COLUMNS = [
    "client_name",
    "days_until_renewal",
    "contract_start",
    "contract_end",
    "mrr",
    "scope",
    "last_delivery_date",
    "deliverables_count",
    "match_score",
]

MANUAL_CHECK_COLUMNS = [
    "client_name",
    "reason",
    "note",
    "days_until_renewal",
    "contract_start",
    "contract_end",
    "mrr",
    "matched_project_name",
    "match_score",
]


@dataclass
class RenewalReport:
    lapsed: pd.DataFrame
    renewing: pd.DataFrame
    needs_manual_check: pd.DataFrame


def _project_lookup(project_df: pd.DataFrame) -> dict[str, pd.Series]:
    return {row["client_name"]: row for _, row in project_df.iterrows()}


def _match_lookup(matches: list[MatchResult]) -> dict[str, MatchResult]:
    return {m.billing_name: m for m in matches}


def build_report(
    billing_df: pd.DataFrame,
    project_df: pd.DataFrame,
    today: dt.date | None = None,
    confirmed_billing_names: frozenset[str] = frozenset(),
) -> RenewalReport:
    """confirmed_billing_names holds clients whose review-band match a human
    has one-click-confirmed this session (PRD 4.1's "never silently merged"
    implies a confirmation step must exist somewhere; the Streamlit layer
    passes this in from a button click). Confirming promotes that one pair
    to behave like an auto-match for this report only — it isn't written
    back to the CSV, so a re-upload starts from an unconfirmed state again.
    """
    if today is None:
        today = dt.date.today()

    dedup = resolve_duplicate_contracts(billing_df)
    active = dedup.active

    matches = match_clients(
        active["client_name"].tolist(), project_df["client_name"].tolist()
    )
    match_by_billing = _match_lookup(matches)
    project_by_name = _project_lookup(project_df)

    lapsed_rows: list[dict] = []
    renewing_rows: list[dict] = []
    manual_check_rows: list[dict] = []

    for _, billing_row in active.iterrows():
        client_name = billing_row["client_name"]
        days = days_until_renewal(billing_row["contract_end"], today)
        window = classify_window(days)
        match = match_by_billing.get(client_name)
        confirmed = client_name in confirmed_billing_names

        # A pending-review match (70-89) is never silently merged into the
        # confirmed renewal sections, no matter how urgent the renewal date
        # looks — that would show possibly-wrong scope/delivery data next to
        # a real dollar figure before a human has confirmed the identity.
        # It still needs to be visible somewhere though, so it always lands
        # in manual check (independent of the window, since "these two rows
        # are the same client" isn't a fact that becomes less true once the
        # renewal is 200 days out) and carries its own days_until_renewal so
        # urgency isn't lost while it waits for confirmation.
        if match is not None and match.band is MatchBand.REVIEW and not confirmed:
            manual_check_rows.append(
                {
                    "client_name": client_name,
                    "reason": "pending_name_confirmation",
                    "note": (
                        f"Possible match with project record "
                        f"'{match.project_name}' (score {match.score:.0f}) — "
                        "confirm before merging."
                    ),
                    "days_until_renewal": days,
                    "contract_start": billing_row["contract_start"],
                    "contract_end": billing_row["contract_end"],
                    "mrr": billing_row["mrr"],
                    "matched_project_name": match.project_name,
                    "match_score": match.score,
                }
            )

        if window == UNKNOWN:
            manual_check_rows.append(
                {
                    "client_name": client_name,
                    "reason": "missing_contract_end",
                    "note": "No contract_end on file — needs a manual look, never guessed.",
                    "days_until_renewal": None,
                    "contract_start": billing_row["contract_start"],
                    "contract_end": billing_row["contract_end"],
                    "mrr": billing_row["mrr"],
                    "matched_project_name": match.project_name if match else None,
                    "match_score": match.score if match else None,
                }
            )
            continue

        if match is not None and match.band is MatchBand.REVIEW and not confirmed:
            # Already queued for manual check above; don't also show it as a
            # confirmed renewal row.
            continue

        project_row = None
        if match is not None and (match.band is MatchBand.AUTO or confirmed):
            project_row = project_by_name.get(match.project_name)

        record = {
            "client_name": client_name,
            "days_until_renewal": days,
            "contract_start": billing_row["contract_start"],
            "contract_end": billing_row["contract_end"],
            "mrr": billing_row["mrr"],
            "scope": project_row["scope"] if project_row is not None else None,
            "last_delivery_date": project_row["last_delivery_date"] if project_row is not None else None,
            "deliverables_count": project_row["deliverables_count"] if project_row is not None else None,
            "match_score": match.score if match is not None else None,
        }

        if window == LAPSED:
            lapsed_rows.append(record)
        elif window == RENEWING:
            renewing_rows.append(record)
        # window == "later": intentionally not surfaced anywhere — PRD scopes
        # this tool to what's due, not a full contract register.

    for _, superseded_row in dedup.superseded.iterrows():
        manual_check_rows.append(
            {
                "client_name": superseded_row["client_name"],
                "reason": "superseded_contract",
                "note": (
                    f"Older contract (started {superseded_row['contract_start'].date()}), "
                    f"re-signed under the active contract for "
                    f"'{superseded_row['active_client_name']}' — kept as churn "
                    "history, not deleted."
                ),
                "days_until_renewal": None,
                "contract_start": superseded_row["contract_start"],
                "contract_end": superseded_row["contract_end"],
                "mrr": superseded_row["mrr"],
                "matched_project_name": None,
                "match_score": None,
            }
        )

    lapsed = pd.DataFrame(lapsed_rows, columns=REPORT_COLUMNS)
    renewing = pd.DataFrame(renewing_rows, columns=REPORT_COLUMNS)
    needs_manual_check = pd.DataFrame(manual_check_rows, columns=MANUAL_CHECK_COLUMNS)

    # Most-recently-lapsed first: a contract that expired yesterday is still
    # salvageable and time-sensitive; one that expired three months ago is
    # very likely already lost or otherwise resolved, so it sinks to the
    # bottom rather than burying the fresh, actionable ones.
    lapsed = lapsed.sort_values("days_until_renewal", ascending=False).reset_index(drop=True)
    renewing = renewing.sort_values("days_until_renewal", ascending=True).reset_index(drop=True)

    return RenewalReport(lapsed=lapsed, renewing=renewing, needs_manual_check=needs_manual_check)
