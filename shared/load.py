"""
Shared load logic. Writes a transformed row into a PostgreSQL table.

This module requires `psycopg2-binary` — it is intentionally the only
module in shared/ with an external dependency, since loading is always
target-specific (unlike ingest and transform which are pure stdlib).
"""

import os
from typing import Any

import psycopg2  # type: ignore[import-untyped]

WAREHOUSE_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS weather_observations (
    id               SERIAL PRIMARY KEY,
    ingested_at      TIMESTAMP NOT NULL,
    latitude         DOUBLE PRECISION,
    longitude        DOUBLE PRECISION,
    temperature_c    DOUBLE PRECISION,
    wind_speed_kmh   DOUBLE PRECISION,
    humidity_pct     DOUBLE PRECISION
);
"""

INSERT_SQL = """
INSERT INTO weather_observations
    (ingested_at, latitude, longitude, temperature_c, wind_speed_kmh, humidity_pct)
VALUES
    (%(ingested_at)s, %(latitude)s, %(longitude)s,
     %(temperature_c)s, %(wind_speed_kmh)s, %(humidity_pct)s)
RETURNING id;
"""


def get_connection(
    host: str | None = None,
    port: str | None = None,
    dbname: str | None = None,
    user: str | None = None,
    password: str | None = None,
):
    """Return a psycopg2 connection, reading defaults from env vars."""
    return psycopg2.connect(
        host=host or os.environ.get("POSTGRES_HOST", "airflow-postgresql"),
        port=port or os.environ.get("POSTGRES_PORT", "5432"),
        dbname=dbname or os.environ.get("POSTGRES_DB", "postgres"),
        user=user or os.environ.get("POSTGRES_USER", "postgres"),
        password=password or os.environ.get("POSTGRES_PASSWORD", "postgres"),
    )


def ensure_table(conn) -> None:
    """Create the weather_observations table if it doesn't exist."""
    with conn.cursor() as cur:
        cur.execute(WAREHOUSE_TABLE_DDL)
    conn.commit()


def load_row(row: dict[str, Any], conn=None) -> int:
    """Insert one transformed row and return the new row id."""
    own_conn = conn is None
    if own_conn:
        conn = get_connection()
    try:
        ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute(INSERT_SQL, row)
            row_id = cur.fetchone()[0]
        conn.commit()
        return row_id
    finally:
        if own_conn:
            conn.close()


if __name__ == "__main__":
    # Quick local test
    sample = {
        "ingested_at": "2026-06-18T12:00:00+00:00",
        "latitude": 48.86,
        "longitude": 2.36,
        "temperature_c": 25.0,
        "wind_speed_kmh": 12.0,
        "humidity_pct": 55,
    }
    row_id = load_row(sample)
    print(f"Inserted row id={row_id}")
