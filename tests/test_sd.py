"""South Dakota source-era county, precision and complete-grid checks."""
import io
import re
import zipfile
from functools import lru_cache

import pytest

from sdo_mcp import server, store
from sdo_mcp.ingest import sd


@lru_cache
def _body():
    return (sd.RAW_DIR / sd.FILE).read_bytes()


@lru_cache
def _geographies():
    return sd.parse_geographies((sd.RAW_DIR / sd.GEO_FILE).read_bytes())


def _rewrite_zip(body, filename, transform):
    output = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(body)) as source, zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as target:
        for name in source.namelist():
            data = source.read(name)
            target.writestr(name, transform(data) if name == filename else data)
    return output.getvalue()


def _change_cell(cell, new):
    """Mutate original worksheet XML without discarding other cached formulas."""
    def transform(data):
        pattern = rb'(<c\b[^>]*\br="' + cell.encode() + rb'"[^>]*>.*?<v>)(.*?)(</v>)'
        changed, count = re.subn(pattern, lambda match: match[1] + str(new).encode() + match[3], data, count=1)
        assert count == 1
        return changed
    return _rewrite_zip(_body(), "xl/worksheets/sheet1.xml", transform)


def test_published_state_values_base_and_named_medium_series():
    result = server.get_forecast("SD", "state", "South Dakota", "population")
    assert result["status"] == "ok" and result["scenario"] == "medium"
    assert result["series"] == [
        dict(year=year, value=value, datatype="estimate" if year == 2010 else "projection")
        for year, value in zip(sd.YEARS, (814180, 852624.012396865, 889447.3152260791,
                                         922747.8576791115, 951884.9123444387, 977573.6733717498))
    ]
    assert result == server.get_forecast("SD", "state", "46", "population")
    explicit = server.get_forecast("SD", "state", "46", "population", scenario="medium")
    assert explicit["series"] == result["series"] and explicit["scenario"] == "medium"
    source = result["source"]
    assert source["vintage"] == sd.VINTAGE
    assert source["base_year"] == 2010 and source["horizon_year"] == 2035
    assert source["url"] == sd.URL
    assert source["retrieved_at"] == next(e["retrieved_at"] for e in sd.fetch.read_manifest(sd.RAW_DIR) if e["file"] == sd.FILE)
    assert "fractional persons" in source["method_notes"]
    assert "April 1, 2010" in source["method_notes"]
    assert "9,003" in source["method_notes"]


@pytest.mark.parametrize("name,gid,year,value", [
    ("Minnehaha", "46099", 2010, 169468), ("Minnehaha", "46099", 2035, 212353.3156841234),
    ("Jones", "46075", 2010, 1006), ("Jones", "46075", 2035, 651.1085612215595),
    ("Shannon", "46113", 2010, 13586), ("Shannon County", "46113", 2035, 19755.46602925523),
])
def test_original_county_name_fips_and_precision(name, gid, year, value):
    result = server.get_forecast("SD", "county", name, "population", year, year)
    assert result == server.get_forecast("SD", "county", gid, "population", year, year)
    assert result["series"] == [dict(year=year, value=value, datatype="estimate" if year == 2010 else "projection")]


@pytest.mark.parametrize("geo", ["46102", "102", "Oglala Lakota", "Oglala Lakota County"])
def test_modern_county_identifier_is_not_substituted(geo):
    result = server.get_forecast("SD", "county", geo, "population")
    assert result["status"] == "error"
    assert "series" not in result


def test_complete_grid_exact_source_geographies_and_independent_bases():
    conn = store.connect()
    try:
        sd.verify(conn)
        expected = {gid: name for gid, name, _ in _geographies().values()}
        actual = {r["geo_id"]: r["name"] for r in conn.execute("SELECT * FROM geographies WHERE state='SD' AND geo_level='county'")}
        assert expected == actual and len(actual) == 66 and "46102" not in actual
        for gid, _, base in _geographies().values():
            assert conn.execute("SELECT value FROM observations WHERE state='SD' AND geo_id=? AND year=2010", (gid,)).fetchone()[0] == base
    finally:
        conn.close()
    assert server.describe_source("SD")["review"]["status"] == "never_reviewed"


@pytest.mark.parametrize("start,end", [(2011, 2014), (2021, 2024), (2036, 2050)])
def test_no_annual_interpolation_or_extended_horizon(start, end):
    result = server.get_forecast("SD", "state", "SD", "population", start, end)
    assert result["status"] == "empty_range"
    assert result["available_start_year"] == 2010 and result["available_end_year"] == 2035


def test_unresolved_products_and_absent_scenarios():
    for variable in ("households", "employment"):
        assert server.get_forecast("SD", "county", "Minnehaha", variable)["status"] == "coverage_unknown"
    for level in ("place", "county_subdivision"):
        assert server.get_forecast("SD", level, "Sioux Falls", "population")["status"] == "coverage_unknown"
    assert server.get_components("SD", "Minnehaha")["status"] == "coverage_unknown"
    for scenario in ("low", "high"):
        assert server.get_forecast("SD", "state", "SD", "population", scenario=scenario)["status"] == "error"


