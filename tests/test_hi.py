"""Hawaii source definitions, combined county semantics, and original precision."""

import io
import zipfile
from xml.etree import ElementTree

import pytest

from sdo_mcp import server, store
from sdo_mcp.ingest import hi


def _body(name):
    return (hi.RAW_DIR / name).read_bytes()


def _changed_cell(sheet, cell, value):
    output = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(_body(hi.WORKBOOK_FILE))) as old, zipfile.ZipFile(output, "w") as new:
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


def test_resident_population_precision_and_separate_population_base():
    result = server.get_forecast("HI", "state", "Hawaii", "population")
    assert result["status"] == "ok"
    assert result["scenario"] is None
    assert [r["year"] for r in result["series"]] == list(hi.POP_YEARS)
    assert result["series"][0]["value"] == pytest.approx(1451043)
    assert result["series"][0]["datatype"] == "estimate"
    assert result["series"][-1] == {"year": 2050, "value": 1560885.7897387256, "datatype": "projection"}
    source = result["source"]
    assert source["vintage"] == "April 2024"
    assert source["base_year"] == 2020
    assert source["horizon_year"] == 2050
    assert source["url"] == hi.CATALOG_URL
    assert source["retrieved_at"] == next(e["retrieved_at"] for e in hi.fetch.read_manifest(hi.RAW_DIR) if e["file"] == hi.WORKBOOK_FILE)
    assert "estimate edition" in source["method_notes"]
    assert "military" in source["method_notes"]
    assert result["series"][-1]["value"] != 1774820  # Published de facto population, never resident population.


@pytest.mark.parametrize("name,gid,value", [
    ("Hawaii", "15001", 230730.9165990558),
    ("Honolulu", "15003", 1060108.4540644009),
    ("Kauai", "15007", 85179.54242308089),
    (hi.COMBINED_NAME, hi.COMBINED_ID, 184866.8766521879),
])
def test_published_county_groups(name, gid, value):
    result = server.get_forecast("HI", "county", name, "population", 2050, 2050)
    assert result == server.get_forecast("HI", "county", gid, "population", 2050, 2050)
    assert result["series"] == [{"year": 2050, "value": value, "datatype": "projection"}]


@pytest.mark.parametrize("gid", ["15005", "15009", "Kalawao", "Maui"])
@pytest.mark.parametrize("variable", ["population", "employment"])
def test_isolated_maui_and_kalawao_receive_explicit_refusal(gid, variable):
    result = server.get_forecast("HI", "county", gid, variable)
    assert result["status"] == "not_published"
    assert "hi-maui-kalawao" in result["reason"]
    assert "series" not in result
    assert result["closest_published"] is None


def test_combined_id_requery_and_ambiguous_partial_name():
    combined = server.get_forecast("HI", "county", hi.COMBINED_ID, "population")
    assert combined["geo"] == {"level": "county", "id": hi.COMBINED_ID, "name": hi.COMBINED_NAME}
    assert combined["series"][1]["value"] == 173620.30660481827
    assert "173520" in combined["source"]["method_notes"]
    ambiguous = server.get_forecast("HI", "county", "Mau", "population")
    assert ambiguous["status"] == "error"
    assert {g["geo_id"] for g in ambiguous["candidates"]} == {"15009", hi.COMBINED_ID}


def test_eligible_civilian_total_jobs_and_separate_base_year():
    result = server.get_forecast("HI", "state", "15", "employment")
    assert result["series"] == [{"year": y, "value": v, "datatype": "estimate" if y == 2022 else "projection"}
                                for y, v in zip(hi.JOBS_YEARS, (853100, 894370, 939270, 979350))]
    assert result["source"]["base_year"] == 2022
    assert "civilian total jobs" in result["source"]["product"]
    assert "military jobs" in result["source"]["method_notes"].lower()
    assert "proprietors" in result["source"]["method_notes"]
    result = server.get_forecast("HI", "county", hi.COMBINED_ID, "employment", 2050, 2050)
    assert result["series"] == [{"year": 2050, "value": 129980, "datatype": "projection"}]
    conn = store.connect()
    try:
        hi.verify(conn)
        row = conn.execute("SELECT SUM(value) FROM observations WHERE state='HI' AND variable='employment' AND geo_level='county' AND year=2022").fetchone()
        assert row[0] == 853110  # Independently rounded source county totals retained.
    finally:
        conn.close()


def test_no_interpolation_and_unverified_products_remain_unknown():
    assert server.get_forecast("HI", "state", "HI", "population", 2021, 2029)["status"] == "empty_range"
    assert server.get_forecast("HI", "county", "15001", "employment", 2023, 2029)["status"] == "empty_range"
    assert server.get_forecast("HI", "state", "HI", "households")["status"] == "coverage_unknown"
    assert server.get_forecast("HI", "place", "Honolulu", "population")["status"] == "coverage_unknown"
    metadata = server.list_states()["states"]["HI"]
    assert metadata["variables"]["employment"]["county"]["load_status"] == "loaded"
    description = server.describe_source("HI")
    assert description["variables"] == metadata["variables"]
    assert {s["base_year"] for s in description["sources_loaded"]} == {2020, 2022}
    assert any("173520" in caveat for caveat in description["caveats"])


def test_independent_report_anchors_and_documented_publisher_discrepancy():
    rows = hi._validate_all({name: _body(name) for name in hi.FILES})
    checks = hi.parse_report(_body(hi.REPORT_FILE))
    assert len(rows) == len(checks) == 40
    assert checks["15", 2050, "population"] == 1560890
    assert checks[hi.COMBINED_ID, 2030, "population"] == 173520
    assert checks["15", 2050, "employment"] == 979350
    assert next(r["value"] for r in rows if r["geo_id"] == hi.COMBINED_ID and r["year"] == 2030 and r["variable"] == "population") == 173620.30660481827


@pytest.mark.parametrize("body", [b"<html>Unavailable</html>", b"[]", b"PKbroken"])
def test_soft_200_workbook_rejected(body):
    with pytest.raises(ValueError, match="readable XLSX"):
        hi.parse_workbook(body)


def test_soft_200_report_and_geography_evidence_rejected():
    with pytest.raises(ValueError, match="expected population/economic report PDF"):
        hi.parse_report(b"<html>Unavailable</html>")
    with pytest.raises(ValueError, match="combined-county geography evidence"):
        hi._validate_geographies(b"<html>Unavailable</html>", _body(hi.BEA_FILE))


@pytest.mark.parametrize("sheet,cell,value,error", [
    (3, "D2", 2041, "population years"),
    (3, "B2", "2020 projected", "population years"),
    (3, "A4", "De facto population", "population years"),
    (3, "C4", -1, "invalid numeric"),
    (3, "C4", 1501151, "age-table totals disagree"),
    (3, "B10", 0, "age groups do not reconcile"),
    (39, "B2", "2022 projected", "jobs years"),
    (39, "A3", "Labor force", "jobs years"),
    (39, "B3", "853100", "invalid numeric"),
    (40, "E3", 133620, "jobs exceed publication rounding"),
])
def test_changed_definitions_years_totals_and_values_rejected(sheet, cell, value, error):
    with pytest.raises(ValueError, match=error):
        hi.parse_workbook(_changed_cell(sheet, cell, value))


def test_reuses_immutable_validated_originals(monkeypatch):
    manifest = (hi.RAW_DIR / "manifest.json").read_bytes()
    monkeypatch.setattr(hi.fetch, "get_bytes", lambda *_args: pytest.fail("unexpected network call"))
    hi.acquire()
    assert (hi.RAW_DIR / "manifest.json").read_bytes() == manifest
