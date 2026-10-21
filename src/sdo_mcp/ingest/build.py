"""Rebuild data/sdo.sqlite from the committed snapshots in data/raw/.

The database is a built artifact: if it's ever wrong, fix the ingest and
rebuild — never patch it by hand.

Usage: uv run python -m sdo_mcp.ingest.build [db_path]

With no path, this rebuilds the repository artifact at ``data/sdo.sqlite``.
The packaged server reads a compact copy made by ``python -m sdo_mcp.bundle``;
pass an explicit path when a build should go somewhere else.
"""

from __future__ import annotations

import sys
import json
import os
import shutil
import tempfile
from uuid import uuid4
from importlib import import_module
from pathlib import Path

from .. import store
from ..common import fetch
from ..validate import validate_database
from . import (
    ak, al, az, ca, co, ct, de, fl, ga, hi, id, il, ks, ky, ma, md, me, mi,
    mn, mo, ms, nc, nd, ne, nh, nj, nm, nv, ny, oh, pa, ri, sc, sd, seed,
    tn, tx, ut, va, wa, wi, wy,
    ia, wv,
    ar, la,
    ok, vt,
)

# Oregon and Indiana have postal codes that are reserved Python words.
or_adapter = import_module(".or", __package__)
in_adapter = import_module(".in", __package__)

# State adapter modules, each exposing load(conn) and verify(conn).
# Registered in build order (plan/DESIGN.md §5, then plan/EXPANSION.md).
ADAPTERS: list = [
    co, tn, ga, ca, tx, fl, nc, mn, az, wa, or_adapter, va, wi, ut,
    in_adapter, ky, mi, pa, il, md, de, nm, sc, al, wy,
    ak, hi, me, ne, nh, nv, oh,
    ct, ri, ma, ny, nj,
    id, ks, mo, ms, nd, sd,
    ia, wv,
    ar, la,
    ok, vt,
]


def verify_inputs(raw_dir: Path | None = None) -> dict[str, str]:
    """Check every registered build input, including files without state manifests."""
    raw_dir = raw_dir or store.REPO_ROOT / "data" / "raw"
    required = json.loads(Path(__file__).with_name("inputs.json").read_text())
    directories = {Path(name).parent for name in required}
    recorded = {}
    for directory in sorted(directories):
        for entry in fetch.read_manifest(raw_dir / directory):
            name = (directory / entry["file"]).as_posix()
            recorded[name] = entry["sha256"]
    missing = set(required) - recorded.keys()
    if missing:
        raise ValueError(f"build inputs missing fingerprints: {sorted(missing)}")
    return {name: recorded[name] for name in required}


def rebuild(path: Path | str | None = None) -> Path:
    p = Path(path) if path else store.REPOSITORY_DB
    fingerprints = verify_inputs()
    p.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=p.parent, prefix=f".{p.name}.", delete=False) as f:
        temporary = Path(f.name)
    try:
        conn = store.connect(temporary, create=True)
        try:
            store.init_db(conn)
            seed.load(conn)
            for adapter in ADAPTERS:
                adapter.load(conn)
                adapter.verify(conn)
            conn.commit()
        finally:
            conn.close()
        validate_database(temporary)
        if verify_inputs() != fingerprints:
            raise ValueError("source fingerprints changed during the build")
        with temporary.open("rb") as f:
            os.fsync(f.fileno())
        if p.exists():
            # Unique recovery copies are never overwritten by a later rebuild.
            backup = p.with_name(f"{p.name}.previous-{uuid4().hex}")
            try:
                shutil.copy2(p, backup)
                with backup.open("rb") as f:
                    os.fsync(f.fileno())
            except BaseException:
                backup.unlink(missing_ok=True)
                raise
        os.replace(temporary, p)
    finally:
        temporary.unlink(missing_ok=True)
    return p


if __name__ == "__main__":
    built = rebuild(sys.argv[1] if len(sys.argv) > 1 else None)
    print(f"built {built}")
