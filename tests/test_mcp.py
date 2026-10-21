"""Exercise the installed wheel through real current and older MCP connections."""

import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
from importlib.metadata import version

import anyio
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.shared.exceptions import MCPError
from mcp.types import INVALID_PARAMS
import pytest

from sdo_mcp import bundle, server, store


@pytest.fixture(scope="module")
def installed_server(db_path, tmp_path_factory):
    folder = tmp_path_factory.mktemp("installed-server")
    root = Path(__file__).resolve().parents[1]

    def run(*args, cwd=folder):
        return subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True, timeout=180)

    # Build from a copy so the test bundles its own data without touching the checkout.
    project = folder / "project"
    shutil.copytree(root / "src", project / "src",
                    ignore=shutil.ignore_patterns("__pycache__", "data"))
    for name in ("pyproject.toml", "hatch_build.py", ".gitignore"):
        shutil.copy2(root / name, project / name)
    bundle.bundle_database(db_path, project / "src" / "sdo_mcp" / "data" / "sdo.sqlite")
    run("uv", "build", "--wheel", "--out-dir", str(folder / "dist"), cwd=project)
    run("uv", "venv", "--python", sys.executable, str(folder / "env"))
    scripts = folder / "env" / ("Scripts" if os.name == "nt" else "bin")
    python = scripts / ("python.exe" if os.name == "nt" else "python")
    wheel, = (folder / "dist").glob("*.whl")
    run("uv", "pip", "install", "--python", str(python), str(wheel))
    # Installing the wheel alone must install the data; no SDO_DB is set.
    result = run(str(python), "-c", "from sdo_mcp import store; print(store.db_path())")
    assert str(folder / "env") in result.stdout
    return python, folder


