"""Exercise the installed wheel through real current and older MCP connections."""

import json
import os
from pathlib import Path
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

from sdo_mcp import release, server, store


@pytest.fixture(scope="module")
def installed_server(db_path, tmp_path_factory):
    folder = tmp_path_factory.mktemp("installed-server")
    root = Path(__file__).resolve().parents[1]

    def run(*args, cwd=folder):
        return subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True, timeout=180)

    run("uv", "build", "--wheel", "--out-dir", str(folder / "dist"), cwd=root)
    run("uv", "venv", "--python", sys.executable, str(folder / "env"))
    scripts = folder / "env" / ("Scripts" if os.name == "nt" else "bin")
    python = scripts / ("python.exe" if os.name == "nt" else "python")
    wheel, = (folder / "dist").glob("*.whl")
    run("uv", "pip", "install", "--python", str(python), str(wheel))
    # Check the real compressed-release installation command outside the checkout.
    prepared = release.prepare_release(db_path, folder / "releases", "mcp-test")
    manifest = json.loads((prepared / "manifest.json").read_text())
    database = folder / "installed.sqlite"
    run(str(python), "-m", "sdo_mcp.install", str(prepared / manifest["file"]),
        "--sha256", manifest["sha256"], "--destination", str(database))
    result = run(str(python), "-c", "import sdo_mcp; print(sdo_mcp.__file__)")
    assert str(folder / "env") in result.stdout
    return python, folder, database


@pytest.mark.parametrize("protocol", ["2026-07-28", "2025-11-25"])
def test_installed_tools_over_mcp(installed_server, protocol):
    python, folder, database = installed_server

    async def check():
        params = StdioServerParameters(
            command=str(python), args=["-m", "sdo_mcp.server"],
            cwd=str(folder), env={"SDO_DB": str(database)},
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
                    assert summary["database_release"] == "mcp-test"
                    assert {"VA", "WI", "UT"} <= set(summary["states"])
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
    python, folder, _ = installed_server
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
                        assert "sdo-mcp-install-data" in text

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
