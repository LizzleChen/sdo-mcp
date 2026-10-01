"""New York's separate state/county editions and strict original-body parsing."""

import io
import json
import math
import re

import openpyxl
import pytest

from sdo_mcp import server, store
from sdo_mcp.ingest import ny


def _state_body():
    return (ny.RAW_DIR / ny.STATE_FILES["Middle"][0]).read_bytes()


def _county_body():
    return (ny.RAW_DIR / "county_2018_001.json").read_bytes()


def _changed_workbook(change):
    workbook = openpyxl.load_workbook(io.BytesIO(_state_body()))
    try:
        change(workbook)
        output = io.BytesIO()
        workbook.save(output)
        return output.getvalue()
    finally:
        workbook.close()


def _changed_county(change):
    data = json.loads(_county_body())
    change(data)
    return json.dumps(data).encode()


@pytest.fixture
def ny_database(tmp_path, monkeypatch):
    """Adapter-local database; integration registration is tested by full rebuild."""
    path = tmp_path / "ny.sqlite"
    connection = store.connect(path, create=True)
    try:
        store.init_db(connection)
        geographies = [("36", "state", "NY", "New York")]
        geographies += [(f"36{code:03d}", "county", "NY", name + " County") for code, name in ny._counties().items()]
        connection.executemany("INSERT INTO geographies VALUES (?,?,?,?)", geographies)
        connection.executemany("INSERT INTO coverage VALUES (?,?,?,?,?)", [
            ("NY", "population", "state", "available", "October 2024 state scenarios"),
            ("NY", "population", "county", "available", "September 2018 county edition"),
            ("NY", "population", "economic_region", "available", "Ten 2018 economic-region series, not loaded"),
            ("NY", "components", "state", "available", "Published, not loaded"),
            ("NY", "components", "county", "available", "Published, not loaded"),
        ])
        ny.load(connection)
        ny.verify(connection)
    finally:
        connection.close()
    monkeypatch.setenv("SDO_DB", str(path))
    return path


def test_parser_three_state_scenarios_preserve_original_fractional_totals():
    chart = (ny.RAW_DIR / "state_chart_data_2026-10-01.js").read_text()
    for label, scenario in ny.SCENARIOS.items():
        body = (ny.RAW_DIR / ny.STATE_FILES[label][0]).read_bytes()
        observations = ny.parse_state(body, label)
        assert len(observations) == 29
        assert [point["year"] for point in observations] == list(range(2022, 2051))
        assert all(point["scenario"] == scenario for point in observations)
        assert observations[0]["value"] == 19673203
        assert observations[0]["datatype"] == "estimate"
        assert all(point["datatype"] == "projection" for point in observations[1:])
        assert isinstance(observations[-1]["value"], float)
        section = chart.split(scenario + "PopProj.addRows([", 1)[1].split("]);", 1)[0]
        independent = {int(year): float(value) for year, value in re.findall(r"\[(\d{4}),-1,([\d.]+),", section)}
        # The chart data repeats base-age rows for High/Low but only includes
        # the shared 2022 total explicitly in the Middle table.
        assert set(independent) == set(ny.STATE_YEARS if scenario == "middle" else ny.STATE_YEARS[1:])
        # The official chart rounds to ten significant digits; the workbook
        # has the underlying values. Never round the served workbook points.
        for point in observations if scenario == "middle" else observations[1:]:
            assert math.isclose(point["value"], independent[point["year"]], rel_tol=0, abs_tol=0.005)


def test_parser_county_totals_match_independent_original_excel_exports():
    for code in ny.CHECK_EXPORTS:
        points = ny.parse_county((ny.RAW_DIR / f"county_2018_{code:03d}.json").read_bytes(), code)
        exported = ny.parse_county_export((ny.RAW_DIR / f"county_2018_{code:03d}_check.xlsx").read_bytes(), code)
        assert points == exported
        assert len(points) == 26
        assert points[0]["datatype"] == "estimate"
        assert all(point["datatype"] == "projection" for point in points[1:])
        assert "scenario" not in points[0]
    assert ny.parse_county(_county_body(), 1)[-1]["value"] == 328968


