"""Mississippi original 2019 PDF, launch-year and deferred-geography semantics."""
import io
from functools import lru_cache

import pytest
from pypdf import PdfReader, PdfWriter

from sdo_mcp import server, store
from sdo_mcp.ingest import ms


@lru_cache
def _body():
    return (ms.RAW_DIR / ms.FILE).read_bytes()


@lru_cache
def _pages():
    return tuple(page.extract_text() for page in PdfReader(io.BytesIO(_body())).pages)


def test_exact_rendered_totals_2019_vintage_and_2010_launch():
    result = server.get_forecast("MS", "state", "Mississippi", "population")
    assert result["status"] == "ok" and result["scenario"] is None
    assert result == server.get_forecast("MS", "state", "28", "population")
    assert result["series"] == [dict(year=year, value=value, datatype="projection")
                                for year, value in zip(ms.YEARS, (3066382, 3095026, 3104159, 3099766, 3082567, 3078363, 3064588))]
    source = result["source"]
    assert source["vintage"] == ms.VINTAGE and source["base_year"] == 2010
    assert source["horizon_year"] == 2050 and source["url"] == ms.URL
    assert source["retrieved_at"] == next(e["retrieved_at"] for e in ms.fetch.read_manifest(ms.RAW_DIR) if e["file"] == ms.FILE)
    assert "not a forecast rebased to the 2020 Census" in source["method_notes"]
    assert "three persons" in source["method_notes"]
    conn = store.connect()
    try:
        ms.verify(conn)
    finally:
        conn.close()


def test_published_county_place_products_are_deferred():
    assert server.get_forecast("MS", "county", "Hinds", "population")["status"] == "not_loaded"
    assert server.get_forecast("MS", "place", "Jackson", "population")["status"] == "not_loaded"
    assert server.describe_source("MS")["review"]["status"] == "never_reviewed"
    for variable in ("households", "employment"):
        assert server.get_forecast("MS", "state", "MS", variable)["status"] == "coverage_unknown"
    assert server.get_components("MS", "MS")["status"] == "coverage_unknown"
    assert server.get_forecast("MS", "state", "MS", "population", scenario="medium")["status"] == "error"


@pytest.mark.parametrize("start,end", [(2010, 2019), (2021, 2024), (2051, 2070)])
def test_no_fabricated_launch_count_interpolation_or_extension(start, end):
    result = server.get_forecast("MS", "state", "MS", "population", start, end)
    assert result["status"] == "empty_range"
    assert result["available_start_year"] == 2020 and result["available_end_year"] == 2050


def test_all_pdf_pages_age_sex_and_race_totals_checked():
    assert tuple(ms._parse_page(text, year) for text, year in zip(_pages(), ms.YEARS)) == ms.STATE_VALUES
    assert len(ms.parse(_body())) == 7


@pytest.mark.parametrize("old,new,error", [
    ("Mississippi - 2020", "Mississippi - 2010", "year grid"),
    ("Mississippi - 2020", "Alabama - 2020", "state"),
    ("WHITE NONWHITE TOTAL", "NONWHITE WHITE TOTAL", "race header"),
    ("SEXES MALE FEMALE", "SEXES FEMALE MALE", "sex-column header"),
    ("0 - 4", "0 - 5", "age/column grid"),
    ("3,066,382", "NaN", "integer"), ("3,066,382", "-1", "integer"),
    ("3,066,382", "3066382.0", "integer"), ("3,066,382", "3,066,400", "sex cells"),
    ("98,853", "98,854", "rounding differences"),
])
def test_changed_format_columns_year_or_numeric_cells_rejected(old, new, error):
    text = _pages()[0]
    assert old in text
    with pytest.raises(ValueError, match=error):
        ms._parse_page(text.replace(old, new, 1), 2020)


def test_missing_duplicate_and_unexpected_rows_rejected():
    text = _pages()[0]
    total = next(line for line in text.splitlines() if line.startswith("TOTAL "))
    for bad in (text.replace(total, ""), text + "\n" + total,
                "\n".join(line for line in text.splitlines() if not line.startswith("85 + ")),
                text + "\nUnexpected row"):
        with pytest.raises(ValueError, match="total|grid"):
            ms._parse_page(bad, 2020)


@pytest.mark.parametrize("body", [b"<html>Service unavailable</html>", b"%PDF-broken", b"[]"])
def test_soft_200_pdf_rejected(body):
    with pytest.raises(ValueError, match="readable PDF"):
        ms.parse(body)


def test_wrong_readable_pdf_and_missing_year_pages_rejected():
    for count in (1, 6):
        writer = PdfWriter()
        if count == 1:
            writer.add_blank_page(612, 792)
        else:
            for page in PdfReader(io.BytesIO(_body())).pages[:count]:
                writer.add_page(page)
        output = io.BytesIO()
        writer.write(output)
        with pytest.raises(ValueError, match="page grid"):
            ms.parse(output.getvalue())


def test_out_of_order_year_pages_rejected():
    reader = PdfReader(io.BytesIO(_body()))
    writer = PdfWriter()
    for index in (1, 0, 2, 3, 4, 5, 6):
        writer.add_page(reader.pages[index])
    output = io.BytesIO()
    writer.write(output)
    with pytest.raises(ValueError, match="year grid"):
        ms.parse(output.getvalue())


def test_wrong_valid_methods_pdf_cannot_establish_base():
    with pytest.raises(ValueError, match="methods page grid"):
        ms._validate_methods(_body())


def test_reuse_is_offline_preserves_retrieval(monkeypatch):
    before = (ms.RAW_DIR / "manifest.json").read_bytes()
    monkeypatch.setattr(ms.fetch, "get_bytes", lambda *_: pytest.fail("unexpected network call"))
    ms.acquire()
    assert (ms.RAW_DIR / "manifest.json").read_bytes() == before


@pytest.mark.parametrize("failed_file", list(ms.FILES))
def test_failed_pdf_or_catalog_archives_nothing(tmp_path, monkeypatch, failed_file):
    bodies = {url: (ms.RAW_DIR / name).read_bytes() for name, url in ms.FILES.items()}
    bodies[ms.FILES[failed_file]] = b"<html>temporary error</html>"
    raw = tmp_path / "ms"
    monkeypatch.setattr(ms, "RAW_DIR", raw)
    monkeypatch.setattr(ms.fetch, "get_bytes", lambda url: bodies[url])
    with pytest.raises(ValueError):
        ms.acquire()
    assert not raw.exists()
