"""
Turns the raw ProPublica Nonprofit Explorer filings into a tidy
per-org-per-year table of financial-health metrics.

The API's summary fields don't break Form 990 Part IX expenses into
program/management/fundraising columns (that level of detail lives
only in the full e-file XML), so this deliberately does NOT claim a
classic "program expense ratio." Instead it computes what the real
numbers actually support: revenue mix, operating margin, reserve
runway, compensation load, and leverage -- all genuine solvency and
sustainability signals, all traceable to a specific field in a
specific filing.
"""

import json
from pathlib import Path

import pandas as pd

RAW_PATH = Path(__file__).resolve().parent.parent / "data" / "raw" / "filings.json"
PROCESSED_PATH = Path(__file__).resolve().parent.parent / "data" / "processed" / "nonprofit_metrics.csv"

MIN_PEERS_FOR_COMPARISON = 3  # below this, a "peer comparison" is just one or two other orgs


def safe_div(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    """Returns NaN instead of inf/-inf when the denominator is zero."""
    return numerator / denominator.mask(denominator == 0)


def load_raw() -> list[dict]:
    return json.loads(RAW_PATH.read_text())


def build_rows(orgs: list[dict]) -> pd.DataFrame:
    rows = []
    for org in orgs:
        name = org["name"]
        sector = org["sector"]
        ein = org["data"]["organization"]["ein"]
        for f in org["data"].get("filings_with_data", []):
            if not f.get("totrevenue") or not f.get("totfuncexpns"):
                continue
            rows.append(
                {
                    "org": name,
                    "sector": sector,
                    "ein": ein,
                    "tax_year": f["tax_prd_yr"],
                    "total_revenue": f["totrevenue"],
                    "total_expenses": f["totfuncexpns"],
                    "contributions": f.get("totcntrbgfts") or 0,
                    "program_revenue": f.get("totprgmrevnue") or 0,
                    "investment_income": f.get("invstmntinc") or 0,
                    "salaries_wages": f.get("othrsalwages") or 0,
                    "officer_compensation": f.get("compnsatncurrofcr") or 0,
                    "total_assets_end": f.get("totassetsend") or 0,
                    "total_liabilities_end": f.get("totliabend") or 0,
                    "net_assets_end": f.get("totnetassetend") or 0,
                }
            )
    df = pd.DataFrame(rows)
    return df.sort_values(["org", "tax_year"]).reset_index(drop=True)


def add_metrics(df: pd.DataFrame) -> pd.DataFrame:
    df["operating_margin"] = safe_div(df["total_revenue"] - df["total_expenses"], df["total_revenue"])
    df["reserve_months"] = safe_div(df["net_assets_end"], df["total_expenses"] / 12)
    df["compensation_ratio"] = safe_div(df["salaries_wages"] + df["officer_compensation"], df["total_expenses"])
    df["contribution_share"] = safe_div(df["contributions"], df["total_revenue"])
    df["program_revenue_share"] = safe_div(df["program_revenue"], df["total_revenue"])
    df["investment_income_share"] = safe_div(df["investment_income"], df["total_revenue"])
    df["leverage"] = safe_div(df["total_liabilities_end"], df["total_assets_end"])

    # Largest of the three reported revenue categories -- a revenue-MIX concentration
    # proxy, not a single-donor/single-source concentration measure. 70% "contributions"
    # could be one foundation or ten thousand small donors; this can't distinguish them.
    revenue_cols = ["contribution_share", "program_revenue_share", "investment_income_share"]
    df["largest_revenue_category_share"] = df[revenue_cols].max(axis=1)

    df["revenue_growth_yoy"] = df.groupby("org")["total_revenue"].pct_change()
    return df


def latest_filing_per_org(df: pd.DataFrame) -> pd.DataFrame:
    """
    Each org's own most recent filing -- NOT necessarily the same tax
    year across orgs, since filing availability differs. Callers must
    not label this with a single shared fiscal year.
    """
    return df[df["tax_year"] == df.groupby("org")["tax_year"].transform("max")]


def sector_peer_group(latest: pd.DataFrame, sector: str, min_peers: int = MIN_PEERS_FOR_COMPARISON) -> pd.DataFrame | None:
    """
    Returns the sector's peer rows from `latest`, or None if there
    aren't enough organizations in the sector for a comparison to mean
    anything (a "peer comparison" of one or two orgs isn't one).
    """
    peers = latest[latest["sector"] == sector]
    if peers["org"].nunique() < min_peers:
        return None
    return peers


DEFAULT_RISK_THRESHOLDS = {
    "reserve_months_floor": 3.0,
    "leverage_ceiling": 0.5,
    "concentration_ceiling": 0.8,
    "revenue_decline_floor": -0.10,
}


def evaluate_risk_flags(row: pd.Series, thresholds: dict | None = None) -> list[str]:
    """
    Screening flags against illustrative, adjustable thresholds -- not
    universal nonprofit solvency standards. A flag here means "worth a
    board or program officer's attention," not "this org is in trouble."
    """
    t = thresholds or DEFAULT_RISK_THRESHOLDS
    flags = []

    reserve_months = row["reserve_months"]
    if pd.notna(reserve_months) and reserve_months < t["reserve_months_floor"]:
        flags.append(
            f"Reserve runway is {reserve_months:.1f} months -- below the "
            f"{t['reserve_months_floor']:.0f}-month illustrative floor."
        )

    leverage = row["leverage"]
    if pd.notna(leverage) and leverage > t["leverage_ceiling"]:
        flags.append(
            f"Liabilities are {leverage:.0%} of assets -- above the "
            f"{t['leverage_ceiling']:.0%} illustrative leverage ceiling."
        )

    concentration = row["largest_revenue_category_share"]
    if pd.notna(concentration) and concentration > t["concentration_ceiling"]:
        flags.append(
            f"{concentration:.0%} of revenue falls in a single reported category -- above the "
            f"{t['concentration_ceiling']:.0%} illustrative concentration ceiling. This is a "
            f"revenue-mix signal, not proof of single-donor dependence."
        )

    growth = row["revenue_growth_yoy"]
    if pd.notna(growth) and growth < t["revenue_decline_floor"]:
        flags.append(f"Revenue fell {growth:.1%} year over year.")

    return flags


def main() -> None:
    orgs = load_raw()
    df = build_rows(orgs)
    df = add_metrics(df)
    PROCESSED_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(PROCESSED_PATH, index=False)
    print(f"Wrote {len(df):,} org-years -> {PROCESSED_PATH}")
    print(f"Orgs: {df['org'].nunique()}, years: {df['tax_year'].min()}-{df['tax_year'].max()}")


if __name__ == "__main__":
    main()
