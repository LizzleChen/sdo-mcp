"""Wyoming February 2025 edition, source reconciliation, and API coverage."""

import io
import zipfile
from xml.etree import ElementTree

import pytest

from sdo_mcp import server, store
from sdo_mcp.ingest import wy


def _body(name):
    return (wy.RAW_DIR / name).read_bytes()


def _changed_cell(cell: str, new_value: str) -> bytes:
    target = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(_body(wy.WORKBOOK_FILE))) as old, zipfile.ZipFile(target, "w") as new:
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


def test_state_history_and_forecasts():
    result = server.get_forecast("WY", "state", "Wyoming", "population")
    assert result["status"] == "ok"
    assert len(result["series"]) == 31
    assert result["series"][:5] == [
        {"year": year, "value": value, "datatype": "estimate" if year <= 2023 else "projection"}
        for year, value in zip(range(2020, 2025), (576851, 579548, 581629, 584057, 586980))
    ]
    assert result["series"][-1] == {"year": 2050, "value": 625230, "datatype": "projection"}
    source = result["source"]
    assert source["vintage"] == "February 2025"
    assert source["base_year"] == 2023
    assert source["horizon_year"] == 2050
    assert source["url"] == wy.SHEET_URL
    assert source["retrieved_at"] == next(e["retrieved_at"] for e in wy.fetch.read_manifest(wy.RAW_DIR)
                                          if e["file"] == wy.WORKBOOK_FILE)


@pytest.mark.parametrize("name,gid,year,value", [
    ("Albany", "56001", 2024, 38590),
    ("Big Horn", "56003", 2050, 12830),
    ("Johnson", "56019", 2023, 8759),
    ("Laramie", "56021", 2050, 111060),
    ("Lincoln", "56023", 2050, 24540),
    ("Weston", "56045", 2050, 6880),
])
def test_county_names_and_fips(name, gid, year, value):
    by_name = server.get_forecast("WY", "county", name, "population", year, year)
    by_fips = server.get_forecast("WY", "county", gid, "population", year, year)
    assert by_name == by_fips
    assert by_name["series"] == [{"year": year, "value": value,
                                  "datatype": "estimate" if year <= 2023 else "projection"}]


def test_published_municipal_product_and_grid():
    conn = store.connect()
    try:
        wy.verify(conn)
        assert conn.execute("SELECT COUNT(*) FROM observations WHERE state='WY'").fetchone()[0] == 744
    finally:
        conn.close()
    assert server.get_forecast("WY", "place", "Cheyenne", "population")["status"] == "not_loaded"
    assert server.get_forecast("WY", "county", "Albany", "households")["status"] == "coverage_unknown"
    assert server.get_forecast("WY", "state", "WY", "population", start_year=2051)["status"] == "empty_range"
    assert server.describe_source("WY")["review"]["status"] == "never_reviewed"


def test_all_workbook_values_match_independent_pdf():
    rows = wy.parse_workbook(_body(wy.WORKBOOK_FILE))
    pdf = wy.parse_pdf(_body(wy.PDF_FILE))
    assert len(rows) == len(pdf) == 744
    assert all(pdf[row["geo_id"], row["year"]] == row["value"] for row in rows)


@pytest.mark.parametrize("body", [b"<html>error</html>", b"[]", b"PKbroken"])
def test_soft_200_workbook_rejected(body):
    with pytest.raises(ValueError, match="readable XLSX"):
        wy.parse_workbook(body)


def test_soft_200_pdf_rejected():
    with pytest.raises(ValueError, match="expected population PDF"):
        wy.parse_pdf(b"<html>error</html>")


@pytest.mark.parametrize("cell,value,error", [
    ("F3", "2023", "years or estimate boundary"),
    ("F8", "38591", "do not reconcile"),
])
def test_changed_workbook_rejected(cell, value, error):
    with pytest.raises(ValueError, match=error):
        wy.parse_workbook(_changed_cell(cell, value))


def test_reuses_validated_originals(monkeypatch):
    manifest = (wy.RAW_DIR / "manifest.json").read_bytes()
    monkeypatch.setattr(wy.fetch, "get_bytes", lambda *_args: pytest.fail("unexpected network call"))
    wy.acquire()
    assert (wy.RAW_DIR / "manifest.json").read_bytes() == manifest
