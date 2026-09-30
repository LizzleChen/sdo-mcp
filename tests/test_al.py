"""CBER 2025 estimate boundary, source edition and displayed rounding."""

import io
import zipfile
from xml.etree import ElementTree

import pytest

from sdo_mcp import server, store
from sdo_mcp.ingest import al


def _body():
    return (al.RAW_DIR / al.WORKBOOK_FILE).read_bytes()


def _changed_cell(cell: str, new_value: str) -> bytes:
    target = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(_body())) as old, zipfile.ZipFile(target, "w") as new:
        for item in old.infolist():
            body = old.read(item.filename)
            if item.filename == "xl/worksheets/sheet1.xml":
                root = ElementTree.fromstring(body)
                ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
                node = root.find(f".//{ns}c[@r='{cell}']/{ns}v")
                assert node is not None
                node.text = new_value
                body = ElementTree.tostring(root, encoding="utf-8", xml_declaration=True)
            new.writestr(item, body)
    return target.getvalue()


def test_state_estimate_and_displayed_forecasts():
    result = server.get_forecast("AL", "state", "Alabama", "population")
    assert result["status"] == "ok"
    assert result["series"] == [
        {"year": year, "value": value, "datatype": "estimate" if year == 2025 else "projection"}
        for year, value in zip(al.YEARS, (5193088, 5365127, 5500129, 5629457, 5758418, 5890544))
    ]
    source = result["source"]
    assert source["base_year"] == 2025
    assert source["horizon_year"] == 2050
    assert "Fall 2026" in source["vintage"]
    assert source["url"] == al.PUBLIC_URL
    assert source["retrieved_at"] == next(e["retrieved_at"] for e in al.fetch.read_manifest(al.RAW_DIR)
                                          if e["file"] == al.WORKBOOK_FILE)
    assert "October 2024" in source["method_notes"]
    assert "September 24, 2026" in source["method_notes"]


@pytest.mark.parametrize("name,gid,year,value,datatype", [
    ("Baldwin", "01003", 2025, 267761, "estimate"),
    ("Baldwin", "01003", 2050, 436428, "projection"),
    ("Autauga", "01001", 2030, 64905, "projection"),
    ("Greene", "01063", 2050, 4115, "projection"),
    ("Wilcox", "01131", 2050, 5321, "projection"),
])
def test_counties_by_name_and_fips(name, gid, year, value, datatype):
    result = server.get_forecast("AL", "county", name, "population",
                                 start_year=year, end_year=year)
    assert result == server.get_forecast("AL", "county", gid, "population",
                                         start_year=year, end_year=year)
    assert result["series"] == [{"year": year, "value": value, "datatype": datatype}]


def test_grid_rounding_and_unknown_products():
    conn = store.connect()
    try:
        al.verify(conn)
        assert conn.execute("SELECT COUNT(*) FROM observations WHERE state='AL'").fetchone()[0] == 408
        state = conn.execute("SELECT value FROM observations WHERE state='AL' AND geo_level='state' "
                             "AND year=2030").fetchone()[0]
        counties = conn.execute("SELECT SUM(value) FROM observations WHERE state='AL' AND "
                                "geo_level='county' AND year=2030").fetchone()[0]
        assert state - counties == 2
    finally:
        conn.close()
    assert server.get_forecast("AL", "county", "Baldwin", "population", start_year=2026,
                               end_year=2029)["status"] == "empty_range"
    assert server.get_forecast("AL", "state", "AL", "population", start_year=2051)["status"] == "empty_range"
    assert server.get_forecast("AL", "place", "Mobile", "population")["status"] == "coverage_unknown"
    assert server.get_forecast("AL", "county", "Baldwin", "households")["status"] == "coverage_unknown"
    assert server.get_forecast("AL", "state", "AL", "population", scenario="high")["status"] == "error"
    assert server.describe_source("AL")["review"]["status"] == "never_reviewed"


@pytest.mark.parametrize("body", [b"<html>error</html>", b"[]", b"PKbroken"])
def test_soft_200_rejected(body):
    with pytest.raises(ValueError, match="readable XLSX"):
        al.parse_workbook(body)


@pytest.mark.parametrize("cell,value,error", [
    ("K3", "2029", "year grid"),
    ("K5", "-1", "invalid population"),
    ("K4", "5365226.5418064157", "reconcile"),
])
def test_changed_workbook_rejected(cell, value, error):
    with pytest.raises(ValueError, match=error):
        al.parse_workbook(_changed_cell(cell, value))


def test_reuses_validated_originals(monkeypatch):
    manifest = (al.RAW_DIR / "manifest.json").read_bytes()
    monkeypatch.setattr(al.fetch, "get_bytes", lambda *_args: pytest.fail("unexpected network call"))
    al.acquire()
    assert (al.RAW_DIR / "manifest.json").read_bytes() == manifest
