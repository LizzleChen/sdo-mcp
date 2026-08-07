"""Tennessee round-trips through the tools: known published values (read off
the committed 2022-vintage summary snapshots, recorded in plan/RESEARCH.md)
must come back out of get_forecast exactly. Offline."""

from sdo_mcp import server


def _point(res, year):
    return next(p for p in res["series"] if p["year"] == year)


def test_state_population_round_trip():
    res = server.get_forecast("TN", "state", "Tennessee", "population")
    assert res["status"] == "ok"
    assert _point(res, 2022) == {"year": 2022, "value": 7051572, "datatype": "estimate"}
    assert _point(res, 2023) == {"year": 2023, "value": 7117168, "datatype": "projection"}
    years = [p["year"] for p in res["series"]]
    assert (years[0], years[-1]) == (2022, 2070)
    src = res["source"]
    assert src["base_year"] == 2022 and src["vintage"] == "2022"
    assert "CC0" in src["license"]


def test_county_population_by_name():
    res = server.get_forecast("TN", "county", "Anderson", "population")
    assert res["status"] == "ok"
    assert res["geo"]["id"] == "47001"
    assert _point(res, 2022) == {"year": 2022, "value": 78913, "datatype": "estimate"}


def test_households_refusal_is_structural():
    res = server.get_forecast("TN", "county", "Davidson", "households")
    assert res["status"] == "not_published"
    assert "Boyd" in res["reason"]


def test_employment_state_is_pdf_only():
    res = server.get_forecast("TN", "state", "TN", "employment")
    assert res["status"] == "pdf_only"


def test_tn_shows_loaded_in_list_states():
    assert server.list_states()["states"]["TN"]["data_loaded"] is True
