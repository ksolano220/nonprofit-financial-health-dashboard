# Nonprofit Financial Health Dashboard

An interactive tool for answering the question a program officer, board
member, or new hire actually asks about a nonprofit: **is this
organization's financial position getting stronger or weaker, and
where's the risk?**

Built on real IRS Form 990 filings for 20 U.S. nonprofits (journalism,
philanthropy infrastructure, education, workforce development, human
services, health, and environment), pulled live from ProPublica's own
public Nonprofit Explorer API -- the same public dataset ProPublica's
own product runs on.

## What it answers

- Is this org's operating margin, reserve runway, and leverage trending
  up or down over the last decade-plus of filings?
- Is its revenue diversified, or dangerously concentrated in one source
  (donations, program fees, or investment income)?
- How does it stack up against sector peers on the same metrics?
- Does the latest filing trip any of the standard solvency/concentration
  risk flags?

## Data and methodology

Source: [ProPublica Nonprofit Explorer API](https://projects.propublica.org/nonprofits/api)
(public, no key required), which republishes IRS Form 990 e-file data.
`scripts/fetch_data.py` resolves every organization's EIN by live name
search rather than a hardcoded list, so each match is verified against
the API at fetch time, not recalled from memory.

**What's real vs. what's derived:** every dollar figure (revenue,
expenses, contributions, program revenue, investment income, salaries,
assets, liabilities, net assets) is a line item straight from a filed
990. The health metrics are standard ratios computed from those line
items:

```
operating_margin        = (revenue - expenses) / revenue
reserve_months           = net assets / (expenses / 12)
compensation_ratio       = (salaries + officer comp) / expenses
top_revenue_source_share = max(contribution %, program revenue %, investment income %)
leverage                  = liabilities / assets
```

**One honest limitation:** the API's summary fields don't break Form
990 Part IX expenses into program/management/fundraising columns (that
detail only exists in the full e-file XML), so this dashboard does
**not** compute the classic Charity Navigator-style "program expense
ratio." What it computes instead -- reserve runway, leverage, revenue
concentration, operating margin -- are genuine, independently useful
solvency signals, and every one is traceable to a specific filed field.

## Run it

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python scripts/fetch_data.py
python src/data_prep.py
streamlit run app.py
```

## Structure

```
scripts/fetch_data.py   resolves EINs live and pulls multi-year filings
src/data_prep.py        computes the financial-health metrics
app.py                  Streamlit dashboard
```
