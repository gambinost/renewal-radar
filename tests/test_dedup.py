import pandas as pd

from renewal_radar.dedup import resolve_duplicate_contracts


def _billing_df(rows):
    return pd.DataFrame(rows)


def test_single_contract_client_passes_through_unchanged():
    df = _billing_df(
        [
            {
                "client_name": "Acme Co.",
                "contract_start": pd.Timestamp("2026-03-10"),
                "contract_end": pd.Timestamp("2026-09-10"),
                "mrr": 4200,
            }
        ]
    )
    result = resolve_duplicate_contracts(df)
    assert len(result.active) == 1
    assert result.superseded.empty


def test_resigned_client_keeps_latest_start_as_active_and_flags_the_rest():
    # PRD 6: duplicate/re-signed client -> latest contract_start is active,
    # older one is flagged as superseded, not deleted.
    df = _billing_df(
        [
            {
                "client_name": "Sterling Oak Advisors",
                "contract_start": pd.Timestamp("2024-01-01"),
                "contract_end": pd.Timestamp("2024-12-31"),
                "mrr": 2900,
            },
            {
                "client_name": "Sterling Oak Advisors",
                "contract_start": pd.Timestamp("2026-06-01"),
                "contract_end": pd.Timestamp("2026-09-01"),
                "mrr": 3400,
            },
        ]
    )
    result = resolve_duplicate_contracts(df)

    assert len(result.active) == 1
    assert result.active.iloc[0]["contract_start"] == pd.Timestamp("2026-06-01")

    assert len(result.superseded) == 1
    assert result.superseded.iloc[0]["contract_start"] == pd.Timestamp("2024-01-01")
    assert result.superseded.iloc[0]["active_client_name"] == "Sterling Oak Advisors"


def test_dedup_groups_by_normalized_identity_not_raw_string():
    df = _billing_df(
        [
            {
                "client_name": "Sterling Oak Advisors",
                "contract_start": pd.Timestamp("2024-01-01"),
                "contract_end": pd.Timestamp("2024-12-31"),
                "mrr": 2900,
            },
            {
                "client_name": "STERLING OAK ADVISORS LLC",
                "contract_start": pd.Timestamp("2026-06-01"),
                "contract_end": pd.Timestamp("2026-09-01"),
                "mrr": 3400,
            },
        ]
    )
    result = resolve_duplicate_contracts(df)
    assert len(result.active) == 1
    assert len(result.superseded) == 1
