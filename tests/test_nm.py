"""UNM-GPS county workbook, method boundary and PDF-backed fixtures."""

import io
import zipfile

import pytest

from sdo_mcp import server, store
from sdo_mcp.ingest import nm


def _body():
    return (nm.RAW_DIR / "county_totals_spring2024.xlsx").read_bytes()


def _changed_text(before: str, after: str) -> bytes:
    source = io.BytesIO(_body())
    target = io.BytesIO()
    with zipfile.ZipFile(source) as old, zipfile.ZipFile(target, "w") as new:
        for item in old.infolist():
            body = old.read(item.filename)
            if item.filename == "xl/sharedStrings.xml":
                assert body.count(before.encode()) == 1
                body = body.replace(before.encode(), after.encode())
            new.writestr(item, body)
    return target.getvalue()


def test_state_and_county_pdf_fixtures():
    result = server.get_forecast("NM", "state", "New Mexico", "population")
    assert result["series"] == [
        {"year": year, "value": value, "datatype": "estimate" if year == 2020 else "projection"}
        for year, value in zip((2020, 2025, 2030, 2035, 2040, 2045, 2050),
                               (2117527, 2143658, 2161645, 2164780, 2153964, 2131015, 2098886))
    ]
    source = result["source"]
    assert source["base_year"] == 2022
    assert source["horizon_year"] == 2050
    assert source["vintage"] == "Spring 2024"
    assert source["retrieved_at"] == next(e["retrieved_at"] for e in nm.fetch.read_manifest(nm.RAW_DIR)
                                          if e["file"] == "county_totals_spring2024.xlsx")
    assert "Santa Fe 2030" in source["method_notes"]
    for name, gid, year, value in (("Bernalillo", "35001", 2050, 681386),
                                   ("Harding", "35021", 2050, 471),
                                   ("Doña Ana", "35013", 2025, 224218),
                                   ("Santa Fe", "35049", 2030, 164745)):
        county = server.get_forecast("NM", "county", name, "population",
                                     start_year=year, end_year=year)
        assert county == server.get_forecast("NM", "county", gid, "population",
                                             start_year=year, end_year=year)
        assert county["series"] == [{"year": year, "value": value, "datatype": "projection"}]


def test_complete_grid_and_no_invented_values():
    conn = store.connect()
    try:
        nm.verify(conn)
        assert conn.execute("SELECT COUNT(*) FROM observations WHERE state='NM'").fetchone()[0] == 238
    finally:
        conn.close()
    assert server.get_forecast("NM", "county", "Santa Fe", "population", start_year=2022,
                               end_year=2024)["status"] == "empty_range"
    assert server.get_forecast("NM", "county", "Santa Fe", "population", start_year=2051)["status"] == "empty_range"
    assert server.get_forecast("NM", "place", "Santa Fe", "population")["status"] == "coverage_unknown"
    assert server.get_forecast("NM", "state", "NM", "population", scenario="high")["status"] == "error"
    assert server.get_components("NM", "Santa Fe")["status"] == "coverage_unknown"
    assert server.describe_source("NM")["review"]["status"] == "never_reviewed"


@pytest.mark.parametrize("body", [b"<html>error</html>", b"[]", b"PKbroken"])
def test_soft_200_rejected(body):
    with pytest.raises(ValueError, match="readable XLSX"):
        nm.parse_workbook(body)


@pytest.mark.parametrize("before,after,error", [
    ("Projected2030", "Projected2031", "year header"),
    ('<t xml:space="preserve">Santa Fe</t>',
     '<t xml:space="preserve">Unknown County</t>', "geography"),
    ("164,745", "suppressed", "invalid population"),
])
def test_changed_publisher_semantics_rejected(before, after, error):
    with pytest.raises(ValueError, match=error):
        nm.parse_workbook(_changed_text(before, after))


def test_reuses_saved_originals(monkeypatch):
    manifest = (nm.RAW_DIR / "manifest.json").read_bytes()
    monkeypatch.setattr(nm.fetch, "get_bytes", lambda *_args: pytest.fail("unexpected network call"))
    nm.acquire()
    assert (nm.RAW_DIR / "manifest.json").read_bytes() == manifest
