"""Alaska September 2026 current geography, scenarios and independent tables."""

import io
import zipfile
from xml.etree import ElementTree

import pytest

from sdo_mcp import server, store
from sdo_mcp.ingest import ak


def _body(name):
    return (ak.RAW_DIR / name).read_bytes()


def _changed_cell(name, sheet, cell, value):
    output = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(_body(name))) as old, zipfile.ZipFile(output, "w") as new:
        for item in old.infolist():
            body = old.read(item.filename)
            if item.filename == f"xl/worksheets/sheet{sheet}.xml":
                root = ElementTree.fromstring(body)
                ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
                node = root.find(f".//{ns}c[@r='{cell}']")
                assert node is not None
                for child in list(node):
                    node.remove(child)
                if isinstance(value, str):
                    node.set("t", "inlineStr")
                    ElementTree.SubElement(ElementTree.SubElement(node, ns + "is"), ns + "t").text = value
                elif value is not None:
                    node.attrib.pop("t", None)
                    ElementTree.SubElement(node, ns + "v").text = str(value)
                body = ElementTree.tostring(root, encoding="utf-8", xml_declaration=True)
            new.writestr(item, body)
    return output.getvalue()


def test_state_scenarios_metadata_and_estimate_boundary():
    result = server.get_forecast("AK", "state", "Alaska", "population")
    assert result["status"] == "ok"
    assert result["scenario"] == "mid"
    assert result["series"][:2] == [{"year": 2025, "value": 738737, "datatype": "estimate"},
                                     {"year": 2026, "value": 739652, "datatype": "projection"}]
    assert [r["year"] for r in result["series"]] == list(ak.YEARS)
    for scenario, expected in (("low", 566586), ("mid", 724936), ("high", 925038)):
        point = server.get_forecast("AK", "state", "02", "population", 2055, 2055, scenario=scenario)
        assert point["series"] == [{"year": 2055, "value": expected, "datatype": "projection"}]
    source = result["source"]
    assert source["vintage"] == "September 2026"
    assert source["base_year"] == 2025
    assert source["horizon_year"] == 2055
    assert source["url"] == ak.CATALOG_URL
    assert source["retrieved_at"] == next(e["retrieved_at"] for e in ak.fetch.read_manifest(ak.RAW_DIR) if e["file"] == ak.STATE_FILE)


@pytest.mark.parametrize("name,gid,year,value", [
    ("Anchorage Municipality", "02020", 2055, 253626),
    ("Chugach", "02063", 2055, 5623),
    ("Copper River", "02066", 2025, 2628),
    ("Matanuska-Susitna", "02170", 2055, 159086),
    ("Juneau City and Borough", "02110", 2055, 23589),
    ("Skagway Municipality", "02230", 2055, 1085),
    ("Kusilvak", "02158", 2055, 9531),
])
def test_current_county_equivalents_no_old_geography_substitution(name, gid, year, value):
    result = server.get_forecast("AK", "county", name, "population", year, year)
    assert result == server.get_forecast("AK", "county", gid, "population", year, year)
    assert result["scenario"] is None
    assert result["series"] == [{"year": year, "value": value,
                                   "datatype": "estimate" if year == 2025 else "projection"}]


def test_county_single_series_grid_and_unverified_publication_status():
    result = server.get_forecast("AK", "county", "02063", "population")
    assert [r["year"] for r in result["series"]] == list(ak.COUNTY_YEARS)
    assert server.get_forecast("AK", "county", "02063", "population", scenario="low")["status"] == "error"
    assert server.get_forecast("AK", "county", "Chugach", "population", 2026, 2029)["status"] == "empty_range"
    assert server.get_forecast("AK", "county", "02261", "population")["status"] == "error"
    assert server.get_forecast("AK", "place", "Anchorage", "population")["status"] == "coverage_unknown"
    for variable in ("households", "employment"):
        assert server.get_forecast("AK", "state", "AK", variable)["status"] == "coverage_unknown"
    metadata = server.list_states()["states"]["AK"]
    assert metadata["scenario_geo_levels"] == ["state"]
    assert metadata["variables"]["population"]["county"]["load_status"] == "loaded"
    assert server.describe_source("AK")["variables"] == metadata["variables"]
    conn = store.connect()
    try:
        ak.verify(conn)
        assert conn.execute("SELECT COUNT(DISTINCT geo_id) FROM observations WHERE state='AK' AND geo_level='county'").fetchone()[0] == 30
    finally:
        conn.close()


def test_every_loaded_total_agrees_with_independent_pdf():
    rows = ak.parse_state_workbook(_body(ak.STATE_FILE)) + ak.parse_county_workbook(_body(ak.COUNTY_FILE_NAME))
    checks = ak.parse_report(_body(ak.REPORT_FILE))
    assert len(rows) == len(checks) == 303
    assert all(checks[r["geo_id"], r["year"], r.get("scenario", "")] == r["value"] for r in rows)


@pytest.mark.parametrize("parser", [ak.parse_state_workbook, ak.parse_county_workbook])
@pytest.mark.parametrize("body", [b"<html>Unavailable</html>", b"[]", b"PKbroken"])
def test_soft_200_workbook_rejected(parser, body):
    with pytest.raises(ValueError, match="readable XLSX"):
        parser(body)


def test_soft_200_report_rejected():
    with pytest.raises(ValueError, match="expected population report PDF"):
        ak.parse_report(b"<html>Unavailable</html>")


@pytest.mark.parametrize("cell,value,error", [
    ("A9", "2026-27", "annual population year grid"),
    ("C9", -1, "invalid population"),
    ("C13", 717258, "annual and five-year"),
])
def test_changed_state_year_value_or_cross_table_rejected(cell, value, error):
    with pytest.raises(ValueError, match=error):
        ak.parse_state_workbook(_changed_cell(ak.STATE_FILE, 2, cell, value))


@pytest.mark.parametrize("cell,value,error", [
    ("D3", "July 1, 2031", "years or estimate boundary"),
    ("B4", "Projection", "years or estimate boundary"),
    ("B13", -1, "invalid population"),
    ("B13", 6595, "do not reconcile"),
    ("A13", None, "incomplete county"),
    ("A14", "   Chugach Census Area", "duplicate county"),
    ("A13", "   Invented Census Area", "unknown or duplicate"),
])
def test_changed_county_grid_rejected(cell, value, error):
    with pytest.raises(ValueError, match=error):
        ak.parse_county_workbook(_changed_cell(ak.COUNTY_FILE_NAME, 2, cell, value))


def test_changed_annual_value_rejected_by_independent_pdf():
    bodies = {name: _body(name) for name in ak.FILES}
    bodies[ak.STATE_FILE] = _changed_cell(ak.STATE_FILE, 2, "C9", 734804)
    with pytest.raises(ValueError, match="independent PDF disagree"):
        ak._validate_all(bodies)


def test_reuses_immutable_validated_originals(monkeypatch):
    manifest = (ak.RAW_DIR / "manifest.json").read_bytes()
    monkeypatch.setattr(ak.fetch, "get_bytes", lambda *_args: pytest.fail("unexpected network call"))
    ak.acquire()
    assert (ak.RAW_DIR / "manifest.json").read_bytes() == manifest
