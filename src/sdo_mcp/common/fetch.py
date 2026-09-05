"""Validated fetch + snapshot helpers (ingest side only).

Government endpoints lie with HTTP 200: many SDO backends return errors as
200 OK with an HTML or plain-text body, and content-type headers are wrong
(DOLA serves JSON as text/html). The only reliable check is parsing the body.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
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


def write_snapshot(path: Path, body: bytes) -> None:
    """Publish a complete new file; existing bytes may never be replaced."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as output:
        temporary = Path(output.name)
        try:
            output.write(body)
            output.flush()
            os.fsync(output.fileno())
        except BaseException:
            temporary.unlink()
            raise
    try:
        try:
            os.link(temporary, path)
        except FileExistsError:
            if path.read_bytes() != body:
                raise ValueError(f"{path}: snapshot differs; use a new edition filename")
    finally:
        temporary.unlink()


def snapshot_json(raw_dir: Path, name: str, data, source: str, note: str = "") -> dict:
    """Write `data` as a snapshot file in data/raw/<...> and return its manifest
    entry (recorded vintage/retrieval metadata is a domain rule, not a nicety)."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_dir / name
    body = json.dumps(data, indent=1).encode()
    write_snapshot(path, body)
    entry = {
        "file": name,
        "source": source,
        "retrieved_at": date.today().isoformat(),
        "sha256": sha256(body),
        "records": len(data) if isinstance(data, list) else None,
        "note": note,
    }
    if (raw_dir / "manifest.json").exists():
        previous = next((e for e in read_manifest(raw_dir) if e["file"] == name), None)
        if previous is not None:
            return previous
    return entry


def write_manifest(raw_dir: Path, entries: list[dict]) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_dir / "manifest.json"
    previous = read_manifest(raw_dir) if path.exists() else []
    merged = {entry["file"]: entry for entry in previous}
    for entry in entries:
        source = raw_dir / entry["file"]
        if sha256(source.read_bytes()) != entry["sha256"]:
            raise ValueError(f"{source}: fingerprint mismatch")
        old = merged.get(entry["file"])
        if old is not None:
            if old["sha256"] != entry["sha256"]:
                raise ValueError(f"{source}: existing manifest fingerprint differs")
            # Reusing an existing file is not a new retrieval.
            continue
        merged[entry["file"]] = entry
    if list(merged.values()) == previous:
        return
    with tempfile.NamedTemporaryFile(dir=raw_dir, delete=False) as output:
        temporary = Path(output.name)
        output.write((json.dumps(list(merged.values()), indent=1) + "\n").encode())
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def read_manifest(raw_dir: Path) -> list[dict]:
    entries = json.loads((raw_dir / "manifest.json").read_text())
    for entry in entries:
        path = raw_dir / entry["file"]
        if sha256(path.read_bytes()) != entry["sha256"]:
            raise ValueError(f"{path}: fingerprint mismatch")
    return entries
