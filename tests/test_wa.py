"""Washington's state and county products remain separate and round-trip."""

from sdo_mcp import server
import pytest


def _point(res, year):
    return next(p for p in res["series"] if p["year"] == year)


def test_state_uses_newer_single_series_not_gma_comparison():
    res = server.get_forecast("WA", "state", "Washington", "population")
    assert res["status"] == "ok"
    assert res["scenario"] is None
    assert _point(res, 2025) == {"year": 2025, "value": 8115100, "datatype": "estimate"}
    assert _point(res, 2050) == {"year": 2050, "value": 9719108, "datatype": "projection"}
    assert res["source"]["base_year"] == 2025
    assert "State Population" in res["source"]["product"]


def test_state_rejects_county_scenario_choice():
    res = server.get_forecast("WA", "state", "WA", "population", scenario="high")
    assert res["status"] == "error"
    assert "single series" in res["error"]


def test_king_county_defaults_to_gma_medium():
    res = server.get_forecast("WA", "county", "King", "population")
    assert res["status"] == "ok"
    assert res["scenario"] == "medium"
    assert res["geo"]["id"] == "53033"
    assert _point(res, 2020)["value"] == 2269675
    assert _point(res, 2025) == {"year": 2025, "value": 2377737, "datatype": "projection"}
    assert _point(res, 2050)["value"] == 2879176
    assert "Growth Management Act" in res["source"]["product"]


def test_gma_gap_is_not_filled():
    res = server.get_forecast("WA", "county", "King", "population")
    years = [p["year"] for p in res["series"]]
    assert years[:4] == [2020, 2021, 2022, 2025]
    assert 2023 not in years and 2024 not in years


def test_state_components_and_pdf_employment_are_explicit():
    components = server.get_components("WA", "WA")
    assert components["status"] == "ok"
    assert len(components["series"]) == 40
    assert _point(components, 2025) == dict(year=2025, datatype="estimate",
        births=83698, deaths=66612, net_migration=62314,
        period_start_year=2024, period_end_year=2025)
    assert _point(components, 2026)["datatype"] == "projection"
    assert _point(components, 2050)["deaths"] == 95583
    assert components["source"]["base_year"] == 2025
    jobs = server.get_forecast("WA", "state", "WA", "employment")
    assert jobs["status"] == "pdf_only"


def test_county_components_preserve_five_year_totals_and_boundary():
    result = server.get_components("WA", "King")
    assert result["status"] == "ok"
    assert result["scenario"] == "medium"
    assert [p["year"] for p in result["series"]] == list(range(1965, 2055, 5))
    assert _point(result, 2020)["datatype"] == "estimate"
    assert _point(result, 2025) == dict(year=2025, datatype="projection",
        births=113170, deaths=81098, net_migration=75990,
        period_start_year=2020, period_end_year=2025)
    assert _point(result, 2050)["net_migration"] == 76738
    assert result["source"]["base_year"] == 2020
    assert "five-year" in result["source"]["method_notes"].lower()
    assert server.get_components("WA", "King", 2026, 2029)["status"] == "empty_range"
    for scenario in ("low", "high"):
        rejected = server.get_components("WA", "King", scenario=scenario)
        assert rejected["status"] == "error"
        assert "only for the medium" in rejected["error"]


def test_all_counties_and_negative_migration(db_path):
    from sdo_mcp import store
    conn = store.connect(db_path)
    try:
        rows = conn.execute("SELECT geo_id, count(*) FROM observations WHERE source_id='wa-components-2022-gma' GROUP BY geo_id").fetchall()
        assert len(rows) == 39
        assert all(r[1] == 54 for r in rows)
    finally:
        conn.close()
    assert _point(server.get_components("WA", "Adams"), 2025)["net_migration"] == -385


def test_state_components_match_annual_population_changes():
    population = {p["year"]: p["value"] for p in server.get_forecast("WA", "state", "WA", "population")["series"]}
    for p in server.get_components("WA", "WA")["series"]:
        assert p["births"] - p["deaths"] + p["net_migration"] == population[p["year"]] - population[p["year"] - 1]


@pytest.mark.parametrize("cell,value", [("E9", "Birth Rate"), ("E28", None), ("J28", 0)])
def test_component_loader_rejects_changed_columns_missing_counts_and_bad_balance(monkeypatch, cell, value):
    import openpyxl
    from sdo_mcp.ingest import wa
    workbook = openpyxl.load_workbook(wa.RAW_DIR / wa.STATE_COMPONENT_FILE, data_only=True)
    workbook["Components of Change"][cell] = value
    monkeypatch.setattr(openpyxl, "load_workbook", lambda *a, **k: workbook)
    from sdo_mcp import store
    conn = store.connect()
    try:
        with pytest.raises(ValueError, match="WA state|WA components"):
            wa.load_components(conn, {})
    finally:
        conn.close()


def test_state_catalog_says_scenarios_are_county_only():
    wa = server.list_states()["states"]["WA"]
    assert wa["scenarios"] == ["low", "medium", "high"]
    assert wa["scenario_geo_levels"] == ["county"]
