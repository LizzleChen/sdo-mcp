-- SDO Forecast MCP — common schema (see plan/DESIGN.md §2).
-- Long format: one row of `observations` holds exactly one number; every other
-- column on the row says what that number is.

-- Where numbers came from: one row per state × product × vintage.
CREATE TABLE sources (
    source_id    TEXT PRIMARY KEY,          -- readable, e.g. 'co-pop-2024'
    state        TEXT NOT NULL,             -- 2-letter code
    agency       TEXT NOT NULL,
    product_name TEXT NOT NULL,
    vintage      TEXT NOT NULL,
    base_year    INTEGER,                   -- last estimate year; forecast starts after
    horizon_year INTEGER,
    source_url   TEXT,
    retrieved_at TEXT,                      -- ISO date; matters because several states
                                           -- overwrite or delete files in place
    license      TEXT,
    citation     TEXT,
    method_notes TEXT
);

-- The numbers.
CREATE TABLE observations (
    state     TEXT NOT NULL,
    geo_level TEXT NOT NULL,               -- state / county / county_subdivision / msa / cog / ...
    geo_id    TEXT NOT NULL,               -- FIPS ('08', '08035'); non-FIPS levels use the
                                           -- source's own id prefixed (e.g. 'tx-cog-1')
    year      INTEGER NOT NULL,
    variable  TEXT NOT NULL,               -- population / households / employment /
                                           -- births / deaths / net_migration / labor_force
    value     REAL NOT NULL,
    datatype  TEXT NOT NULL CHECK (datatype IN ('estimate', 'projection')),
    scenario  TEXT NOT NULL DEFAULT '',    -- '' = the only series there is (served as null);
                                           -- stored non-NULL so the primary key can enforce
                                           -- uniqueness (NULLs never compare equal in SQLite)
    age_group TEXT NOT NULL DEFAULT 'all', -- detail dimensions live in the schema from day
    sex       TEXT NOT NULL DEFAULT 'all', -- one; v1 tools serve totals ('all') only
    race      TEXT NOT NULL DEFAULT 'all', -- race labels are per-state, never remapped
    source_id TEXT NOT NULL REFERENCES sources(source_id),
    PRIMARY KEY (state, geo_level, geo_id, year, variable, scenario, age_group, sex, race)
) WITHOUT ROWID;

CREATE INDEX idx_obs_query
    ON observations (state, geo_level, geo_id, variable, year);

-- FIPS <-> name join (GA and FL publish names only, no FIPS).
CREATE TABLE geographies (
    geo_id    TEXT NOT NULL,
    geo_level TEXT NOT NULL,
    state     TEXT NOT NULL,
    name      TEXT NOT NULL,               -- Census spelling
    PRIMARY KEY (state, geo_level, geo_id)
);

CREATE INDEX idx_geo_name ON geographies (state, geo_level, name);

-- What each state does and does NOT publish. This table is what makes
-- "not published" answers structural: refusals are looked up here, the data
-- table is never consulted, so there is nothing to accidentally extrapolate.
CREATE TABLE coverage (
    state     TEXT NOT NULL,
    variable  TEXT NOT NULL,
    geo_level TEXT NOT NULL,
    status    TEXT NOT NULL CHECK (status IN
              ('available', 'not_published', 'state_level_only', 'pdf_only')),
    detail    TEXT,
    PRIMARY KEY (state, variable, geo_level)
);
