"""Copy the served rows of a full build into the package before ``uv build``.

The full research database keeps age, sex and race detail that no tool serves.
This writes a compact copy with every served observation and every source,
geography and coverage record, then checks both directions against the full
build. The wheel ships that copy, so installing the package installs the data.

Usage::

    uv run python -m sdo_mcp.bundle [data/sdo.sqlite]
    uv build --wheel
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import tempfile
import tomllib
from datetime import datetime, timezone
from pathlib import Path

from . import store
from .validate import validate_database

TOTALS = "age_group='all' AND sex='all' AND race='all'"


def package_version() -> str:
    """Read the version being built, not the version of an older install."""
    pyproject = tomllib.loads((store.REPO_ROOT / 'pyproject.toml').read_text())
    return pyproject['project']['version']


def bundle_database(source: Path | str = store.REPOSITORY_DB,
                    output: Path | str = store.BUNDLED_DB,
                    version: str | None = None) -> Path:
    """Write the compact copy; the full build is opened read-only and never changed."""
    source = validate_database(source)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=output.parent, prefix=f'.{output.name}.',
                                     delete=False) as f:
        temporary = Path(f.name)
    try:
        original = sqlite3.connect(f'{source.resolve().as_uri()}?mode=ro', uri=True)
        compact = sqlite3.connect(temporary)
        try:
            original.backup(compact)
            compact.execute(f'DELETE FROM observations WHERE NOT ({TOTALS})')
            compact.commit()
            compact.execute('VACUUM')
            # Compare both directions, including all source and lookup fields.
            compact.execute('ATTACH DATABASE ? AS full', (f'{source.resolve().as_uri()}?mode=ro',))
            for table in ('observations', 'sources', 'coverage', 'geographies'):
                where = f' WHERE {TOTALS}' if table == 'observations' else ''
                a = f'SELECT * FROM main.{table}'
                b = f'SELECT * FROM full.{table}{where}'
                for left, right in ((a, b), (b, a)):
                    if compact.execute(f'{left} EXCEPT {right} LIMIT 1').fetchone():
                        raise ValueError(f'bundled copy differs from full database: {table}')
            compact.execute('DETACH DATABASE full')
            counts = {t: compact.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
                      for t in ('observations', 'sources', 'coverage', 'geographies')}
            metadata = {'release_version': version or package_version(),
                        'created_at': datetime.now(timezone.utc).isoformat(),
                        'kind': 'served-totals', 'counts': counts}
            compact.execute('CREATE TABLE IF NOT EXISTS release_metadata (metadata TEXT NOT NULL)')
            compact.execute('DELETE FROM release_metadata')
            compact.execute('INSERT INTO release_metadata VALUES (?)', (json.dumps(metadata),))
            compact.commit()
        finally:
            compact.close()
            original.close()
        validate_database(temporary)
        # Temporary files are private; the shipped copy must be readable by all.
        os.chmod(temporary, 0o644)
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('source', type=Path, nargs='?', default=store.REPOSITORY_DB)
    args = parser.parse_args()
    print(f'bundled {bundle_database(args.source)}')


if __name__ == '__main__':
    main()
