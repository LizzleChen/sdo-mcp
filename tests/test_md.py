"""Maryland product boundaries, independent cities, provenance and validation."""

import io

import openpyxl
import pytest

from sdo_mcp import server, store
from sdo_mcp.ingest import md


def _body(variable):
    return (md.RAW_DIR / md.PRODUCTS[variable]["file"]).read_bytes()


def _changed(variable, change):
    workbook = openpyxl.load_workbook(io.BytesIO(_body(variable)))
    try:
        change(workbook.active)
        output = io.BytesIO()
        workbook.save(output)
        return output.getvalue()
    finally:
        workbook.close()


@pytest.mark.parametrize("variable,values,vintage", [
    ("population", [6177224, 6300610, 6492470, 6687460, 6863910, 7029400, 7191870, 7341680], "November 2025"),
    ("households", [2321208, 2411360, 2493200, 2579390, 2655590, 2721500, 2786290, 2865380], "November 2025"),
    ("employment", [3536398, 3684000, 3857800, 3947400, 4036500, 4108000, 4179100], "October 2022 (preliminary)"),
])
def test_state_series_and_product_metadata(variable, values, vintage):
    result = server.get_forecast("MD", "state", "Maryland", variable)
    assert result["status"] == "ok"
    assert result["geo"] == {"level": "state", "id": "24", "name": "Maryland"}
    assert result["scenario"] is None
    assert result["series"] == [
        {"year": year, "value": value, "datatype": "estimate" if year == 2020 else "projection"}
        for year, value in zip(range(2020, 2060, 5), values)
    ]
    source = result["source"]
    spec = md.PRODUCTS[variable]
    assert source["base_year"] == 2020
    assert source["vintage"] == vintage
    assert source["horizon_year"] == spec["horizon"]
    entry = next(e for e in md.fetch.read_manifest(md.RAW_DIR) if e["file"] == spec["file"])
    assert source["url"] == entry["source"]
    assert source["retrieved_at"] == entry["retrieved_at"]
    assert "Maryland Department of Planning" in source["citation"]
    if variable == "employment":
        assert "Preliminary" in source["method_notes"]
        assert "BEA" in source["method_notes"]
    else:
        assert "October 2025" in source["method_notes"]
        assert "Census" in source["method_notes"]


@pytest.mark.parametrize("variable,city,county", [
    ("population", 584130, 919450),
    ("households", 262030, 369830),
    ("employment", 454800, 564900),
])
def test_baltimore_city_is_distinct_from_county(variable, city, county):
    for name, gid, value in (("Baltimore City", "24510", city), ("Baltimore County", "24005", county)):
        result = server.get_forecast("MD", "county", name, variable, start_year=2050, end_year=2050)
        assert result["status"] == "ok"
        assert result["geo"]["id"] == gid
        assert result["series"] == [{"year": 2050, "value": value, "datatype": "projection"}]
        assert result == server.get_forecast("MD", "county", gid, variable, start_year=2050, end_year=2050)
        assert result == server.get_forecast("MD", "county", gid[2:], variable, start_year=2050, end_year=2050)


def test_complete_grids_and_inventory():
    conn = store.connect()
    try:
        md.verify(conn)
        assert conn.execute("SELECT COUNT(*) FROM observations WHERE state='MD'").fetchone()[0] == 575
        assert {row[0] for row in conn.execute(
            "SELECT DISTINCT geo_level FROM observations WHERE state='MD'"
        )} == {"state", "county"}
        for variable in md.PRODUCTS:
            rows = conn.execute(
                "SELECT geo_id, COUNT(*) FROM observations WHERE state='MD' AND variable=? "
                "AND geo_level='county' GROUP BY geo_id", (variable,),
            ).fetchall()
            assert len(rows) == 24
            assert {r[1] for r in rows} == {7 if variable == "employment" else 8}
    finally:
        conn.close()
    summary = server.list_states()["states"]["MD"]
    for variable in md.PRODUCTS:
        for level in ("state", "county"):
            assert summary["variables"][variable][level]["load_status"] == "loaded"
    description = server.describe_source("MD")
    assert description["variables"] == summary["variables"]
    assert description["review"]["status"] == "never_reviewed"


