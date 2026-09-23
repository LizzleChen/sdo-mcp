"""Utah Gardner baseline, scenario availability, and loader validation."""

from pathlib import Path

import openpyxl
import pytest

from sdo_mcp import server, store
from sdo_mcp.ingest import seed, ut


def _point(result, year):
    return next(point for point in result["series"] if point["year"] == year)


def test_baseline_population_households_and_jobs_round_trip_without_base_year():
    population = server.get_forecast("UT", "state", "Utah", "population")
    households = server.get_forecast("UT", "state", "UT", "households")
    jobs = server.get_forecast("UT", "state", "49", "employment")

    assert population["status"] == households["status"] == jobs["status"] == "ok"
    assert population["geo"]["id"] == households["geo"]["id"] == jobs["geo"]["id"] == "49"
    assert [point["year"] for point in population["series"]] == list(range(2025, 2066))
    assert _point(population, 2025) == {"year": 2025, "value": 3556394, "datatype": "projection"}
    assert _point(population, 2065) == {"year": 2065, "value": 5550525, "datatype": "projection"}
    assert _point(households, 2065) == {"year": 2065, "value": 2332663, "datatype": "projection"}
    assert _point(jobs, 2025) == {"year": 2025, "value": 2503944, "datatype": "projection"}
    assert _point(jobs, 2065) == {"year": 2065, "value": 3729317, "datatype": "projection"}
    for result in (population, households, jobs):
        assert result["scenario"] == "baseline"
        assert result["source"]["base_year"] is None
        assert result["source"]["horizon_year"] == 2065


def test_components_round_trip_for_state_and_county():
    state = server.get_components("UT", "UT", 2025, 2025)
    county = server.get_components("UT", "Salt Lake", 2025, 2025)

    assert state["status"] == county["status"] == "ok"
    assert state["scenario"] == county["scenario"] == "baseline"
    assert state["series"] == [{
        "year": 2025,
        "datatype": "projection",
        "births": 43784,
        "deaths": 20826,
        "net_migration": 26598,
    }]
    assert county["series"] == [{
        "year": 2025,
        "datatype": "projection",
        "births": 13733,
        "deaths": 7382,
        "net_migration": 2584,
    }]
    assert state["source"]["base_year"] is None


def test_ut_shapes_include_all_30_geographies_and_41_years():
    conn = store.connect()
    try:
        shapes = conn.execute(
            "SELECT variable, COUNT(*) AS n, COUNT(DISTINCT geo_id) AS geos, "
            "COUNT(DISTINCT year) AS years, MIN(year) AS first_year, MAX(year) AS last_year "
            "FROM observations WHERE state='UT' GROUP BY variable ORDER BY variable"
        ).fetchall()
    finally:
        conn.close()

    shape_map = {row["variable"]: tuple(row)[1:] for row in shapes}
    for variable in ("births", "deaths", "net_migration", "population", "households", "employment"):
        assert shape_map[variable] == (1230, 30, 41, 2025, 2065)


def test_explicit_and_default_baseline_are_the_same_series():
    implicit = server.get_forecast("UT", "county", "Salt Lake", "population")
    explicit = server.get_forecast("UT", "county", "Salt Lake", "population", scenario="baseline")

    assert implicit["status"] == explicit["status"] == "ok"
    assert implicit["scenario"] == explicit["scenario"] == "baseline"
    assert implicit["series"] == explicit["series"]


def test_ut_catalog_advertises_baseline_and_unloaded_scenarios():
    state = server.list_states()["states"]["UT"]

    assert state["scenarios"] == ["baseline", "high", "low"]
    assert state["default_scenario"] == "baseline"
    assert state["scenario_geo_levels"] == ["state", "county"]


@pytest.mark.parametrize("variable", ["population", "households", "employment"])
@pytest.mark.parametrize("geo_level,geo", [("state", "UT"), ("county", "Salt Lake")])
@pytest.mark.parametrize("scenario", ["high", "low"])
def test_high_low_totals_are_published_but_not_loaded(variable, geo_level, geo, scenario):
    result = server.get_forecast("UT", geo_level, geo, variable, scenario=scenario)

    assert result["status"] == "not_loaded"
    assert result["scenario"] == scenario
    assert "scenario" in result["reason"].lower()


@pytest.mark.parametrize("scenario", ["high", "low"])
def test_high_low_with_unknown_county_still_reports_invalid_geography(scenario):
    result = server.get_forecast("UT", "county", "No Such County", "population", scenario=scenario)

    assert result["status"] == "error"
    assert "county" in result["error"].lower()


