"""Original Arkansas SDC time-series grid, precision and row meanings."""
import io
from functools import lru_cache
from zipfile import ZipFile
import xml.etree.ElementTree as ET

import pytest

from sdo_mcp import server, store
from sdo_mcp.ingest import ar


@lru_cache
def _body():
    return (ar.RAW_DIR / ar.FILE).read_bytes()


@pytest.fixture(scope="module")
def db_path(tmp_path_factory):
    path = tmp_path_factory.mktemp("ar-only") / "sdo.sqlite"
    conn = store.connect(path, create=True)
    store.init_db(conn)
    conn.execute("INSERT INTO geographies VALUES ('05','state','AR','Arkansas')")
    conn.executemany("INSERT INTO geographies VALUES (?,'county','AR',?)", ar.roster().items())
    conn.executemany("INSERT INTO coverage VALUES ('AR','population',?,'available','Original selected time-series product')", [("state",), ("county",)])
    ar.load(conn)
    ar.verify(conn)
    conn.close()
    return path


def _edit_xml(cell=None, value=None, *, xml_transform=None):
    original = ZipFile(io.BytesIO(_body()))
    output = io.BytesIO()
    with ZipFile(output, "w") as edited:
        for info in original.infolist():
            body = original.read(info.filename)
            if info.filename == "xl/worksheets/sheet1.xml":
                root = ET.fromstring(body)
                if cell:
                    ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
                    parent = root.find(f'.//s:c[@r="{cell}"]', ns)
                    if parent is None:
                        row_id = "".join(c for c in cell if c.isdigit())
                        row = root.find(f'.//s:row[@r="{row_id}"]', ns)
                        assert row is not None
                        parent = ET.SubElement(row, "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c", r=cell, t="n")
                    node = parent.find("s:v", ns)
                    if node is None:
                        node = ET.SubElement(parent, "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v")
                    node.text = str(value)
                if xml_transform:
                    xml_transform(root)
                body = ET.tostring(root)
            edited.writestr(info, body)
    return output.getvalue()


def test_exact_county_state_grid_precision_and_2013_boundary():
    rows = ar.parse(_body())
    assert len(rows) == 6536
    assert {(r["geo_id"], r["year"]) for r in rows} == {(g, y) for g in ("05", *ar.roster()) for y in range(1980, 2066)}
    state = server.get_forecast("AR", "state", "Arkansas", "population", 2013, 2014)
    assert state["status"] == "ok" and state["scenario"] is None
    assert state["series"] == [dict(year=2013, value=2959373, datatype="estimate"),
                               dict(year=2014, value=2975048.321292217, datatype="projection")]
    assert state["source"]["base_year"] == 2013 and state["source"]["horizon_year"] == 2065
    assert state["source"]["vintage"] == ar.VINTAGE
    assert "fractional persons" in state["source"]["method_notes"]
    assert server.get_forecast("AR", "county", "St. Francis", "population")["status"] == "ok"


@pytest.mark.parametrize("geo,first,horizon", [
    ("Benton", 242074.30416131904, 673336.1743284131),
    ("Pulaski", 393958.1640389359, 551832.5898480512),
    ("Calhoun", 5218.681172451978, 4158.875482473251),
])
def test_independent_original_ooxml_large_small_counties(geo, first, horizon):
    result = server.get_forecast("AR", "county", geo, "population", 2014, 2065)
    assert result["status"] == "ok"
    assert result["series"][0] == dict(year=2014, value=first, datatype="projection")
    assert result["series"][-1] == dict(year=2065, value=horizon, datatype="projection")


def test_fitted_bounds_components_and_other_products_not_served():
    result = server.get_forecast("AR", "state", "AR", "population", 2015, 2015)
    assert result["series"] == [dict(year=2015, value=2989826.309862175, datatype="projection")]
    assert server.get_forecast("AR", "state", "AR", "population", scenario="lower")["status"] == "error"
    for variable in ("households", "employment"):
        assert server.get_forecast("AR", "state", "AR", variable)["status"] == "coverage_unknown"
    assert server.get_components("AR", "AR")["status"] == "coverage_unknown"
    assert server.get_forecast("AR", "place", "Little Rock", "population")["status"] == "coverage_unknown"


@pytest.mark.parametrize("start,end", [(1970, 1979), (2066, 2100)])
def test_no_extension(start, end):
    result = server.get_forecast("AR", "state", "05", "population", start, end)
    assert result["status"] == "empty_range"


@pytest.mark.parametrize("cell,value,error", [
    ("C1", 1979, "year header"), ("AK5", -1, "positive population"),
    ("AK5", "NaN", "unreadable numeric"), ("AK5", "", "positive population"),
    ("AJ2", 18777.5, "positive population"), ("AK4", 999999, "confidence bounds"),
    ("C4", 123, "outside historical/forecast span"),
    ("AK20", 242075, "independently checked"),
])
def test_changed_header_suppressed_missing_numeric_or_bounds_rejected(cell, value, error):
    with pytest.raises(ValueError, match=error):
        ar.parse(_edit_xml(cell, value))


def test_missing_or_duplicate_county_row_rejected():
    ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    def remove(root):
        data = root.find("s:sheetData", ns)
        row = data.find('s:row[@r="20"]', ns)
        data.remove(row)
    with pytest.raises(ValueError, match="roster|semantics|positive"):
        ar.parse(_edit_xml(xml_transform=remove))


@pytest.mark.parametrize("body", [b"<html>Service unavailable</html>", b"[]", b"PKbroken"])
def test_soft_200_wrong_format_rejected(body):
    with pytest.raises(ValueError, match="readable XLSX"):
        ar.parse(body)


def test_reuse_offline_preserves_retrieval(monkeypatch):
    before = (ar.RAW_DIR / "manifest.json").read_bytes()
    monkeypatch.setattr(ar.fetch, "get_bytes", lambda *_: pytest.fail("unexpected network"))
    ar.acquire()
    assert (ar.RAW_DIR / "manifest.json").read_bytes() == before


@pytest.mark.parametrize("failed_file", list(ar.FILES))
def test_failed_source_archives_nothing(tmp_path, monkeypatch, failed_file):
    bodies = {url: (ar.RAW_DIR / name).read_bytes() for name, url in ar.FILES.items()}
    bodies[ar.FILES[failed_file]] = b"<html>temporary error</html>"
    raw = tmp_path / "ar"
    monkeypatch.setattr(ar, "RAW_DIR", raw)
    monkeypatch.setattr(ar.fetch, "get_bytes", lambda url: bodies[url])
    with pytest.raises(ValueError):
        ar.acquire()
    assert not raw.exists()