@pytest.mark.parametrize("cell,new,error", [
    ("B2", 2005, "year grid"), ("C2", 2010, "year grid"),
    ("B3", -1, "nonnegative"), ("B3", "NaN", "invalid literal"), ("B3", "inf", "invalid literal"),
    ("B3", "1e309", "finite"),
    ("G66", 2659, "published total"), ("B66", 2711, "published total"),
])
def test_changed_year_nonfinite_negative_and_total_rejected(cell, new, error):
    with pytest.raises(ValueError, match=error):
        sd.parse(_change_cell(cell, new), _geographies())


@pytest.mark.parametrize("old,new,error", [
    (b'Medium Series', b'High Series', "scenario"),
    (b'0-4', b'1-4', "age grid"),
])
def test_changed_scenario_or_age_label_rejected(old, new, error):
    def transform(body):
        assert old in body
        return body.replace(old, new, 1)
    body = _rewrite_zip(_body(), "xl/sharedStrings.xml", transform)
    with pytest.raises(ValueError, match=error):
        sd.parse(body, _geographies())


@pytest.mark.parametrize("old,new", [(b'name="Aurora"', b'name="Unknown"'), (b'name="Aurora"', b'name="Beadle"')])
def test_unknown_and_duplicate_geography_rejected(old, new):
    body = _rewrite_zip(_body(), "xl/workbook.xml", lambda data: data.replace(old, new, 1))
    with pytest.raises(ValueError, match="geography grid"):
        sd.parse(body, _geographies())


@pytest.mark.parametrize("body", [b"<html>Unavailable</html>", b"PKbroken", b"[]"])
def test_soft_200_wrong_workbook_rejected(body):
    with pytest.raises(ValueError, match="readable population workbook"):
        sd.parse(body, _geographies())


def test_missing_workbook_sheet_rejected():
    from openpyxl import Workbook
    output = io.BytesIO()
    Workbook().save(output)
    with pytest.raises(ValueError, match="geography grid"):
        sd.parse(output.getvalue(), _geographies())


def test_geography_reference_requires_original_name_code_and_count():
    body = (sd.RAW_DIR / sd.GEO_FILE).read_bytes()
    with pytest.raises(ValueError, match="unreadable"):
        sd.parse_geographies(b"<html>Error</html>")
    for old, new in ((b"Shannon County", b"Oglala Lakota County"), (b"46113", b"46102"), (b"13586", b"13587")):
        def transform(data):
            return b"\n".join(line.replace(old, new, 1) if line.startswith(b"SD\t46113\t") else line for line in data.split(b"\n"))
        changed = _rewrite_zip(body, "Gaz_counties_national.txt", transform)
        with pytest.raises(ValueError, match="roster"):
            sd.parse_geographies(changed)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf"), True, "1000"])
def test_numeric_guard_rejects_nonfinite_boolean_and_text(value):
    with pytest.raises(ValueError, match="finite nonnegative"):
        sd._number(value)


def test_independent_worksheet_xml_decimal_anchors():
    # A separate direct XML read checks the original numeric caches. It does
    # not use openpyxl or the adapter's parsed observations.
    import xml.etree.ElementTree as ET
    ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(io.BytesIO(_body())) as archive:
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        names = [s.attrib["name"] for s in workbook.findall("s:sheets/s:sheet", ns)]
        for name, expected in (("So Dak Proj", "977573.67337174981"), ("Minnehaha", "212353.3156841234"),
                               ("Jones", "651.10856122155951"), ("Shannon", "19755.466029255229")):
            sheet = ET.fromstring(archive.read(f"xl/worksheets/sheet{names.index(name) + 1}.xml"))
            assert sheet.find('.//s:c[@r="G66"]/s:v', ns).text == expected


def test_reuse_is_offline_and_does_not_change_retrieval(monkeypatch):
    manifest = (sd.RAW_DIR / "manifest.json").read_bytes()
    monkeypatch.setattr(sd.fetch, "get_bytes", lambda *_: pytest.fail("unexpected network"))
    sd.acquire()
    assert (sd.RAW_DIR / "manifest.json").read_bytes() == manifest


@pytest.mark.parametrize("failed_file", list(sd.FILES))
def test_failed_source_or_evidence_archives_nothing(tmp_path, monkeypatch, failed_file):
    bodies = {url: (sd.RAW_DIR / name).read_bytes() for name, url in sd.FILES.items()}
    bodies[sd.FILES[failed_file]] = b"<html>Temporary error</html>"
    raw = tmp_path / "sd"
    monkeypatch.setattr(sd, "RAW_DIR", raw)
    monkeypatch.setattr(sd.fetch, "get_bytes", lambda url: bodies[url])
    with pytest.raises(ValueError):
        sd.acquire()
    assert not raw.exists()