@pytest.mark.parametrize("protocol", ["2026-07-28", "2025-11-25"])
def test_installed_tools_over_mcp(installed_server, protocol):
    python, folder = installed_server

    async def check():
        params = StdioServerParameters(
            command=str(python), args=["-m", "sdo_mcp.server"], cwd=str(folder),
        )
        with anyio.fail_after(45):
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as client:
                    if protocol == "2026-07-28":
                        await client.discover()
                    else:
                        await client.initialize()
                    assert client.protocol_version == protocol
                    assert client.server_info.version == version("sdo-mcp")
                    tools = {t.name: t for t in (await client.list_tools()).tools}
                    assert set(tools) == {"list_states", "get_forecast", "get_components", "describe_source"}
                    for tool in tools.values():
                        assert tool.output_schema["properties"]
                        assert tool.annotations.read_only_hint is True
                        assert tool.annotations.destructive_hint is False
                        assert tool.annotations.idempotent_hint is True
                        assert tool.annotations.open_world_hint is False

                    async def call(name, args, status=None, error=False):
                        result = await client.call_tool(name, args)
                        assert result.is_error is error
                        data = result.structured_content
                        assert data is not None
                        assert json.loads(result.content[0].text) == data
                        if status:
                            assert data["status"] == status
                        return data

                    summary = await call("list_states", {})
                    assert summary["database_release"] == client.server_info.version
                    assert len(summary["states"]) == 50
                    assert {"AR", "IA", "LA", "MT", "OK", "VT", "WV"} <= set(summary["states"])
                    assert sum(state["data_loaded"] for state in summary["states"].values()) == 49
                    assert summary["states"]["MT"]["data_loaded"] is False
                    vt_settings = summary["states"]["VT"]["scenario_settings_by_geo"]
                    assert vt_settings["state"]["default_scenario"] == "current_trends"
                    assert vt_settings["county"]["default_scenario"] == "b"
                    for state, level, geo, year, value, base in (
                        ("AR", "county", "Calhoun", 2065, 4158.875482473251, 2013),
                        ("IA", "county", "Polk", 2000, 326900, 1980),
                        ("LA", "county", "Jefferson Davis", 2030, 29720, 2005),
                        ("OK", "county", "Cimarron", 2070, 1356, None),
                        ("VT", "state", "VT", 2050, 644731, None),
                        ("VT", "county", "Chittenden", 2030, 162967, 2010),
                        ("WV", "county", "Wirt", 2040, 4225, None),
                    ):
                        forecast = await call("get_forecast", {
                            "state": state, "geo_level": level, "geo": geo,
                            "variable": "population", "start_year": year, "end_year": year,
                        }, "ok")
                        assert forecast["series"] == [{"year": year, "value": value, "datatype": "projection"}]
                        assert forecast["source"]["base_year"] == base
                        assert forecast["source"]["retrieved_at"]
                        if state == "VT":
                            assert forecast["scenario"] == vt_settings[level]["default_scenario"]
                            assert forecast["scenario_note"] == vt_settings[level]["default_scenario_note"]
                    for level, geo, scenario in (("state", "VT", "b"), ("county", "Chittenden", "current_trends")):
                        await call("get_forecast", {
                            "state": "VT", "geo_level": level, "geo": geo,
                            "variable": "population", "scenario": scenario,
                        }, "error", True)
                    await call("get_forecast", {
                        "state": "MT", "geo_level": "state", "geo": "MT", "variable": "population",
                    }, "coverage_unknown")
                    await call("get_components", {"state": "MT", "geo": "MT"}, "coverage_unknown")
                    for state in ("AR", "IA", "LA", "MT", "OK", "VT", "WV"):
                        described = await call("describe_source", {"state": state})
                        assert bool(described["sources_loaded"]) is (state != "MT")
                        assert described["review"]["status"] == "never_reviewed"
                    assert {"VA", "WI", "UT", "IN", "MI", "PA", "KY", "IL", "MD"} <= set(summary["states"])
                    assert {"AK", "HI", "ME", "NE", "NH", "OH", "NV"} <= set(summary["states"])
                    assert {"CT", "MA", "NJ", "NY", "RI"} <= set(summary["states"])
                    assert {"ID", "KS", "MO", "MS", "ND", "SD"} <= set(summary["states"])
                    assert all(summary["states"][state]["data_loaded"] for state in ("ID", "KS", "MO", "MS", "ND", "SD"))
                    for state, level, geo, year, value, base in (
                        ("ID", "state", "ID", 2034, 2364544, None),
                        ("KS", "county", "Greeley", 2021, 873, None),
                        ("MO", "county", "Adair", 2005, 24690, 2007),
                        ("MS", "state", "MS", 2050, 3064588, 2010),
                        ("ND", "state", "ND", 2050, 957194, 2020),
                        ("SD", "county", "Shannon", 2035, 19755.46602925523, 2010),
                    ):
                        forecast = await call("get_forecast", {
                            "state": state, "geo_level": level, "geo": geo,
                            "variable": "population", "start_year": year, "end_year": year,
                        }, "ok")
                        assert forecast["series"] == [{"year": year, "value": value, "datatype": "projection"}]
                        assert forecast["source"]["base_year"] == base
                        assert forecast["source"]["retrieved_at"]
                    await call("get_forecast", {
                        "state": "KS", "geo_level": "state", "geo": "KS", "variable": "population",
                    }, "coverage_unknown")
                    await call("get_forecast", {
                        "state": "MS", "geo_level": "county", "geo": "Hinds", "variable": "population",
                    }, "not_loaded")
                    await call("get_forecast", {
                        "state": "KS", "geo_level": "county", "geo": "Greeley", "variable": "population",
                        "start_year": 2026, "end_year": 2030,
                    }, "empty_range")
                    await call("get_forecast", {
                        "state": "SD", "geo_level": "county", "geo": "46102", "variable": "population",
                    }, "error", True)
                    await call("get_components", {
                        "state": "ND", "geo": "ND",
                    }, "pdf_only")
                    for state in ("ID", "KS", "MO", "MS", "ND", "SD"):
                        described = await call("describe_source", {"state": state})
                        assert described["sources_loaded"]
                        assert described["review"]["status"] == "never_reviewed"
                    for state, level, geo, year, value, base, datatype in (
                        ("CT", "county", "Fairfield", 2040, 905219, 2010, "projection"),
                        ("CT", "cog", "Southeastern CT", 2040, 303785, 2010, "projection"),
                        ("MA", "state", "MA", 2020, 7039146.791183238, 2020, "estimate"),
                        ("NJ", "county", "Bergen", 2034, 1065500, 2014, "projection"),
                        ("NY", "county", "Albany", 2040, 328968, 2015, "projection"),
                        ("RI", "county_subdivision", "Providence", 2050, 201447, None, "projection"),
                    ):
                        forecast = await call("get_forecast", {
                            "state": state, "geo_level": level, "geo": geo,
                            "variable": "population", "start_year": year, "end_year": year,
                        }, "ok")
                        assert forecast["series"] == [{"year": year, "value": value, "datatype": datatype}]
                        assert forecast["source"]["base_year"] == base
                    ny = await call("get_forecast", {
                        "state": "NY", "geo_level": "state", "geo": "NY", "variable": "population",
                        "start_year": 2022, "end_year": 2022,
                    }, "ok")
                    assert ny["series"] == [{"year": 2022, "value": 19673203, "datatype": "estimate"}]
                    assert ny["scenario"] == "middle" and "server" in ny["scenario_note"]
                    await call("get_forecast", {
                        "state": "NY", "geo_level": "economic_region", "geo": "Capital District", "variable": "population",
                    }, "not_loaded")
                    await call("get_forecast", {
                        "state": "RI", "geo_level": "county_subdivision", "geo": "Kingstown", "variable": "population",
                    }, "error", True)
                    await call("get_forecast", {
                        "state": "RI", "geo_level": "county", "geo": "Providence", "variable": "population",
                    }, "coverage_unknown")
                    for state in ("CT", "MA", "NJ", "NY", "RI"):
                        described = await call("describe_source", {"state": state})
                        assert described["sources_loaded"]
                        assert described["review"]["status"] == "never_reviewed"
                    for state, geo, year, value, base_year in (
                        ("AK", "Chugach", 2055, 5623, 2025),
                        ("HI", "hi-maui-kalawao", 2030, 173620.30660481827, 2020),
                        ("ME", "Cumberland", 2032, 322972.8624317943, 2022),
                        ("NE", "Keya Paha", 2050, 514, 2020),
                        ("NH", "Carroll", 2020, 50111, 2020),
                        ("OH", "Ottawa", 2050, 31371, 2020),
                        ("NV", "Carson City", 2044, 64275, 2024),
                    ):
                        forecast = await call("get_forecast", {
                            "state": state, "geo_level": "county", "geo": geo,
                            "variable": "population", "start_year": year, "end_year": year,
                        }, "ok")
                        assert forecast["series"] == [{"year": year, "value": value,
                                                       "datatype": "estimate" if year == 2020 else "projection"}]
                        assert forecast["source"]["base_year"] == base_year
                        assert forecast["source"]["retrieved_at"]
                    jobs = await call("get_forecast", {
                        "state": "HI", "geo_level": "county", "geo": "hi-maui-kalawao",
                        "variable": "employment", "start_year": 2050, "end_year": 2050,
                    }, "ok")
                    assert jobs["series"][0]["value"] == 129980
                    assert jobs["source"]["base_year"] == 2022
                    for variable in ("population", "employment"):
                        refusal = await call("get_forecast", {
                            "state": "HI", "geo_level": "county", "geo": "Maui", "variable": variable,
                        }, "not_published")
                        assert "hi-maui-kalawao" in refusal["reason"]
                        assert "series" not in refusal
                    await call("get_forecast", {
                        "state": "AK", "geo_level": "county", "geo": "Chugach",
                        "variable": "population", "scenario": "high",
                    }, "error", True)
                    high = await call("get_forecast", {
                        "state": "AK", "geo_level": "state", "geo": "AK", "variable": "population",
                        "scenario": "high", "start_year": 2055, "end_year": 2055,
                    }, "ok")
                    assert high["series"][0]["value"] == 925038
                    await call("get_forecast", {
                        "state": "ME", "geo_level": "state", "geo": "ME", "variable": "population",
                        "start_year": 2028, "end_year": 2028,
                    }, "empty_range")
                    await call("get_components", {"state": "NH", "geo": "Carroll"}, "pdf_only")
                    hi_source = await call("describe_source", {"state": "HI"})
                    assert {source["base_year"] for source in hi_source["sources_loaded"]} == {2020, 2022}
                    for variable, value in (("population", 584130), ("households", 262030), ("employment", 454800)):
                        maryland = await call("get_forecast", {
                            "state": "MD", "geo_level": "county", "geo": "Baltimore City",
                            "variable": variable, "start_year": 2050, "end_year": 2050,
                        }, "ok")
                        assert maryland["geo"]["id"] == "24510"
                        assert maryland["series"] == [{"year": 2050, "value": value, "datatype": "projection"}]
                    await call("get_forecast", {
                        "state": "MD", "geo_level": "place", "geo": "Baltimore", "variable": "population",
                    }, "coverage_unknown")
                    illinois = await call("get_forecast", {
                        "state": "IL", "geo_level": "county", "geo": "Cook", "variable": "population",
                        "start_year": 2020, "end_year": 2025,
                    }, "ok")
                    assert illinois["series"] == [
                        {"year": 2020, "value": 5262741, "datatype": "estimate"},
                        {"year": 2025, "value": 5148792, "datatype": "projection"},
                    ]
                    assert illinois["source"]["base_year"] == 2020
                    await call("get_forecast", {
                        "state": "IL", "geo_level": "place", "geo": "Chicago", "variable": "population",
                    }, "not_loaded")
                    await call("get_components", {"state": "IL", "geo": "Cook"}, "pdf_only")
                    il_description = await call("describe_source", {"state": "IL"})
                    assert il_description["review"]["status"] == "never_reviewed"
                    assert "Table 3" in il_description["sources_loaded"][0]["citation"]
                    for variable, value in (("population", 4785233), ("households", 1944624)):
                        kentucky = await call("get_forecast", {
                            "state": "KY", "geo_level": "state", "geo": "KY", "variable": variable,
                            "start_year": 2050, "end_year": 2050,
                        }, "ok")
                        assert kentucky["series"] == [{"year": 2050, "value": value, "datatype": "projection"}]
                        assert kentucky["source"]["base_year"] == 2021
                    pennsylvania = await call("get_forecast", {
                        "state": "PA", "geo_level": "county", "geo": "Philadelphia", "variable": "population",
                        "start_year": 2020, "end_year": 2025,
                    }, "ok")
                    assert pennsylvania["series"] == [
                        {"year": 2020, "value": 1600600, "datatype": "estimate"},
                        {"year": 2025, "value": 1662041, "datatype": "projection"},
                    ]
                    assert pennsylvania["source"]["vintage"] == "2023"
                    assert pennsylvania["source"]["base_year"] == 2020
                    michigan = await call("get_forecast", {
                        "state": "MI", "geo_level": "county", "geo": "Wayne", "variable": "population",
                        "start_year": 2050, "end_year": 2050,
                    }, "ok")
                    assert michigan["series"] == [{"year": 2050, "value": 1565187.79, "datatype": "projection"}]
                    assert michigan["source"]["vintage"] == "2024"
                    assert michigan["source"]["base_year"] is None
                    indiana = await call("get_forecast", {
                        "state": "IN", "geo_level": "county", "geo": "Hamilton", "variable": "population",
                        "start_year": 2050, "end_year": 2050,
                    }, "ok")
                    assert indiana["series"] == [{"year": 2050, "value": 529505, "datatype": "projection"}]
                    assert indiana["source"]["base_year"] == 2023
                    va = await call("get_forecast", {
                        "state": "VA", "geo_level": "state", "geo": "VA", "variable": "population",
                        "start_year": 2030, "end_year": 2030,
                    }, "ok")
                    assert va["series"][0]["value"] == 9060432.76370604
                    wi = await call("get_forecast", {
                        "state": "WI", "geo_level": "state", "geo": "WI", "variable": "population",
                        "start_year": 2020, "end_year": 2020,
                    }, "ok")
                    assert wi["series"] == [{"year": 2020, "value": 5893718, "datatype": "estimate"}]
                    ut = await call("get_forecast", {
                        "state": "UT", "geo_level": "state", "geo": "UT", "variable": "population",
                        "start_year": 2025, "end_year": 2025,
                    }, "ok")
                    assert ut["scenario"] == "baseline"
                    high = await call("get_forecast", {
                        "state": "UT", "geo_level": "state", "geo": "UT", "variable": "population",
                        "scenario": "high",
                    }, "not_loaded")
                    assert high["scenario"] == "high"
                    await call("get_components", {
                        "state": "UT", "geo": "UT", "scenario": "high",
                    }, "error", True)
                    wa_status = summary["states"]["WA"]
                    assert wa_status["review"]["status"] == "never_reviewed"
                    assert wa_status["variables"]["components"]["county"]["load_status"] == "loaded"
                    wa_source = await call("describe_source", {"state": "WA"})
                    assert wa_source["variables"] == wa_status["variables"]
                    assert (await call("describe_source", {"state": "CO"}))["sources_loaded"]
                    base = dict(state="CO", geo_level="county", geo="Douglas", variable="population")
                    forecast = await call("get_forecast", dict(base, start_year=2024, end_year=2025), "ok")
                    assert [p["datatype"] for p in forecast["series"]] == ["estimate", "projection"]
                    assert forecast["source"]["retrieved_at"]
                    components = dict(state="CO", geo="Douglas")
                    assert (await call("get_components", dict(components, start_year=2024, end_year=2024), "ok"))["series"][0]["births"] == 3960
                    for name, args in [("get_forecast", base), ("get_components", components)]:
                        empty = await call(name, dict(args, start_year=2100, end_year=2110), "empty_range")
                        assert empty["available_end_year"] == 2060
                        await call(name, dict(args, start_year=2050, end_year=2020), "error", True)
                        await call(name, dict(args, geo="Sprongfield"), "error", True)
                        await call(name, dict(args, state="ZZ"), "error", True)
                        await call(name, dict(args, scenario="high"), "error", True)
                    await call("get_forecast", dict(base, geo_level="countyy"), "error", True)
                    await call("get_forecast", dict(base, variable="births"), "error", True)
                    await call("get_forecast", dict(base, geo_level="place"), "not_published")
                    await call("get_forecast", dict(base, geo_level="cog"), "coverage_unknown")
                    await call("get_forecast", dict(base, state="TX", geo="Harris", variable="households"), "not_published")
                    wa = await call("get_components", dict(state="WA", geo="King", start_year=2025, end_year=2025), "ok")
                    assert wa["series"][0]["births"] == 113170
                    assert wa["series"][0]["period_start_year"] == 2020
                    assert wa["source"]["base_year"] == 2020
                    statewide = await call("get_components", dict(state="WA", geo="WA", start_year=2026, end_year=2026), "ok")
                    assert statewide["series"][0]["births"] == 81966
                    assert statewide["series"][0]["datatype"] == "projection"
                    await call("get_components", dict(state="WA", geo="King", scenario="high"), "error", True)
                    await call("describe_source", {"state": "ZZ"}, "error", True)
                    ambiguous = await call("get_forecast", dict(base, geo="ar"), "error", True)
                    assert len(ambiguous["candidates"]) > 1
                    for args in ({}, dict(base, start_year="not a year")):
                        assert (await client.call_tool("get_forecast", args)).is_error
                    with pytest.raises(MCPError) as exc:
                        await client.call_tool("unknown_tool", {})
                    assert exc.value.code == INVALID_PARAMS

    anyio.run(check)


@pytest.mark.parametrize("broken", [False, True])
def test_database_failures_are_tool_errors_without_paths(installed_server, tmp_path, broken):
    python, folder = installed_server
    database = tmp_path / "private-database.sqlite"
    if broken:
        database.write_text("not a database")

    async def check():
        params = StdioServerParameters(command=str(python), args=["-m", "sdo_mcp.server"],
                                      cwd=str(folder), env={"SDO_DB": str(database)})
        with anyio.fail_after(30):
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as client:
                    await client.discover()
                    result = await client.call_tool("list_states", {})
                    assert result.is_error
                    text = result.content[0].text
                    assert str(tmp_path) not in text
                    if not broken:
                        assert "Reinstall a released sdo-mcp package" in text

    anyio.run(check)


def test_serving_connection_cannot_write(db_path):
    conn = store.connect(db_path)
    try:
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            conn.execute("CREATE TABLE should_never_exist (value TEXT)")
    finally:
        conn.close()


def test_gap_between_decade_observations_is_empty_range():
    result = server.get_forecast("TX", "cog", "18", "population", 2031, 2039)
    assert result["status"] == "empty_range"
    assert result["available_start_year"] <= 2030
    assert result["available_end_year"] >= 2040
