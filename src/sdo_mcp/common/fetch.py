"""Validated fetch + snapshot helpers (ingest side only).

Government endpoints lie with HTTP 200: many SDO backends return errors as
200 OK with an HTML or plain-text body, and content-type headers are wrong
(DOLA serves JSON as text/html). The only reliable check is parsing the body.
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.request
from datetime import date
from pathlib import Path

# CA's DOF 403s anonymous fetchers; identify ourselves everywhere.
UA = {"User-Agent": "sdo-mcp ingest (chenliang.aiesecnku@gmail.com)"}


def get_json(url: str, tries: int = 3, timeout: int = 120):
    """GET a URL and require the body to parse as JSON.

    Status codes and content-type headers are never trusted — a plain-text
    error in a 200 body fails json parsing, which is the guard.
    """
    last: Exception | None = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = r.read().decode("utf-8", "replace")
            if not body.lstrip().startswith(("[", "{")):
                raise ValueError(f"non-JSON response body: {body[:120]!r}")
            return json.loads(body)
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(0.8 * (i + 1))
    raise RuntimeError(f"GET {url} failed after {tries} tries: {last}")


def post_json(url: str, form: dict, tries: int = 3, timeout: int = 300):
    """POST form data and require the body to parse as JSON (same guard as
    get_json). Needed for ArcGIS /query layers where GET stalls on long
    query strings (TN's alldata table)."""
    import urllib.parse

    data = urllib.parse.urlencode(form).encode()
    last: Exception | None = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, data=data, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = r.read().decode("utf-8", "replace")
            if not body.lstrip().startswith(("[", "{")):
                raise ValueError(f"non-JSON response body: {body[:120]!r}")
            return json.loads(body)
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(0.8 * (i + 1))
    raise RuntimeError(f"POST {url} failed after {tries} tries: {last}")


def get_bytes(url: str, tries: int = 3, timeout: int = 300) -> bytes:
    last: Exception | None = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(0.8 * (i + 1))
    raise RuntimeError(f"GET {url} failed after {tries} tries: {last}")


def get_with_js(url: str, tries: int = 3, timeout: int = 300) -> bytes:
    """GET through a browser-like client for sites guarded by a JavaScript
    challenge, while still rejecting challenge/error pages as data.

    Arizona OEO's downloads are the current use case. ``cloudscraper`` is an
    ingest-only dependency; nothing on the MCP serve path imports it.
    """
    import cloudscraper

    last: Exception | None = None
    for i in range(tries):
        try:
            scraper = cloudscraper.create_scraper()
            response = scraper.get(url, headers=UA, timeout=timeout)
            response.raise_for_status()
            body = response.content
            beginning = body[:500].lower()
            if b"<html" in beginning or b"just a moment" in beginning:
                raise ValueError("received an HTML challenge/error page instead of data")
            return body
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(0.8 * (i + 1))
    raise RuntimeError(f"challenge-capable GET {url} failed after {tries} tries: {last}")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def snapshot_json(raw_dir: Path, name: str, data, source: str, note: str = "") -> dict:
    """Write `data` as a snapshot file in data/raw/<...> and return its manifest
    entry (recorded vintage/retrieval metadata is a domain rule, not a nicety)."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_dir / name
    body = json.dumps(data, indent=1).encode()
    path.write_bytes(body)
    return {
        "file": name,
        "source": source,
        "retrieved_at": date.today().isoformat(),
        "sha256": sha256(body),
        "records": len(data) if isinstance(data, list) else None,
        "note": note,
    }


def write_manifest(raw_dir: Path, entries: list[dict]) -> None:
    (raw_dir / "manifest.json").write_text(json.dumps(entries, indent=1) + "\n")


def read_manifest(raw_dir: Path) -> list[dict]:
    return json.loads((raw_dir / "manifest.json").read_text())