def test_parser_complete_county_identifier_grid():
    rows = [point for county in ny._counties() for point in ny.parse_county(
        (ny.RAW_DIR / f"county_2018_{county:03d}.json").read_bytes(), county
    )]
    assert len(rows) == 1612
    assert {point["geo_id"] for point in rows} == {f"36{code:03d}" for code in ny._counties()}
    assert all(point["geo_level"] == "county" for point in rows)
    assert sum(point["datatype"] == "estimate" for point in rows) == 62


def test_state_county_sources_horizons_and_scenarios_are_separate(ny_database):
    state = server.get_forecast("NY", "state", "NY", "population")
    county = server.get_forecast("NY", "county", "Albany", "population")
    assert state["status"] == county["status"] == "ok"
    assert state["scenario"] == "middle"
    assert "recommend" not in state["scenario_note"].lower()
    assert "server" in state["scenario_note"].lower()
    assert county["scenario"] is None
    assert (state["source"]["base_year"], state["source"]["horizon_year"], state["source"]["vintage"]) == (2022, 2050, "October 2024")
    assert (county["source"]["base_year"], county["source"]["horizon_year"], county["source"]["vintage"]) == (2015, 2040, "September 21, 2018")
    assert state["source"]["url"] == ny.STATE_URL
    assert county["source"]["url"] == ny.COUNTY_URL
    assert state["series"][-1]["value"] == 18288497.49360878
    assert county["series"][-1]["value"] == 328968
    assert county == server.get_forecast("NY", "county", "36001", "population")
    assert county == server.get_forecast("NY", "county", "1", "population")
    assert server.get_forecast("NY", "county", "Albany", "population", scenario="middle")["status"] == "error"
    for scenario in ("middle", "high", "low"):
        assert server.get_forecast("NY", "state", "NY", "population", scenario=scenario)["status"] == "ok"


def test_no_newer_county_values_or_generated_state_history(ny_database):
    assert server.get_forecast("NY", "county", "Albany", "population", start_year=2041)["status"] == "empty_range"
    assert server.get_forecast("NY", "state", "NY", "population", end_year=2021)["status"] == "empty_range"
    assert server.get_forecast("NY", "county", "St. Lawrence", "population")["geo"]["id"] == "36089"
    for variable in ("households", "employment"):
        for level, geo in (("state", "NY"), ("county", "Albany")):
            assert server.get_forecast("NY", level, geo, variable)["status"] == "coverage_unknown"
    assert server.get_forecast("NY", "place", "Albany", "population")["status"] == "coverage_unknown"
    assert server.get_components("NY", "NY")["status"] == "not_loaded"
    assert server.get_components("NY", "Albany")["status"] == "not_loaded"


def test_published_economic_regions_are_explicitly_deferred(ny_database):
    result = server.get_forecast("NY", "economic_region", "Capital Region", "population")
    assert result["status"] == "not_loaded"
    assert result["geo_level"] == "economic_region"
    assert "Ten 2018 economic-region series" in result["reason"]
    assert "series" not in result


@pytest.mark.parametrize("sheet,cell,value,error", [
    ("Readme", "B3", "Other producer", "producer"),
    ("Readme", "B4", "October 2025", "edition"),
    ("Readme", "B5", "Low", "scenario"),
    ("PopByAge", "A1", "2022", "header"),
    ("PopByAge", "A2", 2021, "identifier"),
    ("PopByAge", "B3", -1, "duplicate"),
    ("PopByAge", "B3", 101, "identifier"),
    ("PopByAge", "C2", 19673203.5, "numeric"),
    ("PopByAge", "C3", -1, "numeric"),
    ("PopByAge", "C3", None, "numeric"),
    ("PopByAge", "C3", "NaN", "numeric"),
    ("PopByAge", "C3", True, "numeric"),
    ("PopByAge", "D3", 1, "sex totals"),
    ("Components", "A2", 2022, "year grid"),
    ("Components", "B2", -1, "numeric"),
    ("Components", "I2", 1, "balance"),
])
def test_parser_state_rejects_edition_grid_and_numeric_changes(sheet, cell, value, error):
    with pytest.raises(ValueError, match=error):
        ny.parse_state(_changed_workbook(lambda workbook: setattr(workbook[sheet][cell], "value", value)), "Middle")


