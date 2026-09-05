"""Prepare an immutable, compressed database release from a full build."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import shutil
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .install import validate_database

TOTALS = "age_group='all' AND sex='all' AND race='all'"


def file_sha256(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def prepare_release(source: Path | str, output: Path | str, version: str) -> Path:
    """Keep all served rows and lookup/source records; never modify the full build."""
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,79}', version):
        raise ValueError('release version must use letters, numbers, dots, underscores or hyphens')
    source = validate_database(source)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    destination = output / version
    if destination.exists():
        raise FileExistsError(f'release already exists: {destination}')
    with tempfile.TemporaryDirectory(dir=output, prefix='.release-') as folder:
        stage = Path(folder)
        database = stage / 'sdo.sqlite'
        original = sqlite3.connect(f'{source.resolve().as_uri()}?mode=ro', uri=True)
        compact = sqlite3.connect(database)
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
                        raise ValueError(f'release differs from full database: {table}')
            counts = {t: compact.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
                      for t in ('observations', 'sources', 'coverage', 'geographies')}
            metadata = {'release_version': version, 'created_at': datetime.now(timezone.utc).isoformat(),
                        'kind': 'served-totals', 'counts': counts,
                        'full_database_sha256': file_sha256(source)}
            compact.execute('CREATE TABLE IF NOT EXISTS release_metadata (metadata TEXT NOT NULL)')
            compact.execute('DELETE FROM release_metadata')
            compact.execute('INSERT INTO release_metadata VALUES (?)', (json.dumps(metadata),))
            compact.commit()
        finally:
            compact.close()
            original.close()
        validate_database(database)
        archive = stage / f'sdo-{version}.sqlite.gz'
        with database.open('rb') as incoming, archive.open('wb') as outgoing:
            with gzip.GzipFile(filename='', mode='wb', fileobj=outgoing, compresslevel=6, mtime=0) as zipped:
                shutil.copyfileobj(incoming, zipped)
        manifest = {**metadata, 'format_version': 1, 'file': archive.name,
                    'sha256': file_sha256(archive), 'size_bytes': archive.stat().st_size,
                    'database_sha256': file_sha256(database), 'database_size_bytes': database.stat().st_size}
        (stage / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        database.unlink()
        os.rename(stage, destination)
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--output', type=Path, default=Path('data/releases'))
    parser.add_argument('--version', required=True)
    args = parser.parse_args()
    print(prepare_release(args.source, args.output, args.version))


if __name__ == '__main__':
    main()
