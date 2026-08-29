"""CSV loading for both exports.

Split out from pipeline.py so the Streamlit layer can hand this file-like
objects from st.file_uploader without the core logic needing to know whether
its input came from a path or an upload widget.
"""

from __future__ import annotations

import pandas as pd

BILLING_DATE_COLUMNS = ["contract_start", "contract_end"]
PROJECT_DATE_COLUMNS = ["last_delivery_date"]


def load_billing_csv(source) -> pd.DataFrame:
    df = pd.read_csv(source)
    for col in BILLING_DATE_COLUMNS:
        df[col] = pd.to_datetime(df[col])
    return df


def load_project_csv(source) -> pd.DataFrame:
    df = pd.read_csv(source)
    for col in PROJECT_DATE_COLUMNS:
        df[col] = pd.to_datetime(df[col])
    return df
