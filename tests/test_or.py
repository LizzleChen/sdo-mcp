"""Oregon's sparse 35-county combined product round-trips without filling gaps."""

from sdo_mcp import server


def _point(res, year):
    return next(p for p in res["series"] if p["year"] == year)


def test_benton_and_deschutes_round_trip():
    benton = server.get_forecast("OR", "county", "Benton", "population")
    assert benton["status"] == "ok"
    assert _point(benton, 2020) == {"year": 2020, "value": 95319, "datatype": "estimate"}
    assert _point(benton, 2045) == {"year": 2045, "value": 112545, "datatype": "projection"}
    deschutes = server.get_forecast("OR", "county", "41017", "population")
    assert _point(deschutes, 2020)["value"] == 199264
    assert _point(deschutes, 2045)["value"] == 292440


def test_sparse_years_and_labels_are_preserved():
    res = server.get_forecast("OR", "county", "Deschutes", "population")
    years = [p["year"] for p in res["series"]]
    assert years == [1990, 2000, 2010, 2020, *range(2025, 2046)]
    assert all(_point(res, y)["datatype"] == "estimate" for y in (1990, 2000, 2010, 2020))
    assert all(_point(res, y)["datatype"] == "projection" for y in range(2025, 2046))
    assert res["source"]["base_year"] == 2020


def test_state_forecast_is_structurally_not_published():
    res = server.get_forecast("OR", "state", "Oregon", "population")
    assert res["status"] == "not_published"
    assert "no official statewide" in res["reason"].lower()


def test_multnomah_is_an_explicit_source_exception_not_unfinished_data():
    res = server.get_forecast("OR", "county", "Multnomah", "population")
    assert res["status"] == "not_published"
    assert res["geo"]["id"] == "41051"
    assert "Metro" in res["reason"]
    assert "not been ingested" not in res["reason"]


def test_households_are_not_published():
    res = server.get_forecast("OR", "county", "Benton", "households")
    assert res["status"] == "not_published"
