"""
Pulls multi-year financial filings for a curated sample of real U.S.
nonprofits from ProPublica's Nonprofit Explorer API (public, no key
required -- the same public dataset ProPublica's own product runs on).

API docs: https://projects.propublica.org/nonprofits/api
"""

import json
import time
from pathlib import Path

import requests

BASE = "https://projects.propublica.org/nonprofits/api/v2"
RAW_PATH = Path(__file__).resolve().parent.parent / "data" / "raw" / "filings.json"

# search query, sector, expected state (disambiguates common-name orgs) --
# curated across a mix of sizes and causes, weighted toward journalism/
# data-transparency/health/human-services/workforce peers of the kinds of
# nonprofits doing product & data hiring. EINs are resolved live via the
# search API below, never hardcoded, so every org is verified rather than
# recalled from memory.
ORGS = [
    ("ProPublica", "Journalism", None),
    ("Marshall Project", "Journalism", None),
    ("Center for Public Integrity", "Journalism", None),
    ("Texas Tribune", "Journalism", None),
    ("Center for Investigative Reporting", "Journalism", "CA"),
    ("Candid", "Philanthropy Infrastructure", "NY"),
    ("Charity Navigator", "Philanthropy Infrastructure", None),
    ("DonorsChoose", "Education", None),
    ("Khan Academy", "Education", None),
    ("Per Scholas", "Workforce Development", None),
    ("Year Up", "Workforce Development", None),
    ("International Rescue Committee", "Human Services", None),
    ("New York Blood Center", "Health", None),
    ("Robin Hood Foundation", "Human Services", "NY"),
    ("Coalition for the Homeless", "Human Services", "NY"),
    ("Natural Resources Defense Council", "Environment", None),
    ("Sierra Club Foundation", "Environment", None),
    ("GiveDirectly", "Human Services", None),
    ("Kiva Microfunds", "Financial Inclusion", None),
    ("Feeding America", "Human Services", None),
]


def search_ein(query: str, expected_state: str | None) -> tuple[str, str] | None:
    resp = requests.get(f"{BASE}/search.json", params={"q": query}, timeout=30)
    resp.raise_for_status()
    orgs = resp.json().get("organizations", [])
    if not orgs:
        return None
    if expected_state:
        orgs = [o for o in orgs if o.get("state") == expected_state] or orgs
    top = orgs[0]
    return str(top["ein"]), top["name"]


def fetch_org(ein: str) -> dict | None:
    resp = requests.get(f"{BASE}/organizations/{ein}.json", timeout=30)
    if resp.status_code != 200:
        print(f"  MISS ({resp.status_code}) fetching EIN {ein}")
        return None
    return resp.json()


def main() -> None:
    results = []
    for query, sector, expected_state in ORGS:
        match = search_ein(query, expected_state)
        if match is None:
            print(f"NO MATCH: {query}")
            continue
        ein, matched_name = match
        print(f"{query!r} -> {matched_name} (EIN {ein})")

        data = fetch_org(ein)
        if data is None:
            continue
        results.append({"name": matched_name, "sector": sector, "data": data})
        time.sleep(0.5)  # be polite to a free public API

    RAW_PATH.parent.mkdir(parents=True, exist_ok=True)
    RAW_PATH.write_text(json.dumps(results, indent=2))
    print(f"\nSaved {len(results)} orgs -> {RAW_PATH}")


if __name__ == "__main__":
    main()