@pytest.mark.parametrize("variable", md.PRODUCTS)
@pytest.mark.parametrize("start,end", [(2010, 2019), (2021, 2024), (2026, 2029), (2056, 2060)])
def test_no_invented_years(variable, start, end):
    result = server.get_forecast("MD", "county", "Montgomery", variable, start_year=start, end_year=end)
    assert result["status"] == "empty_range"
    assert result["available_start_year"] == 2020
    assert result["available_end_year"] == md.PRODUCTS[variable]["horizon"]
    assert "series" not in result


def test_separate_job_horizon_and_unverified_products():
    assert server.get_forecast("MD", "state", "MD", "employment", start_year=2055)["status"] == "empty_range"
    for variable in md.PRODUCTS:
        result = server.get_forecast("MD", "place", "Baltimore", variable)
        assert result["status"] == "coverage_unknown"
        assert "series" not in result
        assert server.get_forecast("MD", "county", "BALTIMORE REGION", variable)["status"] == "error"
        assert server.get_forecast("MD", "state", "MD", variable, scenario="high")["status"] == "error"
    assert server.get_components("MD", "Montgomery")["status"] == "coverage_unknown"


@pytest.mark.parametrize("variable", md.PRODUCTS)
@pytest.mark.parametrize("body", [b"<html>Service unavailable</html>", b"PKbroken", b"[]"])
def test_rejects_soft_200(variable, body):
    with pytest.raises(ValueError, match="readable"):
        md.parse_workbook(body, variable)


@pytest.mark.parametrize("variable,cell,value,error", [
    ("population", "A1", "Household population", "title or edition"),
    ("households", "A2", "(October 2025)", "title or edition"),
    ("employment", "C2", "(Revisions October 2025)", "title or edition"),
    ("population", "E3", "2026", "year header"),
    ("employment", "I4", 2024, "year header"),
    ("population", "A41", "All points are estimates", "footnote"),
    ("employment", "B45", "Projections from 2020", "footnote"),
    ("population", "A7", "Unknown County", "unknown"),
    ("employment", "B14", "Baltimore", "duplicate"),
    ("households", "A12", "Baltimore County", "duplicate"),
    ("population", "E4", 6300611, "county sum"),
    ("population", "L7", 1, "extra"),
])
def test_rejects_changed_semantics(variable, cell, value, error):
    body = _changed(variable, lambda s: setattr(s[cell], "value", value))
    with pytest.raises(ValueError, match=error):
        md.parse_workbook(body, variable)


@pytest.mark.parametrize("variable,cell", [("population", "E7"), ("households", "D7"), ("employment", "I9")])
@pytest.mark.parametrize("value", [None, True, -1, 1.5, "NaN", "#VALUE!"])
def test_rejects_invalid_numbers(variable, cell, value):
    body = _changed(variable, lambda s: setattr(s[cell], "value", value))
    with pytest.raises(ValueError, match="invalid"):
        md.parse_workbook(body, variable)


@pytest.mark.parametrize("variable,row", [("population", 7), ("households", 7), ("employment", 9)])
def test_rejects_missing_geography(variable, row):
    def clear(sheet):
        for cell in sheet[row]:
            cell.value = None
    with pytest.raises(ValueError, match="incomplete"):
        md.parse_workbook(_changed(variable, clear), variable)


def test_reuses_originals_without_network(monkeypatch):
    before = (md.RAW_DIR / "manifest.json").read_bytes()
    def fail_network(*args, **kwargs):
        raise AssertionError("saved edition must not be downloaded again")
    monkeypatch.setattr(md.fetch, "get_bytes", fail_network)
    md.acquire()
    assert (md.RAW_DIR / "manifest.json").read_bytes() == before
