"""Maine April 2025 grid, fractional source precision, and API metadata."""

import io
import zipfile
from xml.etree import ElementTree

import pytest

from sdo_mcp import server, store
from sdo_mcp.ingest import me


def _body(name):
    return (me.RAW_DIR / name).read_bytes()


def _changed_numeric(sheet, cell, value):
    target = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(_body(me.WORKBOOK_FILE))) as old, zipfile.ZipFile(target, "w") as new:
        for item in old.infolist():
            body = old.read(item.filename)
            if item.filename == f"xl/worksheets/sheet{sheet}.xml":
                root = ElementTree.fromstring(body)
                ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
                node = root.find(f".//{ns}c[@r='{cell}']/{ns}v")
                assert node is not None
                node.text = str(value)
                body = ElementTree.tostring(root, encoding="utf-8", xml_declaration=True)
            new.writestr(item, body)
    return target.getvalue()


def test_state_grid_boundary_and_precision():
    result = server.get_forecast("ME", "state", "Maine", "population")
    assert result["status"] == "ok"
    assert [r["year"] for r in result["series"]] == list(me.YEARS)
    assert result["series"][0] == {"year": 2022, "value": 1389338, "datatype": "estimate"}
    assert result["series"][1] == {"year": 2027, "value": 1419888.2879359922, "datatype": "projection"}
    assert result["series"][-1] == {"year": 2042, "value": 1424856.838353645, "datatype": "projection"}
    source = result["source"]
    assert (source["vintage"], source["base_year"], source["horizon_year"]) == ("April 2025", 2022, 2042)
    assert source["url"] == me.WORKBOOK_URL
    assert source["retrieved_at"] == next(e["retrieved_at"] for e in me.fetch.read_manifest(me.RAW_DIR)
                                          if e["file"] == me.WORKBOOK_FILE)
    assert "beyond 2032" in source["method_notes"]


@pytest.mark.parametrize("name,gid,year,value", [
    ("Androscoggin", "23001", 2022, 113225),
    ("Cumberland", "23005", 2032, 322972.8624317943),
    ("Piscataquis", "23021", 2042, 16667.90336057443),
    ("Sagadahoc", "23023", 2027, 38858.98012740696),
    ("York", "23031", 2032, 232135.78662340573),
])
def test_county_names_and_fips(name, gid, year, value):
    by_name = server.get_forecast("ME", "county", name, "population", year, year)
    by_fips = server.get_forecast("ME", "county", gid, "population", year, year)
    assert by_name == by_fips
    assert by_name["series"] == [{"year": year, "value": value,
                                  "datatype": "estimate" if year == 2022 else "projection"}]


def test_publication_and_loading_metadata():
    assert server.get_forecast("ME", "place", "Portland", "population")["status"] == "not_loaded"
    for variable in ("households", "employment"):
        assert server.get_forecast("ME", "county", "Cumberland", variable)["status"] == "coverage_unknown"
    components = server.get_components("ME", "Maine")
    assert components["status"] == "coverage_unknown"
    assert components["geo_level"] == "state"
    description = server.describe_source("ME")
    assert description["review"]["status"] == "never_reviewed"
    assert "Consensus Economic Forecasting Commission" in description["employment_note"]
    assert any("fractional" in caveat for caveat in description["caveats"])
    for year in (2023, 2025, 2028, 2043):
        assert server.get_forecast("ME", "state", "Maine", "population", year, year)["status"] == "empty_range"


def test_complete_grid_and_independently_published_pdf():
    conn = store.connect()
    try:
        me.verify(conn)
    finally:
        conn.close()
    rows = me.parse_workbook(_body(me.WORKBOOK_FILE))
    pdf = me.parse_pdf(_body(me.PDF_FILE))
    assert len(rows) == len(pdf) == 85
    assert all(abs(row["value"] - pdf[row["geo_id"], row["year"]]) <= 0.5 for row in rows)
    assert sum(row["datatype"] == "estimate" for row in rows) == 17


@pytest.mark.parametrize("body", [b"<html>error</html>", b"[]", b"PKbroken"])
def test_soft_200_workbook_rejected(body):
    with pytest.raises(ValueError, match="readable XLSX"):
        me.parse_workbook(body)


def test_soft_200_pdf_rejected():
    with pytest.raises(ValueError, match="expected population PDF"):
        me.parse_pdf(b"<html>error</html>")


@pytest.mark.parametrize("sheet,cell,value,error", [
    (18, "C2", 2025, "year grid"),
    (18, "C3", 114957, "summary and age/sex totals disagree"),
    (18, "B3", -1, "invalid population"),
    (1, "C46", 6071, "age cells do not reconcile"),
])
def test_changed_grid_or_values_rejected(sheet, cell, value, error):
    with pytest.raises(ValueError, match=error):
        me.parse_workbook(_changed_numeric(sheet, cell, value))


def test_reuses_validated_originals(monkeypatch):
    manifest = (me.RAW_DIR / "manifest.json").read_bytes()
    monkeypatch.setattr(me.fetch, "get_bytes", lambda *_args: pytest.fail("unexpected network call"))
    me.acquire()
    assert (me.RAW_DIR / "manifest.json").read_bytes() == manifest
