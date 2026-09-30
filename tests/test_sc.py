"""RFA Vintage 2023 totals and cross-workbook validation."""

import io

import openpyxl
import pytest

from sdo_mcp import server, store
from sdo_mcp.ingest import sc


def _bodies():
    return {name: (sc.RAW_DIR / name).read_bytes() for name in sc.FILES}


def _changed(cell: str, value) -> bytes:
    book = openpyxl.load_workbook(io.BytesIO(_bodies()["population_components_v2023.xlsx"]))
    try:
        book.worksheets[0][cell] = value
        output = io.BytesIO()
        book.save(output)
        return output.getvalue()
    finally:
        book.close()


def test_state_series_and_source():
    result = server.get_forecast("SC", "state", "South Carolina", "population")
    assert result["status"] == "ok"
    assert len(result["series"]) == 21
    assert result["series"][0] == {"year": 2023, "value": 5373555, "datatype": "estimate"}
    assert result["series"][1] == {"year": 2024, "value": 5445291, "datatype": "projection"}
    assert result["series"][-1] == {"year": 2043, "value": 6870048, "datatype": "projection"}
    source = result["source"]
    assert source["vintage"] == "Vintage 2023"
    assert source["base_year"] == 2023
    assert source["horizon_year"] == 2043
    assert source["url"] == sc.TOTALS_URL
    assert source["retrieved_at"] == next(e["retrieved_at"] for e in sc.fetch.read_manifest(sc.RAW_DIR)
                                          if e["file"] == "population_components_v2023.xlsx")
    assert "2026-08 URL directory" in source["method_notes"]


@pytest.mark.parametrize("name,gid,year,value", [
    ("Abbeville", "45001", 2043, 23969),
    ("Allendale", "45005", 2043, 3791),
    ("Charleston", "45019", 2024, 428463),
    ("Richland", "45079", 2043, 463442),
    ("York", "45091", 2043, 391896),
])
def test_counties_by_name_and_fips(name, gid, year, value):
    result = server.get_forecast("SC", "county", name, "population",
                                 start_year=year, end_year=year)
    assert result == server.get_forecast("SC", "county", gid, "population",
                                         start_year=year, end_year=year)
    assert result["series"] == [{"year": year, "value": value, "datatype": "projection"}]


def test_complete_annual_grid_and_product_gaps():
    conn = store.connect()
    try:
        sc.verify(conn)
        assert conn.execute("SELECT COUNT(*) FROM observations WHERE state='SC'").fetchone()[0] == 987
    finally:
        conn.close()
    assert server.get_forecast("SC", "county", "York", "population", start_year=2044)["status"] == "empty_range"
    assert server.get_forecast("SC", "place", "Charleston", "population")["status"] == "coverage_unknown"
    assert server.get_components("SC", "York")["status"] == "coverage_unknown"
    assert server.get_forecast("SC", "state", "SC", "population", scenario="high")["status"] == "error"
    assert server.describe_source("SC")["review"]["status"] == "never_reviewed"


def test_all_displayed_totals_match_companion_age_workbook():
    rows = sc._validate_all(_bodies())
    assert len(rows) == 987


@pytest.mark.parametrize("body", [b"<html>error</html>", b"[]", b"PKbroken"])
def test_soft_200_rejected(body):
    with pytest.raises(ValueError, match="readable XLSX"):
        sc.parse_totals(body)


@pytest.mark.parametrize("cell,value,error", [
    ("C11", "2024 - 2025", "period"),
    ("B14", 99999, "FIPS"),
    ("H14", -1, "invalid population"),
])
def test_changed_semantics_rejected(cell, value, error):
    with pytest.raises(ValueError, match=error):
        sc.parse_totals(_changed(cell, value))


def test_changed_total_is_caught_by_companion():
    bodies = _bodies()
    bodies["population_components_v2023.xlsx"] = _changed("H13", 5445292)
    with pytest.raises(ValueError, match="workbooks disagree"):
        sc._validate_all(bodies)


def test_reuses_originals_without_network(monkeypatch):
    before = (sc.RAW_DIR / "manifest.json").read_bytes()
    monkeypatch.setattr(sc.fetch, "get_bytes", lambda *_args: pytest.fail("unexpected network call"))
    sc.acquire()
    assert (sc.RAW_DIR / "manifest.json").read_bytes() == before
