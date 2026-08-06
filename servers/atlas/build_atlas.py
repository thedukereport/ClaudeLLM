#!/usr/bin/env python3
"""
Build atlas.duckdb — a local-first historical geo-temporal database.

Backbone: DuckDB + spatial extension (single file, no server). Schema follows
the Linked Places Format (LPF) idea: a place carries names, types, geometry, and
relations, each of which can be *temporally scoped* with a valid-time range.
Years are integers, negative = BCE (so -750 = 750 BCE), matching Pleiades.

Two temporal shapes are supported:
  • static places that change over time  (names/borders valid for a date range)
  • trajectories                          (ordered, time-stamped waypoints)

This script creates the schema and seeds it from the existing Pleiades gazetteer
(pleiades.sqlite, ~42k ancient places). Re-runnable: drops & rebuilds.

  python3 build_atlas.py
Requires: duckdb (pip). Spatial extension auto-installs on first run (needs net
once, then cached under ~/.duckdb/).
"""
import sys
from pathlib import Path
import duckdb

HERE = Path(__file__).resolve().parent
DB = HERE / "atlas.duckdb"
import os
PLEIADES = os.environ.get("PLEIADES_DB", "/Volumes/PRO-BLADE/Pleiades/pleiades.sqlite")

# Pleiades controlled-vocabulary period codes (approximate spans, refine w/ PeriodO)
PLEIADES_PERIODS = [
    ("A", "Archaic",                -750,  -550),
    ("C", "Classical",              -550,  -330),
    ("H", "Hellenistic/Republican", -330,   -30),
    ("R", "Roman",                   -30,   300),
    ("L", "Late Antique",            300,   640),
    ("M", "Medieval",                640,  1500),
    ("S", "(Pleiades code S)",      None,  None),
    ("F", "(Pleiades code F)",      None,  None),
]


def main():
    if DB.exists():
        DB.unlink()
    con = duckdb.connect(str(DB))
    con.execute("INSTALL spatial; LOAD spatial;")
    con.execute("INSTALL sqlite; LOAD sqlite;")

    # ── schema (LPF-inspired, valid-time on the temporally-scoped tables) ──
    con.execute("""
    CREATE TABLE places (
        place_id     BIGINT PRIMARY KEY,
        source       VARCHAR,          -- 'pleiades', 'whg', ...
        source_id    VARCHAR,          -- id within that source
        title        VARCHAR,          -- canonical/display name
        ccodes       VARCHAR,          -- modern country codes (LPF), optional
        feature_types VARCHAR,         -- 'settlement, port'
        period_codes VARCHAR,          -- source period vocabulary (e.g. 'ACHRL')
        valid_from   INTEGER,          -- year, negative = BCE
        valid_to     INTEGER,
        lat          DOUBLE,
        lng          DOUBLE,
        geom         GEOMETRY,         -- point (or later, polygon)
        uri          VARCHAR,
        description  VARCHAR
    );
    CREATE TABLE place_names (          -- names can change over time (LPF names*)
        place_id   BIGINT,
        name       VARCHAR,
        lang       VARCHAR,
        valid_from INTEGER,
        valid_to   INTEGER
    );
    CREATE TABLE periods (              -- period vocab (Pleiades now, PeriodO later)
        code   VARCHAR,
        label  VARCHAR,
        region VARCHAR,
        start_year INTEGER,
        end_year   INTEGER
    );
    CREATE TABLE relations (            -- LPF relations* (part-of, near, etc.)
        place_id   BIGINT,
        rel_type   VARCHAR,
        target_id  BIGINT,
        valid_from INTEGER,
        valid_to   INTEGER
    );
    CREATE TABLE trajectories (         -- a movement/route (army, voyage, migration)
        traj_id  BIGINT PRIMARY KEY,
        title    VARCHAR,
        category VARCHAR,
        source   VARCHAR,
        notes    VARCHAR
    );
    CREATE TABLE waypoints (            -- ordered, time-stamped points of a trajectory
        traj_id  BIGINT,
        seq      INTEGER,
        place_id BIGINT,               -- optional link to a place
        label    VARCHAR,
        t_year   INTEGER,              -- when the object was here (negative = BCE)
        lat      DOUBLE,
        lng      DOUBLE,
        geom     GEOMETRY
    );
    """)

    con.executemany(
        "INSERT INTO periods(code,label,region,start_year,end_year) "
        "VALUES(?,?,?,?,?)",
        [(c, l, "Mediterranean (Pleiades)", s, e) for c, l, s, e in PLEIADES_PERIODS])

    # ── seed from Pleiades via the sqlite scanner ──
    con.execute(f"ATTACH '{PLEIADES}' AS ple (TYPE sqlite);")
    con.execute("""
        INSERT INTO places
        SELECT
            CAST(pid AS BIGINT)                                   AS place_id,
            'pleiades'                                            AS source,
            CAST(pid AS VARCHAR)                                  AS source_id,
            title,
            NULL                                                  AS ccodes,
            feature_types,
            time_periods                                          AS period_codes,
            TRY_CAST(split_part(time_range, ',', 1) AS DOUBLE)::INTEGER AS valid_from,
            TRY_CAST(split_part(time_range, ',', 2) AS DOUBLE)::INTEGER AS valid_to,
            lat, lng,
            CASE WHEN lat IS NOT NULL AND lng IS NOT NULL
                 THEN ST_Point(lng, lat) END                      AS geom,
            uri,
            description
        FROM ple.places;
    """)
    con.execute("DETACH ple;")

    # spatial index (RTREE) on located places' geometry
    con.execute("CREATE INDEX idx_places_geom ON places USING RTREE (geom);")
    con.execute("CREATE INDEX idx_places_time ON places (valid_from, valid_to);")

    total = con.execute("SELECT COUNT(*) FROM places").fetchone()[0]
    located = con.execute("SELECT COUNT(*) FROM places WHERE geom IS NOT NULL").fetchone()[0]
    span = con.execute("SELECT MIN(valid_from), MAX(valid_to) FROM places").fetchone()
    print(f"atlas.duckdb built:")
    print(f"  places:  {total:,}  ({located:,} located)")
    print(f"  periods: {con.execute('SELECT COUNT(*) FROM periods').fetchone()[0]}")
    print(f"  time span: {span[0]} .. {span[1]} (negative = BCE)")
    print(f"  -> {DB}")
    con.close()


if __name__ == "__main__":
    main()
