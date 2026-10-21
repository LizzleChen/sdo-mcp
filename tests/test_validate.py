import sqlite3

import pytest

from sdo_mcp import store, validate


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


def test_default_is_bundled_and_override_is_explicit(monkeypatch, tmp_path):
    monkeypatch.delenv("SDO_DB", raising=False)
    assert store.db_path() == store.BUNDLED_DB

    override = tmp_path / "chosen.sqlite"
    monkeypatch.setenv("SDO_DB", str(override))
    assert store.db_path() == override


def test_validate_database_checks_schema_columns(tmp_path):
    path = tmp_path / "valid.sqlite"
    _usable_database(path)
    assert validate.validate_database(path) == path

    broken = tmp_path / "broken.sqlite"
    conn = sqlite3.connect(broken)
    conn.execute("CREATE TABLE observations (state TEXT)")
    conn.commit()
    conn.close()
    with pytest.raises(validate.DatabaseValidationError, match="required table"):
        validate.validate_database(broken)


def test_validate_database_rejects_empty_schema(tmp_path):
    path = tmp_path / "empty.sqlite"
    _empty_database(path)
    with pytest.raises(validate.DatabaseValidationError, match="no serviceable forecast data"):
        validate.validate_database(path)


@pytest.mark.parametrize("variable", ["population", "households", "employment"])
def test_validate_database_rejects_mixed_sources_within_forecast_series(tmp_path, variable):
    path = tmp_path / "mixed.sqlite"
    _usable_database(path)
    with sqlite3.connect(path) as conn:
        conn.execute("UPDATE observations SET variable=?", (variable,))
        conn.execute("UPDATE coverage SET variable=?", (variable,))
        conn.execute(
            "INSERT INTO sources (source_id, state, agency, product_name, vintage) "
            "VALUES ('other', 'CO', 'Test', 'Test', '2027')"
        )
        conn.execute(
            "INSERT INTO observations (state, geo_level, geo_id, year, variable, value, datatype, source_id) "
            "VALUES ('CO', 'state', '08', 2027, ?, 2, 'projection', 'other')", (variable,)
        )
    with pytest.raises(validate.DatabaseValidationError, match="mixes sources within one forecast series"):
        validate.validate_database(path)

    # Separate scenario products may legitimately have different sources.
    with sqlite3.connect(path) as conn:
        conn.execute("UPDATE observations SET scenario='high' WHERE source_id='other'")
    assert validate.validate_database(path) == path


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
    with pytest.raises(validate.DatabaseValidationError, match="no serviceable forecast data"):
        validate.validate_database(path)
