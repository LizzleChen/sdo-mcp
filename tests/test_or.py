"""Oregon's latest rolling county releases preserve their distinct vintages."""

from sdo_mcp import server


def _point(res, year):
    return next(p for p in res["series"] if p["year"] == year)


def test_benton_and_deschutes_round_trip():
    benton = server.get_forecast("OR", "county", "Benton", "population")
    assert benton["status"] == "ok"
    assert _point(benton, 2020) == {"year": 2020, "value": 95184, "datatype": "estimate"}
    assert _point(benton, 2045) == {"year": 2045, "value": 112546, "datatype": "projection"}
    assert benton["source"]["vintage"] == "2025 regional release"
    assert benton["source"]["base_year"] == 2024
    assert 2024 not in [p["year"] for p in benton["series"]]
    deschutes = server.get_forecast("OR", "county", "41017", "population")
    assert _point(deschutes, 2025) == {
        "year": 2025, "value": 213886, "datatype": "estimate"
    }
    assert _point(deschutes, 2045) == {
        "year": 2045, "value": 278432, "datatype": "projection"
    }
    assert deschutes["source"]["vintage"] == "2026 regional release"
    assert deschutes["source"]["base_year"] == 2025


def test_explicit_2026_labels_and_years_are_preserved():
    res = server.get_forecast("OR", "county", "Deschutes", "population")
    years = [p["year"] for p in res["series"]]
    assert years == [1990, 2000, 2010, *range(2020, 2077)]
    assert all(
        _point(res, y)["datatype"] == "estimate"
        for y in (1990, 2000, 2010, *range(2020, 2026))
    )
    assert all(_point(res, y)["datatype"] == "projection" for y in range(2026, 2077))


def test_older_tables_use_the_documented_base_year_without_filling_it():
    baker = server.get_forecast("OR", "county", "Baker", "population")
    assert [p["year"] for p in baker["series"]] == list(range(2023, 2074))
    assert all(p["datatype"] == "projection" for p in baker["series"])
    assert baker["source"]["base_year"] == 2020

    clackamas = server.get_forecast("OR", "county", "Clackamas", "population")
    assert [p["year"] for p in clackamas["series"]] == list(range(2023, 2075))
    assert all(p["datatype"] == "projection" for p in clackamas["series"])
    assert clackamas["source"]["base_year"] == 2022


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