@pytest.mark.parametrize("scenario", ["high", "low"])
def test_high_low_components_are_not_published_by_the_scenario_workbook(scenario):
    result = server.get_components("UT", "UT", scenario=scenario)

    assert result["status"] == "error"
    assert "components" in result["error"].lower()


def test_acquire_rejects_html_instead_of_workbook(monkeypatch):
    monkeypatch.setattr(ut.fetch, "get_bytes", lambda _url: b"<html>soft 200 error</html>")

    with pytest.raises(RuntimeError, match="not an xlsx"):
        ut.acquire()


def test_acquire_rejects_fake_pdf_payload(monkeypatch, tmp_path):
    responses = iter([
        (ut.RAW_DIR / ut.FILE).read_bytes(),
        b"%PDF fake but not parseable",
    ])
    monkeypatch.setattr(ut.fetch, "get_bytes", lambda _url: next(responses))
    monkeypatch.setattr(ut, "RAW_DIR", tmp_path / "ut")

    with pytest.raises(ValueError, match="readable PDF"):
        ut.acquire()


def _fresh_seeded_db(tmp_path: Path):
    conn = store.connect(tmp_path / "ut-loader.sqlite", create=True)
    store.init_db(conn)
    seed.load(conn)
    return conn


def _modified_workbook(monkeypatch, *, edit):
    original = openpyxl.load_workbook(ut.RAW_DIR / ut.FILE, data_only=False)
    edit(original)
    monkeypatch.setattr(openpyxl, "load_workbook", lambda *args, **kwargs: original)


@pytest.mark.parametrize("bad_value", [-1, 5036.5])
def test_loader_rejects_negative_or_fractional_county_employment_values(monkeypatch, tmp_path, bad_value):
    def edit(workbook):
        workbook["Total Employment by County"]["C5"] = bad_value

    _modified_workbook(monkeypatch, edit=edit)
    conn = _fresh_seeded_db(tmp_path)
    try:
        with pytest.raises(ValueError, match="invalid county jobs"):
            ut.load(conn)
    finally:
        conn.close()


def test_loader_rejects_duplicate_county_employment_rows(monkeypatch, tmp_path):
    def edit(workbook):
        sheet = workbook["Total Employment by County"]
        sheet["A6"] = sheet["A5"].value
        sheet["B6"] = sheet["B5"].value

    _modified_workbook(monkeypatch, edit=edit)
    conn = _fresh_seeded_db(tmp_path)
    try:
        with pytest.raises(ValueError, match="duplicate county jobs"):
            ut.load(conn)
    finally:
        conn.close()


@pytest.mark.parametrize(
    ("sheet", "first_cell", "second_cell", "match"),
    [
        ("Total Employment by County", "A1194", "A1195", "duplicate county-table state jobs"),
        ("State Industry Employment", "A5", "A6", "duplicate state jobs"),
    ],
)
def test_loader_rejects_duplicate_state_employment_rows(
    monkeypatch, tmp_path, sheet, first_cell, second_cell, match
):
    def edit(workbook):
        worksheet = workbook[sheet]
        worksheet[second_cell] = worksheet[first_cell].value
        if sheet == "Total Employment by County":
            worksheet["B1195"] = worksheet["B1194"].value
            worksheet["C1195"] = worksheet["C1194"].value
        else:
            worksheet["B6"] = worksheet["B5"].value

    _modified_workbook(monkeypatch, edit=edit)
    conn = _fresh_seeded_db(tmp_path)
    try:
        with pytest.raises(ValueError, match=match):
            ut.load(conn)
    finally:
        conn.close()


@pytest.mark.parametrize(
    ("sheet", "cell", "bad_value", "match"),
    [
        ("Total Employment by County", "C1194", -1, "invalid county-table state jobs"),
        ("State Industry Employment", "B5", 2503944.5, "invalid state jobs"),
    ],
)
def test_loader_rejects_invalid_state_employment_values(
    monkeypatch, tmp_path, sheet, cell, bad_value, match
):
    def edit(workbook):
        workbook[sheet][cell] = bad_value

    _modified_workbook(monkeypatch, edit=edit)
    conn = _fresh_seeded_db(tmp_path)
    try:
        with pytest.raises(ValueError, match=match):
            ut.load(conn)
    finally:
        conn.close()
