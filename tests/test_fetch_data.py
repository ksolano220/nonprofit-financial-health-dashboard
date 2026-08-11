from unittest.mock import MagicMock, patch

import pytest

from scripts.fetch_data import EinMismatch, search_ein


def _mock_response(orgs):
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"organizations": orgs}
    return resp


def test_search_ein_succeeds_when_top_result_matches_expected():
    orgs = [{"ein": 142007220, "name": "Pro Publica Inc", "state": "NY"}]
    with patch("scripts.fetch_data.requests.get", return_value=_mock_response(orgs)):
        ein, name = search_ein("ProPublica", None, "142007220")
    assert ein == "142007220"
    assert name == "Pro Publica Inc"


def test_search_ein_raises_when_top_result_does_not_match_expected():
    # e.g. a same-ish-named but unrelated org outranking the intended one
    orgs = [{"ein": 630862378, "name": "Chalkhead Baptist Church", "state": "AL"}]
    with patch("scripts.fetch_data.requests.get", return_value=_mock_response(orgs)):
        with pytest.raises(EinMismatch):
            search_ein("Chalkbeat", None, "999999999")


def test_search_ein_raises_when_no_results():
    with patch("scripts.fetch_data.requests.get", return_value=_mock_response([])):
        with pytest.raises(EinMismatch):
            search_ein("Nonexistent Org", None, "111111111")


def test_search_ein_state_filter_picks_correct_candidate():
    orgs = [
        {"ein": 999999999, "name": "Robin Hood Foundation", "state": "FL"},
        {"ein": 133441066, "name": "Robin Hood Foundation", "state": "NY"},
    ]
    with patch("scripts.fetch_data.requests.get", return_value=_mock_response(orgs)):
        ein, _ = search_ein("Robin Hood Foundation", "NY", "133441066")
    assert ein == "133441066"
