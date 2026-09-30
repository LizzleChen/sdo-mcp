"""Nevada PDF extraction, source semantics and public MCP behavior."""

import io

import pytest
from pypdf import PdfReader

from sdo_mcp import server, store
from sdo_mcp.ingest import nv


def _body():
    return (nv.RAW_DIR / nv.PDF_FILE).read_bytes()


def _pages():
    return [page.extract_text() for page in PdfReader(io.BytesIO(_body())).pages]


def test_published_population_boundary_and_source():
    result = server.get_forecast("NV", "state", "Nevada", "population")
    assert result["status"] == "ok"
    assert result["series"][0] == {"year": 2024, "value": 3282911, "datatype": "estimate"}
    assert result["series"][1] == {"year": 2025, "value": 3326902, "datatype": "projection"}
    assert result["series"][-1] == {"year": 2044, "value": 3699248, "datatype": "projection"}
    assert [point["year"] for point in result["series"]] == list(nv.YEARS)
    assert all(point["datatype"] == "projection" for point in result["series"][1:])
    assert result["source"]["vintage"] == "October 2025"
    assert result["source"]["base_year"] == 2024
    assert result["source"]["horizon_year"] == 2044
    assert result["source"]["retrieved_at"] == "2026-09-30"
    assert result["scenario"] is None
    assert "March 2026" in result["source"]["method_notes"]


def test_carson_city_is_county_equivalent_and_small_county_is_preserved():
    result = server.get_forecast("NV", "county", "Carson City", "population")
    assert result == server.get_forecast("NV", "county", "32510", "population")
    assert result["geo"] == {"level": "county", "id": "32510", "name": "Carson City"}
    assert result["series"][-1]["value"] == 64275
    tiny = server.get_forecast("NV", "county", "Esmeralda", "population")
    assert tiny["series"][1]["value"] == 1081
    assert tiny["series"][-1]["value"] == 1205
    assert server.get_forecast("NV", "county", "Clark", "population")["series"][-1]["value"] == 2726185


def test_complete_grid_and_rounding_differences_preserved():
    conn = store.connect()
    try:
        nv.verify(conn)
        differences = conn.execute(
            "SELECT s.year,SUM(c.value)-s.value FROM observations s JOIN observations c "
            "ON c.state=s.state AND c.year=s.year AND c.geo_level='county' "
            "WHERE s.state='NV' AND s.geo_level='state' GROUP BY s.year ORDER BY s.year"
        ).fetchall()
        assert any(row[1] != 0 for row in differences)
        assert max(abs(row[1]) for row in differences) <= 3
    finally:
        conn.close()


def test_unverified_products_and_inventory():
    for level, geo in (("state", "NV"), ("county", "Clark")):
        for variable in ("households", "employment"):
            assert server.get_forecast("NV", level, geo, variable)["status"] == "coverage_unknown"
        assert server.get_components("NV", geo)["status"] == "coverage_unknown"
    assert server.get_forecast("NV", "place", "Las Vegas", "population")["status"] == "coverage_unknown"
    assert server.get_forecast("NV", "state", "NV", "population", scenario="high")["status"] == "error"
    summary = server.list_states()["states"]["NV"]
    assert summary["variables"]["population"]["county"]["load_status"] == "loaded"
    description = server.describe_source("NV")
    assert description["variables"] == summary["variables"]
    assert len(description["sources_loaded"]) == 1


@pytest.mark.parametrize("start,end", [(2020, 2023), (2045, 2050)])
def test_no_history_or_extended_horizon_generated(start, end):
    result = server.get_forecast("NV", "state", "NV", "population", start_year=start, end_year=end)
    assert result["status"] == "empty_range"
    assert result["available_start_year"] == 2024
    assert result["available_end_year"] == 2044
    assert "series" not in result


@pytest.mark.parametrize("page,old,new,error", [
    (0, "October 1, 2025", "October 1, 2026", "edition"),
    (1, "July 1, 2024", "July 1, 2025", "boundary"),
    (2, "2024† 2025 2026", "2024† 2026 2027", "year header"),
    (2, "Carson City 60,266", "Churchill 60,266", "geography"),
    (2, "Esmeralda 1,086", "Esmeralda -1", "population row"),
    (2, "Esmeralda 1,086", "Esmeralda NaN", "population row"),
    (2, "Esmeralda 1,086", "Esmeralda 1,08", "population row"),
    (2, "Carson City 60,266", "Carson City 60,267", "disagree"),
    (3, "State Total* 3,615,215", "State Total* 3,615,214", "disagree"),
    (4, "2025 60,829", "2026 60,829", "year row"),
])
def test_parser_rejects_changed_tables(page, old, new, error):
    pages = _pages()
    assert old in pages[page]
    pages[page] = pages[page].replace(old, new, 1)
    with pytest.raises(ValueError, match=error):
        nv.parse_pages(pages)


def test_parser_rejects_missing_rows_and_wrong_page_count():
    pages = _pages()
    pages[2] = "\n".join(line for line in pages[2].splitlines() if not line.startswith("Esmeralda"))
    with pytest.raises(ValueError, match="geography"):
        nv.parse_pages(pages)
    with pytest.raises(ValueError, match="page count"):
        nv.parse_pages(_pages()[:-1])


@pytest.mark.parametrize("page", [2, 3])
def test_parser_rejects_empty_summary_pages(page):
    pages = _pages()
    pages[page] = ""
    with pytest.raises(ValueError, match="summary geography/year grid"):
        nv.parse_pages(pages)


@pytest.mark.parametrize("body", [b"<html>Service unavailable</html>", b"%PDF broken", b"{}"])
def test_parser_rejects_soft_200_errors(body):
    with pytest.raises(ValueError, match="readable population PDF"):
        nv.parse_pdf(body)


def test_saved_acquisition_needs_no_network(monkeypatch):
    before = (nv.RAW_DIR / "manifest.json").read_bytes()
    def fail(*args, **kwargs):
        raise AssertionError("saved edition must not be downloaded again")
    monkeypatch.setattr(nv.fetch, "get_bytes", fail)
    nv.acquire()
    assert (nv.RAW_DIR / "manifest.json").read_bytes() == before


def test_invalid_download_is_not_archived(tmp_path, monkeypatch):
    raw = tmp_path / "nv"
    monkeypatch.setattr(nv, "RAW_DIR", raw)
    monkeypatch.setattr(nv.fetch, "get_bytes", lambda *args, **kwargs: b"<html>error</html>")
    with pytest.raises(ValueError):
        nv.acquire()
    assert not raw.exists()
