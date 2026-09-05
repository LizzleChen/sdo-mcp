"""Rebuild data/sdo.sqlite from the committed snapshots in data/raw/.

The database is a built artifact: if it's ever wrong, fix the ingest and
rebuild — never patch it by hand.

Usage: uv run python -m sdo_mcp.ingest.build [db_path]

With no path, this rebuilds the repository artifact at ``data/sdo.sqlite``.
The installed server uses a separate per-user database path; pass an explicit
path when a build should go somewhere else.
"""

from __future__ import annotations

import sys
from importlib import import_module
from pathlib import Path

from .. import store
from . import az, ca, co, fl, ga, mn, nc, seed, tn, tx, wa

# ``or`` is Oregon's postal code but a reserved Python word, so this one
# state-code module must be imported by name rather than in the statement above.
or_adapter = import_module(".or", __package__)

# State adapter modules, each exposing load(conn) and verify(conn).
# Registered in build order (plan/DESIGN.md §5, then plan/EXPANSION.md).
ADAPTERS: list = [co, tn, ga, ca, tx, fl, nc, mn, az, wa, or_adapter]


def rebuild(path: Path | str | None = None) -> Path:
    # Keep source-repository rebuilds separate from the installed serving copy.
    # In particular, SDO_DB is a serving override and must not silently point a
    # destructive rebuild at a user's installed database.
    p = Path(path) if path else store.REPOSITORY_DB
    if p.exists():
        p.unlink()
    conn = store.connect(p, create=True)
    try:
        store.init_db(conn)
        seed.load(conn)
        for adapter in ADAPTERS:
            adapter.load(conn)
            adapter.verify(conn)
        conn.commit()
    finally:
        conn.close()
    return p


if __name__ == "__main__":
    built = rebuild(sys.argv[1] if len(sys.argv) > 1 else None)
    print(f"built {built}")
