"""Michigan source integrity, forecast semantics and public tool behavior."""

import io

import openpyxl
import pytest

from sdo_mcp import server, store
from sdo_mcp.ingest import mi


def _body():
    return (mi.RAW_DIR / mi.FILE).read_bytes()


def _changed_workbook(change):
    workbook = openpyxl.load_workbook(io.BytesIO(_body()))
    try:
        change(workbook.active)
        output = io.BytesIO()
        workbook.save(output)
        return output.getvalue()
    finally:
        workbook.close()


def test_state_scenario_base_year_and_projection_only_series():
    result = server.get_forecast("MI", "state", "Michigan", "population")
    assert result["status"] == "ok"
    assert result["geo"] == {"level": "state", "id": "26", "name": "Michigan"}
    assert result["scenario"] == "net_positive_migration"
    assert [p["year"] for p in result["series"]] == list(range(2025, 2051, 5))
    assert all(p["datatype"] == "projection" for p in result["series"])
    assert result["series"][0]["value"] == 10112318
    assert result["series"][-1]["value"] == 9905991.62
    assert result["source"]["vintage"] == "2024"
    assert result["source"]["base_year"] == 2022
    assert result["source"]["horizon_year"] == 2050
    assert result["source"]["retrieved_at"] == next(
        e["retrieved_at"] for e in mi.fetch.read_manifest(mi.RAW_DIR) if e["file"] == mi.FILE
    )
    assert "2023" in result["source"]["method_notes"]
    unloaded = server.get_forecast("MI", "state", "MI", "population", scenario="zero_migration")
    assert unloaded["status"] == "not_loaded"
    assert unloaded["scenario"] == "zero_migration"
    assert "series" not in unloaded


def test_county_lookup_precision_and_unknown_base():
    wayne = server.get_forecast("MI", "county", "Wayne", "population")
    assert wayne == server.get_forecast("MI", "county", "26163", "population")
    assert wayne["scenario"] is None
    assert wayne["source"]["product"] == "Michigan County Population Projections through 2050"
    assert wayne["source"]["base_year"] is None
    assert "not explicitly identify" in wayne["source"]["method_notes"]
    assert wayne["series"][-1] == {"year": 2050, "value": 1565187.79, "datatype": "projection"}
    for name, gid, value in (("St. Clair", "26147", 144502.45),
                             ("St. Joseph", "26149", 59891.7), ("Keweenaw", "26083", 1562.25)):
        result = server.get_forecast("MI", "county", name, "population")
        assert result["geo"]["id"] == gid
        assert result["series"][-1]["value"] == value
    assert server.get_forecast("MI", "county", "Wayne", "population",
                               scenario="zero_migration")["status"] == "error"


@pytest.mark.parametrize("start,end", [(2022, 2024), (2026, 2029), (2051, 2060)])
def test_no_generated_estimates_intermediate_years_or_extended_horizon(start, end):
    for level, geo in (("state", "MI"), ("county", "Kent")):
        result = server.get_forecast("MI", level, geo, "population", start_year=start, end_year=end)
        assert result["status"] == "empty_range"
        assert result["available_start_year"] == 2025
        assert result["available_end_year"] == 2050
        assert "series" not in result


def test_complete_grid_and_published_values_preserved():
    conn = store.connect()
    try:
        mi.verify(conn)
        counties = conn.execute(
            "SELECT geo_id, COUNT(*) FROM observations WHERE state='MI' AND geo_level='county' GROUP BY geo_id"
        ).fetchall()
        assert len(counties) == 83
        assert all(r[1] == 6 for r in counties)
        differences = conn.execute(
            "SELECT s.year, SUM(c.value)-s.value FROM observations s "
            "JOIN observations c ON c.state=s.state AND c.year=s.year AND c.geo_level='county' "
            "WHERE s.state='MI' AND s.geo_level='state' GROUP BY s.year ORDER BY s.year"
        ).fetchall()
        assert [r[1] for r in differences] == pytest.approx([-.01, 0, 0, .02, -.02, -.03], abs=1e-7)
        assert {r[0] for r in conn.execute("SELECT DISTINCT geo_level FROM observations WHERE state='MI'")} == {"state", "county"}
    finally:
        conn.close()


def test_unverified_products_remain_unknown_and_inventory_matches():
    for level, geo in (("state", "MI"), ("county", "Wayne")):
        for variable in ("households", "employment"):
            assert server.get_forecast("MI", level, geo, variable)["status"] == "coverage_unknown"
        assert server.get_components("MI", geo)["status"] == "coverage_unknown"
    assert server.get_forecast("MI", "place", "Detroit", "population")["status"] == "coverage_unknown"
    assert server.get_forecast("MI", "msa", "Detroit", "population")["status"] == "coverage_unknown"
    summary = server.list_states()["states"]["MI"]
    assert summary["variables"]["population"]["county"]["load_status"] == "loaded"
    assert summary["scenario_geo_levels"] == ["state"]
    description = server.describe_source("MI")
    assert description["variables"] == summary["variables"]
    assert description["review"]["status"] == "never_reviewed"
    assert len(description["sources_loaded"]) == 2


@pytest.mark.parametrize("cell,value,error", [
    ("I1", "households", "header"),
    ("A2", 27, "codes"),
    ("B2", 4, "geography"),
    ("C8", 2, "geography"),
    ("D8", "Invented County", "geography"),
    ("E8", 2026, "geography/year"),
    ("E8", 2030, "duplicate"),
    ("H8", 1, "codes"),
    ("I8", -1, "population value"),
    ("I8", "NaN", "population value"),
    ("I8", None, "population value"),
    ("I8", True, "population value"),
])
def test_parser_rejects_changed_semantics_and_invalid_values(cell, value, error):
    with pytest.raises(ValueError, match=error):
        mi.parse(_changed_workbook(lambda sheet: setattr(sheet[cell], "value", value)))


def test_parser_rejects_missing_county_and_unknown_region():
    with pytest.raises(ValueError, match="incomplete"):
        mi.parse(_changed_workbook(lambda sheet: sheet.delete_rows(8, 6)))
    # Prosperity-region data cannot accidentally enter the county namespace.
    with pytest.raises(ValueError, match="geography"):
        mi.parse(_changed_workbook(lambda sheet: setattr(sheet["B506"], "value", 4)))


@pytest.mark.parametrize("body", [b"<html>Service unavailable</html>", b"PKnot a workbook", b"[]"])
def test_parser_rejects_soft_200_errors(body):
    with pytest.raises(ValueError, match="readable population workbook"):
        mi.parse(body)


def test_acquire_reuses_validated_originals_without_network(monkeypatch):
    before = (mi.RAW_DIR / "manifest.json").read_bytes()
    def fail_network(*args, **kwargs):
        raise AssertionError("saved edition must not be downloaded again")
    monkeypatch.setattr(mi.fetch, "get_bytes", fail_network)
    monkeypatch.setattr(mi, "_get_reference", fail_network)
    mi.acquire()
    assert (mi.RAW_DIR / "manifest.json").read_bytes() == before


def test_acquire_does_not_archive_invalid_workbook(tmp_path, monkeypatch):
    raw = tmp_path / "mi"
    monkeypatch.setattr(mi, "RAW_DIR", raw)
    monkeypatch.setattr(mi.fetch, "get_bytes", lambda url: b"<html>temporary error</html>")
    with pytest.raises(ValueError, match="readable population workbook"):
        mi.acquire()
    assert not raw.exists()
