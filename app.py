from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

DATA_PATH = Path(__file__).parent / "data" / "processed" / "nonprofit_metrics.csv"

st.set_page_config(page_title="Nonprofit Financial Health Dashboard", layout="wide")


@st.cache_data
def load_data() -> pd.DataFrame:
    return pd.read_csv(DATA_PATH)


df = load_data()
latest_year = df["tax_year"].max()
latest = df[df["tax_year"] == df.groupby("org")["tax_year"].transform("max")]

st.title("Nonprofit Financial Health Dashboard")
st.caption(
    "Real IRS Form 990 filings for 20 U.S. nonprofits, sourced live from "
    "[ProPublica's Nonprofit Explorer API](https://projects.propublica.org/nonprofits/api/) "
    "(no login required). Every metric below is computed directly from filed figures -- "
    "revenue, expenses, assets, liabilities -- not survey or self-reported data. "
    "See `src/data_prep.py` for exactly which 990 line items feed each metric."
)

orgs = sorted(df["org"].unique())
selected_org = st.sidebar.selectbox("Organization", orgs, index=orgs.index("Pro Publica Inc") if "Pro Publica Inc" in orgs else 0)
sector = df.loc[df["org"] == selected_org, "sector"].iloc[0]

org_df = df[df["org"] == selected_org].sort_values("tax_year")
org_latest = org_df.iloc[-1]
sector_peers = latest[latest["sector"] == sector]

st.subheader(f"{selected_org} ({sector}) -- FY{int(org_latest['tax_year'])}")

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total revenue", f"${org_latest['total_revenue']:,.0f}")
c2.metric("Operating margin", f"{org_latest['operating_margin']:.1%}")
c3.metric("Reserve runway", f"{org_latest['reserve_months']:.1f} mo")
c4.metric("Leverage (liab/assets)", f"{org_latest['leverage']:.2f}")
growth = org_latest["revenue_growth_yoy"]
c5.metric("Revenue growth YoY", f"{growth:.1%}" if pd.notna(growth) else "n/a")

st.markdown("**Risk flags**")
flags = []
if org_latest["reserve_months"] < 3:
    flags.append(f"Reserve runway is {org_latest['reserve_months']:.1f} months -- under the common 3-month solvency floor.")
if org_latest["leverage"] > 0.5:
    flags.append(f"Liabilities are {org_latest['leverage']:.0%} of assets -- elevated leverage for a nonprofit balance sheet.")
if org_latest["top_revenue_source_share"] > 0.8:
    flags.append(f"{org_latest['top_revenue_source_share']:.0%} of revenue comes from a single source -- high concentration risk if it slows.")
if pd.notna(growth) and growth < -0.10:
    flags.append(f"Revenue fell {growth:.1%} year over year.")
if not flags:
    st.success("No threshold flags tripped on the latest filing.")
else:
    for f in flags:
        st.warning(f)

st.divider()
col_left, col_right = st.columns(2)

with col_left:
    st.markdown("**Revenue vs. expenses over time**")
    trend = org_df.melt(
        id_vars="tax_year", value_vars=["total_revenue", "total_expenses"],
        var_name="metric", value_name="amount",
    )
    fig = px.line(trend, x="tax_year", y="amount", color="metric", markers=True)
    fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=320, yaxis_title="$")
    st.plotly_chart(fig, use_container_width=True)

with col_right:
    st.markdown("**Reserve runway over time (months of expenses covered)**")
    fig = px.line(org_df, x="tax_year", y="reserve_months", markers=True)
    fig.add_hline(y=3, line_dash="dot", line_color="orange", annotation_text="3-month floor")
    fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=320, yaxis_title="Months")
    st.plotly_chart(fig, use_container_width=True)

st.markdown("**Revenue mix over time**")
mix = org_df.melt(
    id_vars="tax_year",
    value_vars=["contribution_share", "program_revenue_share", "investment_income_share"],
    var_name="source", value_name="share",
)
mix["source"] = mix["source"].str.replace("_share", "").str.replace("_", " ").str.title()
fig = px.area(mix, x="tax_year", y="share", color="source")
fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=320, yaxis_tickformat=".0%")
st.plotly_chart(fig, use_container_width=True)

st.divider()
st.markdown(f"**Peer comparison -- {sector} sector, FY{int(latest_year)}**")
metric_choice = st.selectbox(
    "Metric",
    ["operating_margin", "reserve_months", "compensation_ratio", "leverage", "top_revenue_source_share"],
    format_func=lambda m: m.replace("_", " ").title(),
)
peer_fig = go.Figure()
peer_fig.add_bar(
    x=sector_peers["org"], y=sector_peers[metric_choice],
    marker_color=["#4F30EA" if o == selected_org else "#B8AEEA" for o in sector_peers["org"]],
)
peer_fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=340, yaxis_title=metric_choice.replace("_", " ").title())
st.plotly_chart(peer_fig, use_container_width=True)

with st.expander("Raw org-year data"):
    st.dataframe(org_df, use_container_width=True)
