"""Original October2022 WV tables, Census labels and source disagreement guards."""
import io
from functools import lru_cache

import pytest
from pypdf import PdfReader, PdfWriter

from sdo_mcp import server, store
from sdo_mcp.ingest import wv


@lru_cache
def _body(name):
    return (wv.RAW_DIR / name).read_bytes()


@lru_cache
def _summary_pages():
    return tuple(p.extract_text() for p in PdfReader(io.BytesIO(_body(wv.FILE))).pages)


def test_rendered_state_history_and_forecast_totals():
    res = server.get_forecast("WV", "state", "West Virginia", "population")
    assert res["status"] == "ok" and res["scenario"] is None
    assert res["series"] == [dict(year=y, value=v, datatype="estimate" if y == 2020 else "projection")
        for y, v in zip((2020, 2025, 2030, 2035, 2040), (1793716, 1768247, 1747217, 1723594, 1705509))]
    assert res["source"]["vintage"] == "October 2022"
    assert res["source"]["base_year"] is None and res["source"]["horizon_year"] == 2040
    assert "Census-2020" in res["source"]["method_notes"]
    assert "conflicting" in res["source"]["method_notes"]
    assert "last underlying estimate" in res["source"]["method_notes"]
    assert "Health Care Authority" in res["source"]["method_notes"]
    assert res["source"]["retrieved_at"] == next(e["retrieved_at"] for e in wv.fetch.read_manifest(wv.RAW_DIR) if e["file"] == wv.FILE)
    conn = store.connect()
    try:
        wv.verify(conn)
        assert conn.execute("SELECT COUNT(DISTINCT geo_id) FROM observations WHERE state='WV' AND geo_level='county'").fetchone()[0] == 55
    finally:
        conn.close()


@pytest.mark.parametrize("name,gid,first,last", [
    ("Kanawha", "54039", 175931, 168766), ("Wirt", "54105", 4846, 4225),
    ("Berkeley", "54003", 136561, 170498), ("Doddridge", "54017", 7539, 7563),
])
def test_county_name_fips_and_independent_original_cells(name, gid, first, last):
    by_name = server.get_forecast("WV", "county", name, "population", 2025, 2040)
    assert by_name == server.get_forecast("WV", "county", gid, "population", 2025, 2040)
    assert by_name["series"][0]["value"] == first and by_name["series"][-1]["value"] == last
    assert all(r["datatype"] == "projection" for r in by_name["series"])


@pytest.mark.parametrize("start,end", [(2021, 2024), (2041, 2050), (2010, 2019)])
def test_no_interpolation_extension_or_generated_older_base(start, end):
    res = server.get_forecast("WV", "state", "WV", "population", start, end)
    assert res["status"] == "empty_range"
    assert res["available_start_year"] == 2020 and res["available_end_year"] == 2040


def test_unverified_products_and_invalid_requests():
    assert server.get_forecast("WV", "place", "Charleston", "population")["status"] == "coverage_unknown"
    for var in ("households", "employment"):
        assert server.get_forecast("WV", "county", "Kanawha", var)["status"] == "coverage_unknown"
    assert server.get_components("WV", "Kanawha")["status"] == "coverage_unknown"
    assert server.get_forecast("WV", "county", "unknown county", "population")["status"] == "error"
    assert server.get_forecast("WV", "state", "WV", "population", scenario="high")["status"] == "error"
    assert server.describe_source("WV")["review"]["status"] == "never_reviewed"


@pytest.mark.parametrize("old,new", [
    ("MALE & FEMALE", "FEMALE & MALE"), ("7/1/2040", "7/1/2050"),
    ("October 2022", "October 2024"), ("Wirt 5,194", "Wood 5,194"),
    ("1,793,716", "NaN"), ("1,793,716", "-1"), ("1,793,716", ""),
])
def test_changed_summary_schema_roster_edition_or_numeric_cells_rejected(old, new):
    text = _summary_pages()[2]
    assert old in text
    with pytest.raises(ValueError):
        wv._parse_summary_page(text.replace(old, new, 1), "MALE & FEMALE")


def test_independent_document_disagreement_is_rejected(monkeypatch):
    original = wv._parse_detail_page
    def altered(text, name):
        result = original(text, name)
        if name == "Wirt":
            result["MALE & FEMALE"] = (5194, 4847, 4676, 4423, 4225)
        return result
    monkeypatch.setattr(wv, "_parse_detail_page", altered)
    with pytest.raises(ValueError, match="independent detail"):
        wv.parse(_body(wv.FILE), _body(wv.DETAIL_FILE))


def test_changed_census_label_and_missing_age_or_sex_row_rejected():
    text = PdfReader(io.BytesIO(_body(wv.DETAIL_FILE))).pages[0].extract_text()
    for bad in (text.replace("Census-2020", "Estimate-2022"), text.replace("0-4 47,034", "0-5 47,034"),
                text.replace("FEMALE\n", "MALE\n", 1)):
        with pytest.raises(ValueError):
            wv._parse_detail_page(bad, "West Virginia")


@pytest.mark.parametrize("body", [b"<html>Not found</html>", b"%PDF-broken", b"[]"])
def test_soft_200_error_body_rejected(body):
    with pytest.raises(ValueError):
        wv.parse(body, _body(wv.DETAIL_FILE))


def test_missing_summary_page_rejected():
    writer = PdfWriter()
    writer.add_page(PdfReader(io.BytesIO(_body(wv.FILE))).pages[2])
    output = io.BytesIO(); writer.write(output)
    with pytest.raises(ValueError, match="page/geography grid"):
        wv.parse(output.getvalue(), _body(wv.DETAIL_FILE))
