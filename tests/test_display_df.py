from __future__ import annotations

import pandas as pd
from streamlit.dataframe_util import convert_pandas_df_to_arrow_bytes

from skopos.ui import prepare_display_df


def test_prepare_display_df_deduplicates_headers() -> None:
    df = pd.DataFrame([[1, 2]], columns=["Порты", "Порты"])
    out = prepare_display_df(df)
    assert list(out.columns) == ["Порты", "Порты (2)"]
    convert_pandas_df_to_arrow_bytes(out)


def test_prepare_display_df_null_objects() -> None:
    df = pd.DataFrame({"label": [None, "ok"]})
    out = prepare_display_df(df)
    assert out.iloc[0]["label"] == "—"
    convert_pandas_df_to_arrow_bytes(out)


def test_prepare_display_df_float_ports() -> None:
    df = pd.DataFrame({"dest_port": [22.0, None, 80.0]})
    out = prepare_display_df(df)
    assert str(out["dest_port"].dtype) == "Int64"
    convert_pandas_df_to_arrow_bytes(out)


def test_labeled_internal_keys_avoid_duplicate_headers() -> None:
    """Simulate old bug: two columns mapped to the same Russian label."""
    df = pd.DataFrame(
        {
            "ports_targeted": [5],
            "port_list": ["22,80"],
        }
    )
    # Internal keys stay unique even if labels would collide.
    labeled = df.rename(columns={"ports_targeted": "Порты", "port_list": "Порты"})
    with_duplicate = prepare_display_df(labeled)
    assert list(with_duplicate.columns) == ["Порты", "Порты (2)"]
    convert_pandas_df_to_arrow_bytes(with_duplicate)
