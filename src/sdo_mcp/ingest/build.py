"""Rebuild data/sdo.sqlite from the committed snapshots in data/raw/.

The database is a built artifact: if it's ever wrong, fix the ingest and
rebuild — never patch it by hand.

Usage: uv run python -m sdo_mcp.ingest.build [db_path]
"""

from __future__ import annotations

import sys
from pathlib import Path

from .. import store
from . import co, seed

# State adapter modules, each exposing load(conn) and verify(conn).
# Registered in build order (plan/DESIGN.md): CO -> TN -> GA -> CA -> TX -> FL.
ADAPTERS: list = [co]


def rebuild(path: Path | str | None = None) -> Path:
    p = Path(path) if path else store.db_path()
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
