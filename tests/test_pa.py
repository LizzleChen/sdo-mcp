"""Pennsylvania source validation, historical labels, and public tool behavior."""

import io
from datetime import datetime

import openpyxl
import pytest

from sdo_mcp import server, store
from sdo_mcp.ingest import pa


def _body():
    return (pa.RAW_DIR / pa.FILE).read_bytes()


def _changed_workbook(change):
    workbook = openpyxl.load_workbook(io.BytesIO(_body()))
    try:
        change(workbook)
        output = io.BytesIO()
        workbook.save(output)
        return output.getvalue()
    finally:
        workbook.close()


def test_state_estimates_projections_and_source_metadata():
    result = server.get_forecast("PA", "state", "Pennsylvania", "population")
    assert result["status"] == "ok"
    assert result["geo"] == {"level": "state", "id": "42", "name": "Pennsylvania"}
    assert result["scenario"] is None
    assert [p["year"] for p in result["series"]] == list(range(2020, 2051, 5))
    assert result["series"][0] == {"year": 2020, "value": 12994440, "datatype": "estimate"}
    assert result["series"][1] == {"year": 2025, "value": 13108642, "datatype": "projection"}
    assert result["series"][-1] == {"year": 2050, "value": 13195897, "datatype": "projection"}
    assert all(p["datatype"] == "projection" for p in result["series"][1:])
    source = result["source"]
    assert source["vintage"] == "2023"
    assert source["base_year"] == 2020  # Census Vintage 2022 is not the base year.
    assert source["horizon_year"] == 2050
    assert source["url"] == pa.URL
    assert source["retrieved_at"] == next(
        e["retrieved_at"] for e in pa.fetch.read_manifest(pa.RAW_DIR) if e["file"] == pa.FILE
    )
    assert "October 4, 2023" in source["citation"]
    assert "Census Vintage 2022" in source["method_notes"]


@pytest.mark.parametrize("name,gid,value", [
    ("Philadelphia", "42101", 1836216), ("Allegheny", "42003", 1226933),
    ("Centre", "42027", 177459), ("Forest", "42053", 5585), ("McKean", "42083", 37123),
])
def test_county_names_fips_and_report_fixtures(name, gid, value):
    result = server.get_forecast("PA", "county", name, "population", start_year=2050)
    assert result == server.get_forecast("PA", "county", gid, "population", start_year=2050)
    assert result["geo"]["id"] == gid
    assert result["series"] == [{"year": 2050, "value": value, "datatype": "projection"}]


@pytest.mark.parametrize("start,end", [(2010, 2019), (2021, 2024), (2026, 2029), (2051, 2060)])
def test_no_interpolated_or_extended_years(start, end):
    for level, geo in (("state", "PA"), ("county", "Philadelphia")):
        result = server.get_forecast("PA", level, geo, "population", start_year=start, end_year=end)
        assert result["status"] == "empty_range"
        assert result["available_start_year"] == 2020
        assert result["available_end_year"] == 2050
        assert "series" not in result


def test_complete_county_grid_and_published_state_totals():
    conn = store.connect()
    try:
        pa.verify(conn)
        counties = conn.execute(
            "SELECT geo_id, COUNT(*) FROM observations WHERE state='PA' AND geo_level='county' GROUP BY geo_id"
        ).fetchall()
        assert len(counties) == 67
        assert all(row[1] == 7 for row in counties)
        differences = conn.execute(
            "SELECT s.year, SUM(c.value)-s.value FROM observations s "
            "JOIN observations c ON c.state=s.state AND c.year=s.year AND c.geo_level='county' "
            "WHERE s.state='PA' AND s.geo_level='state' GROUP BY s.year ORDER BY s.year"
        ).fetchall()
        assert [tuple(row) for row in differences] == [(year, 0) for year in range(2020, 2051, 5)]
    finally:
        conn.close()


def test_unloaded_pdf_unknown_coverage_and_inventory():
    for level, geo in (("state", "PA"), ("county", "Philadelphia")):
        for variable in ("households", "employment"):
            assert server.get_forecast("PA", level, geo, variable)["status"] == "coverage_unknown"
    assert server.get_forecast("PA", "place", "Philadelphia", "population")["status"] == "coverage_unknown"
    assert server.get_components("PA", "Philadelphia")["status"] == "coverage_unknown"
    components = server.get_components("PA", "PA")
    assert components["status"] == "pdf_only"
    assert "five-year periods" in components["reason"]
    assert "series" not in components
    summary = server.list_states()["states"]["PA"]
    assert summary["variables"]["population"]["county"]["load_status"] == "loaded"
    assert summary["variables"]["components"]["state"]["load_status"] == "not_loaded"
    description = server.describe_source("PA")
    assert description["variables"] == summary["variables"]
    assert description["review"]["status"] == "never_reviewed"
    assert len(description["sources_loaded"]) == 1


@pytest.mark.parametrize("sheet,cell,value,error", [
    ("Source", "A2", "Base population: 2022", "base year"),
    ("Source", "A12", datetime(2024, 9, 5), "edition date"),
    ("Population Projections", "D3", "2020 Total (Proj.)", "header"),
    ("Population Projections", "G3", "2026 Total (Proj.)", "header"),
    ("Population Projections", "A5", 42000, "geography"),
    ("Population Projections", "B5", "Philadelphia County", "geography"),
    ("Population Projections", "C6", "Total Population", "duplicate"),
    ("Population Projections", "C6", "Ages 0 to 9", "geography/age"),
    ("Population Projections", "G5", -1, "population value"),
    ("Population Projections", "G5", 1.5, "population value"),
    ("Population Projections", "G5", "NaN", "population value"),
    ("Population Projections", "G5", None, "population value"),
    ("Population Projections", "G5", True, "population value"),
])
def test_parser_rejects_changed_semantics_and_invalid_values(sheet, cell, value, error):
    with pytest.raises(ValueError, match=error):
        pa.parse(_changed_workbook(lambda w: setattr(w[sheet][cell], "value", value)))


def test_parser_rejects_missing_geography():
    def remove_philadelphia(workbook):
        sheet = workbook["Population Projections"]
        for row in reversed(list(sheet.iter_rows())):
            if row[0].value == 42101:
                sheet.delete_rows(row[0].row)
    with pytest.raises(ValueError, match="incomplete"):
        pa.parse(_changed_workbook(remove_philadelphia))


@pytest.mark.parametrize("body", [b"<html>Service unavailable</html>", b"PKnot a workbook", b"[]"])
def test_parser_rejects_soft_200_errors(body):
    with pytest.raises(ValueError, match="readable population workbook"):
        pa.parse(body)


def test_acquire_reuses_originals_without_network(monkeypatch):
    before = (pa.RAW_DIR / "manifest.json").read_bytes()
    def fail_network(*args, **kwargs):
        raise AssertionError("saved edition must not be downloaded again")
    monkeypatch.setattr(pa.fetch, "get_bytes", fail_network)
    pa.acquire()
    assert (pa.RAW_DIR / "manifest.json").read_bytes() == before


@pytest.mark.parametrize("bad_reference", [False, True])
def test_acquire_does_not_save_invalid_downloads(tmp_path, monkeypatch, bad_reference):
    body = _body()
    raw = tmp_path / "pa"
    monkeypatch.setattr(pa, "RAW_DIR", raw)
    monkeypatch.setattr(pa.fetch, "get_bytes", lambda url: (
        body if bad_reference and url == pa.URL else b"<html>temporary error</html>"
    ))
    with pytest.raises(ValueError, match="readable"):
        pa.acquire()
    assert not raw.exists()
