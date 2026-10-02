"""Oklahoma March 2023 totals, source layout exceptions and unknown estimate base."""
import io
from functools import lru_cache

import pytest
from pypdf import PdfReader, PdfWriter

from sdo_mcp import server, store
from sdo_mcp.ingest import ok


@lru_cache
def _body():
    return (ok.RAW_DIR / ok.FILE).read_bytes()


@lru_cache
def _pages():
    return tuple(page.extract_text() for page in PdfReader(io.BytesIO(_body())).pages)


def test_parser_exact_complete_grid_and_rendered_fixtures():
    rows = ok.parse(_body())
    assert len(rows) == 780
    assert {(r["geo_id"], r["year"]) for r in rows} == {(gid, year) for gid in ok._geographies().values() for year in ok.YEARS}
    assert all(row["datatype"] == "projection" and row["year"] >= 2025 for row in rows)
    values = {(r["geo_id"], r["year"]): r["value"] for r in rows}
    for gid, year, value in ok.FIXTURES:
        assert values[gid, year] == value


def test_source_unknown_base_and_past_projection_semantics():
    result = server.get_forecast("OK", "state", "Oklahoma", "population")
    assert result["status"] == "ok" and result["scenario"] is None
    assert result == server.get_forecast("OK", "state", "40", "population")
    assert [r["value"] for r in result["series"]] == list(ok.STATE_VALUES)
    assert all(r["datatype"] == "projection" for r in result["series"])
    assert result["source"]["base_year"] is None and result["source"]["vintage"] == "March 2023"
    assert result["source"]["horizon_year"] == 2070
    assert "aging" in result["source"]["method_notes"] or "age forward" in result["source"]["method_notes"]
    county = server.get_forecast("OK", "county", "Cimarron", "population")
    assert county == server.get_forecast("OK", "county", "40025", "population")
    assert county["series"][0] == dict(year=2025, value=2092, datatype="projection")
    assert county["series"][-1] == dict(year=2070, value=1356, datatype="projection")
    conn = store.connect()
    try:
        ok.verify(conn)
    finally:
        conn.close()


@pytest.mark.parametrize("start,end", [(2000, 2024), (2026, 2029), (2071, 2090)])
def test_no_old_ambiguous_cells_interpolation_or_extension(start, end):
    assert server.get_forecast("OK", "state", "OK", "population", start_year=start, end_year=end)["status"] == "empty_range"


def test_unknown_extra_products_invalid_scenario_and_ambiguous_county():
    for variable in ("households", "employment"):
        assert server.get_forecast("OK", "state", "OK", variable)["status"] == "coverage_unknown"
    assert server.get_components("OK", "OK")["status"] == "coverage_unknown"
    assert server.get_forecast("OK", "place", "Tulsa", "population")["status"] == "coverage_unknown"
    assert server.get_forecast("OK", "state", "OK", "population", scenario="medium")["status"] == "error"
    assert server.get_forecast("OK", "county", "Roger", "population")["status"] == "error"
    assert server.describe_source("OK")["review"]["status"] == "never_reviewed"


@pytest.mark.parametrize("token", ["-1", "1.5", "1,00", "NA", "*", "", "nan"])
def test_parser_rejects_suppressed_or_invalid_population(token):
    with pytest.raises(ValueError, match="integer"):
        ok._integer(token)


@pytest.mark.parametrize("change", [
    lambda text: text.replace("Population Projections", "Population Estimates"),
    lambda text: text.replace("2025 4,005,315", "2026 4,005,315"),
    lambda text: text.replace("2025 4,005,315", "2025 *"),
    lambda text: text.replace("Oklahoma Statewide", "Oklahoma County"),
    lambda text: text + "\n2025 4,005,315\n",
])
def test_parser_rejects_changed_header_grid_suppression_geography_duplicates(change):
    with pytest.raises(ValueError):
        ok._parse_table(change(_pages()[20]), "Oklahoma Statewide", 21)


def test_parser_handles_cimarron_and_requires_identical_physical_duplicates():
    assert ok._parse_table(_pages()[46], "Cimarron", 47)[2070] == 1356
    assert ok._parse_table(_pages()[76], "Greer", 77)[2070] == 5159
    assert ok._parse_table(_pages()[78], "Harmon", 79)[2070] == 1655
    changed = _pages()[76].rsplit("2070 5,159", 1)
    with pytest.raises(ValueError, match="duplicated"):
        ok._parse_table("2070 5,158".join(changed), "Greer", 77)


@pytest.mark.parametrize("body", [b"<html>error200</html>", b'{"error":"not a PDF"}', b"%PDF-broken"])
def test_parser_rejects_http200_non_pdf(body):
    with pytest.raises(ValueError, match="PDF"):
        ok.parse(body)


def test_parser_rejects_truncated_report_and_swapped_geography_page():
    writer = PdfWriter()
    writer.add_page(PdfReader(io.BytesIO(_body())).pages[0])
    output = io.BytesIO()
    writer.write(output)
    with pytest.raises(ValueError, match="page count"):
        ok.parse(output.getvalue())
    with pytest.raises(ValueError, match="page number"):
        ok._parse_table(_pages()[22], "Oklahoma Statewide", 21)


def test_snapshot_manifest_fingerprints():
    assert {entry["file"] for entry in ok.fetch.read_manifest(ok.RAW_DIR)} == set(ok.FILES)
