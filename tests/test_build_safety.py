import json
import shutil
from types import SimpleNamespace

import pytest

from sdo_mcp.common import fetch
from sdo_mcp.ingest import build


def test_snapshot_conflict_preserves_bytes_and_retrieval(tmp_path):
    entry = fetch.snapshot_json(tmp_path, 'sample.json', [1], 'source')
    entry['retrieved_at'] = '2020-01-01'
    fetch.write_manifest(tmp_path, [entry])
    assert fetch.snapshot_json(tmp_path, 'sample.json', [1], 'source') == entry
    fetch.write_manifest(tmp_path, [{**entry, 'retrieved_at': '2026-09-05'}])
    assert fetch.read_manifest(tmp_path) == [entry]
    with pytest.raises(ValueError, match='snapshot differs'):
        fetch.snapshot_json(tmp_path, 'sample.json', [2], 'source')
    assert json.loads((tmp_path / 'sample.json').read_text()) == [1]


def test_changed_fingerprint_keeps_database(tmp_path, db_path, monkeypatch):
    raw = tmp_path / 'raw'
    shutil.copytree(build.store.REPO_ROOT / 'data/raw', raw)
    (raw / 'census_national_county2020.txt').write_text('changed')
    destination = tmp_path / 'working.sqlite'
    destination.write_bytes(b'previous database')
    original = build.verify_inputs
    monkeypatch.setattr(build, 'verify_inputs', lambda: original(raw))
    with pytest.raises(ValueError, match='fingerprint mismatch'):
        build.rebuild(destination)
    assert destination.read_bytes() == b'previous database'


def test_failed_state_load_keeps_database(tmp_path, monkeypatch):
    destination = tmp_path / 'working.sqlite'
    destination.write_bytes(b'previous database')
    def fail(conn):
        conn.execute("DELETE FROM coverage")
        conn.commit()
        raise RuntimeError('state failed')
    monkeypatch.setattr(build, 'ADAPTERS', [SimpleNamespace(load=fail)])
    with pytest.raises(RuntimeError, match='state failed'):
        build.rebuild(destination)
    assert destination.read_bytes() == b'previous database'
    assert list(tmp_path.iterdir()) == [destination]


def test_successful_replacement_retains_previous(tmp_path, db_path, monkeypatch):
    destination = tmp_path / 'working.sqlite'
    destination.write_bytes(b'previous database')
    monkeypatch.setattr(build.store, 'init_db', lambda conn: None)
    def copy_data(conn):
        import sqlite3
        with sqlite3.connect(db_path) as source:
            source.backup(conn)
    monkeypatch.setattr(build.seed, 'load', copy_data)
    monkeypatch.setattr(build, 'ADAPTERS', [])
    build.rebuild(destination)
    assert build.validate_database(destination) == destination
    backups = list(tmp_path.glob('working.sqlite.previous-*'))
    assert len(backups) == 1
    assert backups[0].read_bytes() == b'previous database'