def test_parser_state_rejects_missing_or_duplicate_rows():
    with pytest.raises(ValueError, match="incomplete"):
        ny.parse_state(_changed_workbook(lambda workbook: workbook["PopByAge"].delete_rows(3)), "Middle")
    with pytest.raises(ValueError, match="duplicate"):
        ny.parse_state(_changed_workbook(lambda workbook: workbook["PopByAge"].append([2022, -1, 19673203, 9605513, 10067690])), "Middle")


@pytest.mark.parametrize("table,index,value,error", [
    ("char", 0, 3, "county identifier/name"),
    ("char", 1, "Bronx", "county identifier/name"),
    ("char", 2, 3, "sex/age/race"),
    ("char", 3, "Total", "sex/age/race"),
    ("char", 4, 100, "sex/age/race"),
    ("char", 6, 1, "sex/age/race"),
    ("char", 8, -1, "numeric"),
    ("char", 8, 1.5, "numeric"),
    ("char", 8, None, "numeric"),
    ("char", 8, True, "numeric"),
    ("char", 8, float("nan"), "numeric"),
    ("comp", 0, 3, "identifier/year"),
    ("comp", 1, 2015, "identifier/year"),
    ("comp", 2, "yr99", "identifier/year"),
    ("comp", 6, -1, "numeric"),
    ("comp", 4, 1, "balance"),
])
def test_parser_county_rejects_identifiers_labels_and_values(table, index, value, error):
    with pytest.raises(ValueError, match=error):
        ny.parse_county(_changed_county(lambda data: data[table]["DATA"][0].__setitem__(index, value)), 1)


@pytest.mark.parametrize("change,error", [
    (lambda data: data["char"]["COLUMNS"].__setitem__(8, "YR_2014"), "header"),
    (lambda data: data["char"]["DATA"].pop(), "incomplete"),
    (lambda data: data["char"]["DATA"].append(data["char"]["DATA"][0]), "duplicate"),
    (lambda data: data["comp"]["DATA"].pop(), "incomplete"),
    (lambda data: data["comp"]["DATA"].append(data["comp"]["DATA"][0]), "duplicate"),
    (lambda data: data["comp"]["COLUMNS"].__setitem__(1, "2020"), "header"),
    (lambda data: data["char"]["DATA"].__setitem__(0, None), "malformed"),
])
def test_parser_county_rejects_headers_duplicates_and_incomplete_grids(change, error):
    with pytest.raises(ValueError, match=error):
        ny.parse_county(_changed_county(change), 1)


@pytest.mark.parametrize("body", [b"<html>temporarily unavailable</html>", b"PKbroken workbook", b"[]"])
def test_parser_rejects_soft_http_200_error_bodies(body):
    with pytest.raises(ValueError, match="readable population workbook"):
        ny.parse_state(body, "Middle")
    with pytest.raises(ValueError, match="readable JSON|unexpected JSON"):
        ny.parse_county(body, 1)


def test_acquire_reuses_validated_originals_without_network(monkeypatch):
    before = (ny.RAW_DIR / "manifest.json").read_bytes()
    def fail_network(*args, **kwargs):
        raise AssertionError("saved editions must not be downloaded again")
    monkeypatch.setattr(ny.fetch, "get_bytes", fail_network)
    ny.acquire()
    assert (ny.RAW_DIR / "manifest.json").read_bytes() == before


@pytest.mark.parametrize("bad_reference", [False, True])
def test_acquire_never_archives_soft_errors(tmp_path, monkeypatch, bad_reference):
    raw = tmp_path / "ny"
    originals = ny.RAW_DIR
    urls = {url: name for name, url, _ in ny._downloads()}
    monkeypatch.setattr(ny, "RAW_DIR", raw)
    first_reference = ny.REFERENCES[0][1]
    monkeypatch.setattr(ny.fetch, "get_bytes", lambda url: (
        b"<html>temporary error</html>" if not bad_reference or url == first_reference
        else (originals / urls[url]).read_bytes()
    ))
    with pytest.raises(ValueError, match="readable|unexpected reference"):
        ny.acquire()
    assert not raw.exists()
