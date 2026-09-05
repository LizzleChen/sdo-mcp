import sqlite3

import pytest

from sdo_mcp import install, store


def _empty_database(path):
    conn = store.connect(path, create=True)
    store.init_db(conn)
    conn.commit()
    conn.close()


def _usable_database(path):
    conn = store.connect(path, create=True)
    store.init_db(conn)
    conn.execute(
        "INSERT INTO sources (source_id, state, agency, product_name, vintage) "
        "VALUES ('test', 'CO', 'Test', 'Test', '2026')"
    )
    conn.execute(
        "INSERT INTO observations "
        "(state, geo_level, geo_id, year, variable, value, datatype, source_id) "
        "VALUES ('CO', 'state', '08', 2026, 'population', 1, 'projection', 'test')"
    )
    conn.execute(
        "INSERT INTO geographies (geo_id, geo_level, state, name) "
        "VALUES ('08', 'state', 'CO', 'Colorado')"
    )
    conn.execute(
        "INSERT INTO coverage (state, variable, geo_level, status, detail) "
        "VALUES ('CO', 'population', 'state', 'available', 'test')"
    )
    conn.commit()
    conn.close()


def test_installed_default_is_per_user_and_override_is_explicit(monkeypatch, tmp_path):
    monkeypatch.delenv("SDO_DB", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    assert store.db_path() == store.user_data_dir() / "sdo.sqlite"

    override = tmp_path / "chosen.sqlite"
    monkeypatch.setenv("SDO_DB", str(override))
    assert store.db_path() == override


def test_validate_database_checks_schema_columns(tmp_path):
    path = tmp_path / "valid.sqlite"
    _usable_database(path)
    assert install.validate_database(path) == path

    broken = tmp_path / "broken.sqlite"
    conn = sqlite3.connect(broken)
    conn.execute("CREATE TABLE observations (state TEXT)")
    conn.commit()
    conn.close()
    with pytest.raises(install.DatabaseValidationError, match="required table"):
        install.validate_database(broken)


def test_validate_database_rejects_empty_schema(tmp_path):
    path = tmp_path / "empty.sqlite"
    _empty_database(path)
    with pytest.raises(install.DatabaseValidationError, match="no serviceable forecast data"):
        install.validate_database(path)


def test_validate_database_rejects_unserved_observation(tmp_path):
    path = tmp_path / "unserved.sqlite"
    conn = store.connect(path, create=True)
    store.init_db(conn)
    conn.execute(
        "INSERT INTO sources (source_id, state, agency, product_name, vintage) "
        "VALUES ('test', 'CO', 'Test', 'Test', '2026')"
    )
    conn.execute(
        "INSERT INTO observations "
        "(state, geo_level, geo_id, year, variable, value, datatype, source_id) "
        "VALUES ('CO', 'state', '08', 2026, 'population', 1, 'projection', 'test')"
    )
    conn.commit()
    conn.close()
    with pytest.raises(install.DatabaseValidationError, match="no serviceable forecast data"):
        install.validate_database(path)


def test_install_database_preserves_destination_when_source_is_invalid(tmp_path):
    source = tmp_path / "not-a-database.sqlite"
    source.write_text("this is not sqlite")
    destination = tmp_path / "installed.sqlite"
    destination.write_text("previous working copy")

    with pytest.raises(install.DatabaseValidationError):
        install.install_database(source, destination)
    assert destination.read_text() == "previous working copy"


def test_install_database_validates_copy_and_replaces_atomically(tmp_path):
    source = tmp_path / "source.sqlite"
    destination = tmp_path / "installed.sqlite"
    _usable_database(source)
    destination.write_text("old copy")

    assert install.install_database(source, destination) == destination
    assert install.validate_database(destination) == destination
    assert destination.read_bytes() == source.read_bytes()
