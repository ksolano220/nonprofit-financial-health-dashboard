"""
Turns the raw ProPublica Nonprofit Explorer filings into a tidy
per-org-per-year table of financial-health metrics.

The API's summary fields don't break Form 990 Part IX expenses into
program/management/fundraising columns (that level of detail lives
only in the full e-file XML), so this deliberately does NOT claim a
classic "program expense ratio." Instead it computes what the real
numbers actually support: revenue mix/concentration, operating
margin, reserve runway, compensation load, and leverage -- all
genuine solvency and sustainability signals, all traceable to a
specific field in a specific filing.
"""

import json
from pathlib import Path

import pandas as pd

RAW_PATH = Path(__file__).resolve().parent.parent / "data" / "raw" / "filings.json"
PROCESSED_PATH = Path(__file__).resolve().parent.parent / "data" / "processed" / "nonprofit_metrics.csv"


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
    df["operating_margin"] = (df["total_revenue"] - df["total_expenses"]) / df["total_revenue"]
    df["reserve_months"] = df["net_assets_end"] / (df["total_expenses"] / 12)
    df["compensation_ratio"] = (df["salaries_wages"] + df["officer_compensation"]) / df["total_expenses"]
    df["contribution_share"] = df["contributions"] / df["total_revenue"]
    df["program_revenue_share"] = df["program_revenue"] / df["total_revenue"]
    df["investment_income_share"] = df["investment_income"] / df["total_revenue"]
    df["leverage"] = df["total_liabilities_end"] / df["total_assets_end"]

    # Largest single revenue source = concentration risk proxy
    revenue_cols = ["contribution_share", "program_revenue_share", "investment_income_share"]
    df["top_revenue_source_share"] = df[revenue_cols].max(axis=1)

    df["revenue_growth_yoy"] = df.groupby("org")["total_revenue"].pct_change()
    return df


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
