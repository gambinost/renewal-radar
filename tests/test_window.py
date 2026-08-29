import datetime as dt

import pandas as pd

from renewal_radar.window import LAPSED, LATER, RENEWING, UNKNOWN, classify_window, days_until_renewal


TODAY = dt.date(2026, 8, 29)


def test_missing_contract_end_returns_none_not_a_guessed_number():
    assert days_until_renewal(pd.NaT, TODAY) is None
    assert classify_window(None) == UNKNOWN


def test_exactly_day_zero_is_inside_the_window():
    days = days_until_renewal(pd.Timestamp("2026-08-29"), TODAY)
    assert days == 0
    assert classify_window(days) == RENEWING


def test_exactly_day_forty_five_is_inside_the_window():
    days = days_until_renewal(pd.Timestamp("2026-10-13"), TODAY)
    assert days == 45
    assert classify_window(days) == RENEWING


def test_day_forty_six_is_outside_the_window():
    days = days_until_renewal(pd.Timestamp("2026-10-14"), TODAY)
    assert days == 46
    assert classify_window(days) == LATER


def test_already_lapsed_contract_is_its_own_category():
    days = days_until_renewal(pd.Timestamp("2026-07-15"), TODAY)
    assert days < 0
    assert classify_window(days) == LAPSED
