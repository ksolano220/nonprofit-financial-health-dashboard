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

# query, sector, expected_state, expected_ein -- curated across a mix of
# sizes and causes. expected_ein was confirmed against a live API search
# for each org at the time this list was built; search_ein() below
# re-verifies every fetch against it and raises rather than silently
# accepting a same-name mismatch (e.g. "Chalkbeat" vs "Chalkhead Baptist
# Church" ranking above it on a fuzzy-name search). This is a fixed
# sample of 20 known organizations, not a general-purpose org lookup --
# the expected-EIN list is exactly why that's safe to do here.
ORGS = [
    ("ProPublica", "Journalism", None, "142007220"),
    ("Marshall Project", "Journalism", None, "464353634"),
    ("Center for Public Integrity", "Journalism", None, "541512177"),
    ("Texas Tribune", "Journalism", None, "264527097"),
    ("Center for Investigative Reporting", "Journalism", "CA", "942282759"),
    ("Candid", "Philanthropy Infrastructure", "NY", "131837418"),
    ("Charity Navigator", "Philanthropy Infrastructure", None, "134148824"),
    ("DonorsChoose", "Education", None, "134129457"),
    ("Khan Academy", "Education", None, "261544963"),
    ("Per Scholas", "Workforce Development", None, "043252955"),
    ("Year Up", "Workforce Development", None, "043534407"),
    ("International Rescue Committee", "Human Services", None, "135660870"),
    ("New York Blood Center", "Health", None, "131949477"),
    ("Robin Hood Foundation", "Human Services", "NY", "133441066"),
    ("Coalition for the Homeless", "Human Services", "NY", "133072967"),
    ("Natural Resources Defense Council", "Environment", None, "132654926"),
    ("Sierra Club Foundation", "Environment", None, "946069890"),
    ("GiveDirectly", "Human Services", None, "271661997"),
    ("Kiva Microfunds", "Financial Inclusion", None, "710992446"),
    ("Feeding America", "Human Services", None, "363673599"),
]


class EinMismatch(Exception):
    pass


def search_ein(query: str, expected_state: str | None, expected_ein: str) -> tuple[str, str]:
    """
    Resolves an org name to an EIN via live search, then validates the
    result against the known-good expected_ein for this fixed 20-org
    sample. Raises EinMismatch rather than silently trusting the top
    fuzzy-match result -- a plain name search can rank an unrelated
    same-ish-named org above the intended one (confirmed during
    development: "Chalkbeat" ranked a Baptist church above the actual
    newsroom, which is why Chalkbeat isn't in this sample).
    """
    resp = requests.get(f"{BASE}/search.json", params={"q": query}, timeout=30)
    resp.raise_for_status()
    orgs = resp.json().get("organizations", [])
    if not orgs:
        raise EinMismatch(f"{query!r}: no search results at all")

    if expected_state:
        orgs = [o for o in orgs if o.get("state") == expected_state] or orgs
    top = orgs[0]
    resolved_ein = str(top["ein"]).zfill(9)

    if resolved_ein != expected_ein.zfill(9):
        raise EinMismatch(
            f"{query!r}: top search result is {top['name']!r} (EIN {resolved_ein}), "
            f"expected EIN {expected_ein}. Search ranking may have changed -- verify "
            f"manually before trusting this org's data."
        )
    return resolved_ein, top["name"]


def fetch_org(ein: str) -> dict | None:
    resp = requests.get(f"{BASE}/organizations/{ein}.json", timeout=30)
    if resp.status_code != 200:
        print(f"  MISS ({resp.status_code}) fetching EIN {ein}")
        return None
    return resp.json()


def main() -> None:
    results = []
    for query, sector, expected_state, expected_ein in ORGS:
        ein, matched_name = search_ein(query, expected_state, expected_ein)
        print(f"{query!r} -> {matched_name} (EIN {ein}, verified against expected {expected_ein})")

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
