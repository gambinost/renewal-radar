import datetime as dt

import pandas as pd

from renewal_radar.pipeline import build_report

TODAY = dt.date(2026, 8, 29)


def _billing(rows):
    df = pd.DataFrame(rows)
    df["contract_start"] = pd.to_datetime(df["contract_start"])
    df["contract_end"] = pd.to_datetime(df["contract_end"])
    return df


def _project(rows):
    df = pd.DataFrame(rows)
    df["last_delivery_date"] = pd.to_datetime(df["last_delivery_date"])
    return df


def test_missing_contract_end_lands_in_manual_check_not_dropped():
    billing = _billing(
        [
            {
                "client_name": "Pinnacle Systems Group",
                "contract_start": "2026-05-01",
                "contract_end": None,
                "mrr": 3900,
            }
        ]
    )
    project = _project(
        [
            {
                "client_name": "Pinnacle Systems",
                "scope": "Internal tooling support",
                "last_delivery_date": "2026-08-25",
                "deliverables_count": 20,
            }
        ]
    )
    report = build_report(billing, project, today=TODAY)

    assert report.lapsed.empty
    assert report.renewing.empty
    manual = report.needs_manual_check
    assert len(manual) == 1
    assert manual.iloc[0]["reason"] == "missing_contract_end"
    assert manual.iloc[0]["client_name"] == "Pinnacle Systems Group"


def test_already_lapsed_contract_surfaces_in_its_own_section():
    billing = _billing(
        [
            {
                "client_name": "Vantage Point Studios",
                "contract_start": "2026-01-15",
                "contract_end": "2026-07-15",
                "mrr": 5400,
            }
        ]
    )
    project = _project(
        [
            {
                "client_name": "Vantage Point Studio",
                "scope": "Product photography",
                "last_delivery_date": "2026-06-30",
                "deliverables_count": 6,
            }
        ]
    )
    report = build_report(billing, project, today=TODAY)

    assert len(report.lapsed) == 1
    assert report.lapsed.iloc[0]["client_name"] == "Vantage Point Studios"
    assert report.lapsed.iloc[0]["days_until_renewal"] < 0
    assert report.renewing.empty
    assert report.needs_manual_check.empty


def test_resigned_client_active_contract_drives_renewal_and_old_one_is_flagged():
    billing = _billing(
        [
            {
                "client_name": "Sterling Oak Advisors",
                "contract_start": "2024-01-01",
                "contract_end": "2024-12-31",
                "mrr": 2900,
            },
            {
                "client_name": "Sterling Oak Advisors",
                "contract_start": "2026-06-01",
                "contract_end": "2026-09-01",
                "mrr": 3400,
            },
        ]
    )
    project = _project(
        [
            {
                "client_name": "Sterling Oak Advisors",
                "scope": "Financial advisory content hub",
                "last_delivery_date": "2026-08-21",
                "deliverables_count": 13,
            }
        ]
    )
    report = build_report(billing, project, today=TODAY)

    # The 2024 contract must not show up as lapsed even though its own
    # contract_end is long past -- only the active (latest-start) contract
    # feeds the renewal calc.
    assert len(report.lapsed) == 0
    assert len(report.renewing) == 1
    assert report.renewing.iloc[0]["contract_start"] == pd.Timestamp("2026-06-01")

    superseded = report.needs_manual_check[
        report.needs_manual_check["reason"] == "superseded_contract"
    ]
    assert len(superseded) == 1
    assert superseded.iloc[0]["contract_start"] == pd.Timestamp("2024-01-01")


def test_auto_matched_row_gets_project_fields_merged_into_renewing():
    billing = _billing(
        [
            {
                "client_name": "Acme Co.",
                "contract_start": "2026-03-10",
                "contract_end": "2026-09-10",
                "mrr": 4200,
            }
        ]
    )
    project = _project(
        [
            {
                "client_name": "ACME CO",
                "scope": "Website redesign",
                "last_delivery_date": "2026-08-15",
                "deliverables_count": 14,
            }
        ]
    )
    report = build_report(billing, project, today=TODAY)

    assert len(report.renewing) == 1
    row = report.renewing.iloc[0]
    assert row["scope"] == "Website redesign"
    assert row["deliverables_count"] == 14


def test_review_band_match_is_held_for_confirmation_not_merged_into_renewing():
    billing = _billing(
        [
            {
                "client_name": "Thornwood Brand Partners",
                "contract_start": "2026-03-20",
                "contract_end": "2026-09-20",
                "mrr": 4600,
            }
        ]
    )
    project = _project(
        [
            {
                "client_name": "Thornwood Brands",
                "scope": "Packaging design",
                "last_delivery_date": "2026-08-05",
                "deliverables_count": 7,
            }
        ]
    )
    report = build_report(billing, project, today=TODAY)

    assert report.renewing.empty
    assert report.lapsed.empty
    manual = report.needs_manual_check
    assert len(manual) == 1
    assert manual.iloc[0]["reason"] == "pending_name_confirmation"
    assert manual.iloc[0]["matched_project_name"] == "Thornwood Brands"


def test_confirming_a_review_band_match_promotes_it_into_renewing():
    billing = _billing(
        [
            {
                "client_name": "Thornwood Brand Partners",
                "contract_start": "2026-03-20",
                "contract_end": "2026-09-20",
                "mrr": 4600,
            }
        ]
    )
    project = _project(
        [
            {
                "client_name": "Thornwood Brands",
                "scope": "Packaging design",
                "last_delivery_date": "2026-08-05",
                "deliverables_count": 7,
            }
        ]
    )
    report = build_report(
        billing,
        project,
        today=TODAY,
        confirmed_billing_names=frozenset({"Thornwood Brand Partners"}),
    )

    assert report.needs_manual_check.empty
    assert len(report.renewing) == 1
    assert report.renewing.iloc[0]["scope"] == "Packaging design"


def test_different_companies_with_similar_names_do_not_get_merged():
    billing = _billing(
        [
            {
                "client_name": "Meridian Health Partners",
                "contract_start": "2026-03-05",
                "contract_end": "2026-09-05",
                "mrr": 5100,
            },
            {
                "client_name": "Meridian Home Partners LLC",
                "contract_start": "2026-05-01",
                "contract_end": "2026-09-15",
                "mrr": 3300,
            },
        ]
    )
    project = _project(
        [
            {
                "client_name": "Meridian Health Partners",
                "scope": "Patient intake microsite",
                "last_delivery_date": "2026-08-12",
                "deliverables_count": 5,
            },
            {
                "client_name": "Meridian Home Partners",
                "scope": "Real estate listing site",
                "last_delivery_date": "2026-08-19",
                "deliverables_count": 10,
            },
        ]
    )
    report = build_report(billing, project, today=TODAY)

    assert len(report.renewing) == 2
    renewing_by_name = {row["client_name"]: row for _, row in report.renewing.iterrows()}
    assert renewing_by_name["Meridian Health Partners"]["scope"] == "Patient intake microsite"
    assert renewing_by_name["Meridian Home Partners LLC"]["scope"] == "Real estate listing site"
