import pandas as pd
import pytest

from src.data_prep import (
    DEFAULT_RISK_THRESHOLDS,
    add_metrics,
    build_rows,
    evaluate_risk_flags,
    latest_filing_per_org,
    safe_div,
    sector_peer_group,
)


def _filing(tax_year, revenue, expenses, **overrides):
    f = {
        "tax_prd_yr": tax_year,
        "totrevenue": revenue,
        "totfuncexpns": expenses,
        "totcntrbgfts": 0,
        "totprgmrevnue": 0,
        "invstmntinc": 0,
        "othrsalwages": 0,
        "compnsatncurrofcr": 0,
        "totassetsend": 0,
        "totliabend": 0,
        "totnetassetend": 0,
    }
    f.update(overrides)
    return f


def _org(name, sector, ein, filings):
    return {"name": name, "sector": sector, "data": {"organization": {"ein": ein}, "filings_with_data": filings}}


# ---------------------------------------------------------------------------
# build_rows: filtering and missing-field defaults
# ---------------------------------------------------------------------------


def test_build_rows_filters_missing_revenue_or_expenses():
    orgs = [
        _org("A", "S", 1, [_filing(2020, 100, 80), _filing(2021, None, 90), _filing(2022, 100, None)])
    ]
    df = build_rows(orgs)
    assert list(df["tax_year"]) == [2020]


def test_build_rows_defaults_missing_optional_fields_to_zero():
    orgs = [_org("A", "S", 1, [{"tax_prd_yr": 2020, "totrevenue": 100, "totfuncexpns": 80}])]
    df = build_rows(orgs)
    assert df.iloc[0]["officer_compensation"] == 0
    assert df.iloc[0]["total_assets_end"] == 0


# ---------------------------------------------------------------------------
# add_metrics: ratio calculations and zero-denominator handling
# ---------------------------------------------------------------------------


def test_operating_margin_calculation():
    orgs = [_org("A", "S", 1, [_filing(2020, 100, 80)])]
    df = add_metrics(build_rows(orgs))
    assert df.iloc[0]["operating_margin"] == pytest.approx(0.20)


def test_reserve_months_calculation():
    orgs = [_org("A", "S", 1, [_filing(2020, 100, 120, totnetassetend=60)])]  # 60 / (120/12) = 6 months
    df = add_metrics(build_rows(orgs))
    assert df.iloc[0]["reserve_months"] == pytest.approx(6.0)


def test_leverage_calculation():
    orgs = [_org("A", "S", 1, [_filing(2020, 100, 80, totliabend=40, totassetsend=200)])]
    df = add_metrics(build_rows(orgs))
    assert df.iloc[0]["leverage"] == pytest.approx(0.20)


def test_leverage_zero_assets_is_nan_not_inf():
    orgs = [_org("A", "S", 1, [_filing(2020, 100, 80, totliabend=40, totassetsend=0)])]
    df = add_metrics(build_rows(orgs))
    assert pd.isna(df.iloc[0]["leverage"])


def test_safe_div_zero_denominator_returns_nan():
    result = safe_div(pd.Series([10.0]), pd.Series([0.0]))
    assert pd.isna(result.iloc[0])


def test_safe_div_normal_case():
    result = safe_div(pd.Series([10.0]), pd.Series([4.0]))
    assert result.iloc[0] == pytest.approx(2.5)


def test_largest_revenue_category_share_is_max_of_three():
    orgs = [_org("A", "S", 1, [_filing(2020, 100, 80, totcntrbgfts=70, totprgmrevnue=20, invstmntinc=10)])]
    df = add_metrics(build_rows(orgs))
    assert df.iloc[0]["largest_revenue_category_share"] == pytest.approx(0.70)


def test_revenue_growth_yoy_first_year_is_nan_then_computed():
    orgs = [_org("A", "S", 1, [_filing(2020, 100, 80), _filing(2021, 150, 80)])]
    df = add_metrics(build_rows(orgs))
    assert pd.isna(df.iloc[0]["revenue_growth_yoy"])
    assert df.iloc[1]["revenue_growth_yoy"] == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# latest_filing_per_org: independent per-org years, not a shared fiscal year
# ---------------------------------------------------------------------------


def test_latest_filing_per_org_uses_each_orgs_own_max_year():
    orgs = [
        _org("A", "S", 1, [_filing(2019, 100, 80), _filing(2021, 110, 85)]),
        _org("B", "S", 2, [_filing(2019, 200, 150), _filing(2020, 210, 160)]),
    ]
    df = add_metrics(build_rows(orgs))
    latest = latest_filing_per_org(df)
    years = dict(zip(latest["org"], latest["tax_year"]))
    assert years == {"A": 2021, "B": 2020}  # different years: exactly the point


# ---------------------------------------------------------------------------
# sector_peer_group: suppress tiny "peer" groups
# ---------------------------------------------------------------------------


def _latest_fixture():
    rows = [
        {"org": "A", "sector": "Tiny", "operating_margin": 0.1},
        {"org": "B", "sector": "Tiny", "operating_margin": 0.1},
        {"org": "C", "sector": "Big", "operating_margin": 0.1},
        {"org": "D", "sector": "Big", "operating_margin": 0.1},
        {"org": "E", "sector": "Big", "operating_margin": 0.1},
    ]
    return pd.DataFrame(rows)


def test_sector_peer_group_returns_none_below_min_peers():
    assert sector_peer_group(_latest_fixture(), "Tiny", min_peers=3) is None


def test_sector_peer_group_returns_peers_when_enough():
    peers = sector_peer_group(_latest_fixture(), "Big", min_peers=3)
    assert peers is not None
    assert set(peers["org"]) == {"C", "D", "E"}


# ---------------------------------------------------------------------------
# evaluate_risk_flags: illustrative thresholds, not universal standards
# ---------------------------------------------------------------------------


def _row(**overrides):
    base = {
        "reserve_months": 6.0,
        "leverage": 0.2,
        "largest_revenue_category_share": 0.5,
        "revenue_growth_yoy": 0.05,
    }
    base.update(overrides)
    return pd.Series(base)


def test_evaluate_risk_flags_no_flags_when_healthy():
    assert evaluate_risk_flags(_row()) == []


def test_evaluate_risk_flags_flags_low_reserve_and_high_leverage():
    flags = evaluate_risk_flags(_row(reserve_months=1.0, leverage=0.9))
    assert len(flags) == 2
    assert any("Reserve runway" in f for f in flags)
    assert any("Liabilities are" in f for f in flags)


def test_evaluate_risk_flags_respects_custom_thresholds():
    custom = {**DEFAULT_RISK_THRESHOLDS, "reserve_months_floor": 8.0}
    flags = evaluate_risk_flags(_row(reserve_months=6.0), thresholds=custom)
    assert any("Reserve runway" in f for f in flags)  # 6 months now fails an 8-month floor


def test_evaluate_risk_flags_nan_metric_does_not_flag():
    flags = evaluate_risk_flags(_row(revenue_growth_yoy=float("nan")))
    assert flags == []
