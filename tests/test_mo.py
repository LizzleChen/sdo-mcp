"""Missouri's original XLS, complete PDF cross-check and old-edition semantics."""

import copy
import pytest
import xlrd

from sdo_mcp import server, store
from sdo_mcp.ingest import mo


def _bodies():
    return {name: (mo.RAW_DIR / name).read_bytes() for name in mo.FILES}


def _grid():
    book = xlrd.open_workbook(file_contents=_bodies()[mo.FILE])
    try:
        sheet = book.sheet_by_index(0)
        return [sheet.row_values(i) for i in range(sheet.nrows)]
    finally:
        book.release_resources()


def test_original_grid_matches_independent_pdf_cells():
    rows = mo._validate(_bodies())
    assert len(rows) == 812
    assert {row["year"] for row in rows} == set(mo.YEARS)
    assert len({row["geo_id"] for row in rows}) == 116
    for gid, year, value in mo.FIXTURES:
        assert next(row["value"] for row in rows if (row["geo_id"], row["year"]) == (gid, year)) == value


def test_state_series_original_edition_and_estimate_input_exception():
    result = server.get_forecast("MO", "state", "Missouri", "population")
    assert result["status"] == "ok"
    assert result["series"] == [
        {"year": year, "value": value, "datatype": "estimate" if year == 2000 else "projection"}
        for year, value in zip(mo.YEARS, mo.STATE_TOTALS, strict=True)]
    source = result["source"]
    assert (source["vintage"], source["base_year"], source["horizon_year"]) == (mo.VINTAGE, 2007, 2030)
    assert source["url"] == mo.TABLE_URL
    assert source["retrieved_at"] == "2026-10-02"
    assert "old March 2008 forecast ending in 2030" in source["method_notes"]
    assert "No 2007 row is generated" in source["method_notes"]
    # A projection preceding the latest migration-calibration estimate year
    # stays a projection because the source explicitly describes it as one.
    assert result["series"][1]["datatype"] == "projection"


@pytest.mark.parametrize("name,gid,year,value", [
    ("St. Louis County", "29189", 2030, 956817),
    ("St. Louis city", "29510", 2030, 349004),
    ("Jackson", "29095", 2030, 714467),
    ("Worth", "29227", 2005, 2139),
    ("Worth", "29227", 2030, 1826),
    ("Adair", "29001", 2005, 24690),
])
def test_county_name_and_id(name, gid, year, value):
    result = server.get_forecast("MO", "county", name, "population", start_year=year, end_year=year)
    assert result == server.get_forecast("MO", "county", gid, "population", start_year=year, end_year=year)
    assert result["series"] == [{"year": year, "value": value, "datatype": "projection"}]


def test_complete_grid_and_expired_horizon_without_interpolation():
    conn = store.connect()
    try:
        mo.verify(conn)
        for year in mo.YEARS:
            difference = conn.execute("SELECT SUM(CASE WHEN geo_level='state' THEN -value ELSE value END) "
                                      "FROM observations WHERE state='MO' AND year=?", (year,)).fetchone()[0]
            assert difference == 0
    finally:
        conn.close()
    assert server.get_forecast("MO", "state", "MO", "population", start_year=2006, end_year=2007)["status"] == "empty_range"
    assert server.get_forecast("MO", "state", "MO", "population", start_year=2031)["status"] == "empty_range"
    assert server.get_forecast("MO", "state", "MO", "population", scenario="preferred")["status"] == "error"
    assert server.get_forecast("MO", "place", "St. Louis", "population")["status"] == "coverage_unknown"
    assert server.get_forecast("MO", "state", "MO", "households")["status"] == "coverage_unknown"
    assert server.get_forecast("MO", "state", "MO", "employment")["status"] == "coverage_unknown"
    assert server.get_components("MO", "MO")["status"] == "not_loaded"
    assert server.get_components("MO", "Worth")["status"] == "not_loaded"


def test_source_inventory_separates_deferred_components():
    result = server.describe_source("MO")
    assert result["review"]["status"] == "never_reviewed"
    assert result["variables"]["population"]["county"]["load_status"] == "loaded"
    assert result["variables"]["components"]["state"]["status"] == "available"
    assert result["variables"]["components"]["state"]["load_status"] == "not_loaded"
    assert server.list_states()["states"]["MO"]["data_loaded"] is True


@pytest.mark.parametrize("body", [b"<html>service unavailable</html>", b"[]", b"broken xls"])
def test_soft_200_not_a_workbook(body):
    with pytest.raises(ValueError, match="readable original XLS"):
        mo.parse(body)


@pytest.mark.parametrize("body", [b"<html>error</html>", b"%PDF-broken", b"{}"])
def test_soft_200_not_a_pdf(body):
    with pytest.raises(ValueError, match="readable population PDF"):
        mo._pdf_text(body, 3)


@pytest.mark.parametrize("row,column,value,error", [
    (0, 0, "Wrong product", "headers"),
    (2, 1, 2001, "years"),
    (3, 0, "Not a county", "unknown geography"),
    (4, 0, "Adair", "duplicate geography"),
    (3, 1, -1, "invalid population"),
    (3, 1, None, "invalid population"),
    (3, 1, "Suppressed", "invalid population"),
    (3, 1, True, "invalid population"),
    (3, 1, float("nan"), "invalid population"),
    (3, 1, 24977.5, "invalid population"),
    (119, 7, 6746763, "statewide totals changed"),
    (3, 7, 24914, "county/state totals disagree"),
])
def test_changed_semantics_or_values_rejected(row, column, value, error):
    grid = _grid()
    grid[row][column] = value
    with pytest.raises(ValueError, match=error):
        mo.parse_grid(grid)


def test_missing_county_row_rejected():
    grid = _grid()
    del grid[3]
    with pytest.raises(ValueError, match="layout"):
        mo.parse_grid(grid)


def test_pdf_duplicate_missing_and_noninteger_cells_rejected():
    texts = mo._pdf_text(_bodies()["total_population_preferred_march2008.pdf"], 3)
    line = next(line for line in texts[0].splitlines() if line.startswith("Adair"))
    for changed, error in [(texts[0] + "\n" + line, "duplicate"),
                           (texts[0].replace(line, ""), "incomplete"),
                           (texts[0].replace("24,977", "Suppressed", 1), "invalid PDF")]:
        with pytest.raises(ValueError, match=error):
            mo.parse_companion_texts([changed, *texts[1:]])


def test_pdf_xls_disagreement_rejected(monkeypatch):
    bodies = _bodies()
    rows = copy.deepcopy(mo.parse(bodies[mo.FILE]))
    rows[0]["value"] += 1
    monkeypatch.setattr(mo, "parse", lambda body: rows)
    with pytest.raises(ValueError, match="XLS and companion PDF disagree"):
        mo._validate(bodies)


@pytest.mark.parametrize("name", [name for name in mo.FILES if name.endswith(".html")])
def test_error_pages_not_saved_as_provenance(name):
    with pytest.raises(ValueError, match="invalid publisher evidence"):
        mo._validate_page(name, b"<html><title>Service Unavailable</title></html>")


def test_acquire_reuses_originals_without_network(monkeypatch):
    before = (mo.RAW_DIR / "manifest.json").read_bytes()
    monkeypatch.setattr(mo.fetch, "get_bytes", lambda *_args: pytest.fail("unexpected network"))
    mo.acquire()
    assert before == (mo.RAW_DIR / "manifest.json").read_bytes()
