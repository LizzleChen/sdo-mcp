"""Nebraska's adopted CPAR product, published state row, and checked PDF grid."""

import io
from types import SimpleNamespace

import pytest

from sdo_mcp import server, store
from sdo_mcp.ingest import ne


def _body():
    return (ne.RAW_DIR / ne.REPORT_FILE).read_bytes()


def test_state_history_and_published_projections():
    result = server.get_forecast("NE", "state", "Nebraska", "population")
    assert result["status"] == "ok"
    assert result["series"] == [
        {"year": year, "value": value, "datatype": "estimate" if year == 2020 else "projection"}
        for year, value in zip(ne.YEARS, (1961504, 1995774, 2023184, 2031075))
    ]
    source = result["source"]
    assert (source["vintage"], source["base_year"], source["horizon_year"]) == ("August 2022", 2020, 2050)
    assert source["url"] == ne.REPORT_URL
    assert source["retrieved_at"] == next(e["retrieved_at"] for e in ne.fetch.read_manifest(ne.RAW_DIR)
                                          if e["file"] == ne.REPORT_FILE)
    assert "adopted national model" in source["method_notes"]
    assert "June 2025" in source["method_notes"]


@pytest.mark.parametrize("name,gid,year,value", [
    ("Adams", "31001", 2030, 29997),
    ("Box Butte", "31013", 2050, 10267),
    ("Douglas", "31055", 2050, 660606),
    ("Grant", "31075", 2030, 639),
    ("Keya Paha", "31103", 2050, 514),
    ("Red Willow", "31145", 2040, 8910),
    ("Sarpy", "31153", 2040, 232217),
    ("Scotts Bluff", "31157", 2050, 27704),
])
def test_pdf_names_and_census_fips(name, gid, year, value):
    by_name = server.get_forecast("NE", "county", name, "population", year, year)
    by_fips = server.get_forecast("NE", "county", gid, "population", year, year)
    assert by_name == by_fips
    assert by_name["series"] == [{"year": year, "value": value, "datatype": "projection"}]


def test_unknown_products_and_exact_decade_grid():
    for variable in ("households", "employment"):
        assert server.get_forecast("NE", "county", "Douglas", variable)["status"] == "coverage_unknown"
    assert server.get_forecast("NE", "place", "Omaha", "population")["status"] == "coverage_unknown"
    components = server.get_components("NE", "Nebraska")
    assert components["status"] == "coverage_unknown"
    assert components["geo_level"] == "state"
    assert server.describe_source("NE")["review"]["status"] == "never_reviewed"
    assert "regional-rivalry" in server.describe_source("NE")["methodology"]
    for year in (2025, 2029, 2045, 2051):
        assert server.get_forecast("NE", "state", "Nebraska", "population", year, year)["status"] == "empty_range"


def test_published_state_totals_and_complete_county_grid():
    conn = store.connect()
    try:
        ne.verify(conn)
        for year, discrepancy in zip(ne.YEARS, (0, 2, 1, 3)):
            state_value = conn.execute("SELECT value FROM observations WHERE state='NE' AND geo_level='state' AND year=?", (year,)).fetchone()[0]
            county_sum = conn.execute("SELECT SUM(value) FROM observations WHERE state='NE' AND geo_level='county' AND year=?", (year,)).fetchone()[0]
            assert state_value - county_sum == discrepancy
    finally:
        conn.close()
    assert len(ne.parse_pdf(_body())) == 376


@pytest.mark.parametrize("body", [b"<html>error</html>", b"[]", b"%PDFbroken"])
def test_soft_200_pdf_rejected(body):
    with pytest.raises(ValueError, match="expected readable population PDF"):
        ne.parse_pdf(body)


@pytest.mark.parametrize("old,new,error", [
    ("2050 \nProjected", "2051 \nProjected", "table year"),
    ("BoxButte", "MissingCounty", "unknown or duplicate"),
    ("KeyaPaha", "Grant", "unknown or duplicate"),
    ("29,997", "-29,997", "malformed population"),
    ("29,997", "29,998", "reconciliation"),
    ("model was adopted", "model was ignored", "changed model"),
])
def test_semantically_changed_pdf_rejected(monkeypatch, old, new, error):
    import pypdf

    original = pypdf.PdfReader(io.BytesIO(_body()))
    texts = [page.extract_text() for page in original.pages]
    assert any(old in text for text in texts)
    reader = SimpleNamespace(metadata=original.metadata,
                             pages=[SimpleNamespace(extract_text=lambda text=text: text.replace(old, new))
                                    for text in texts])
    monkeypatch.setattr(pypdf, "PdfReader", lambda _: reader)
    with pytest.raises(ValueError, match=error):
        ne.parse_pdf(_body())


def test_reuses_validated_originals(monkeypatch):
    manifest = (ne.RAW_DIR / "manifest.json").read_bytes()
    monkeypatch.setattr(ne.fetch, "get_bytes", lambda *_args: pytest.fail("unexpected network call"))
    ne.acquire()
    assert (ne.RAW_DIR / "manifest.json").read_bytes() == manifest
