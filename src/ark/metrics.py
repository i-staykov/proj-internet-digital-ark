"""Per-run collection metrics, persisted for the report's execution notes.

Every collection command records its stats dict here after each run, so
success rates, failure counts, and net-new yields per source can be
queried instead of reconstructed from log files.
"""

import json

import duckdb

_TABLE = """
CREATE TABLE IF NOT EXISTS run_metrics (
    recorded_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    command      TEXT NOT NULL,
    source       TEXT NOT NULL,
    metrics_json TEXT NOT NULL
)
"""


def record_metrics(
    conn: duckdb.DuckDBPyConnection, command: str, source: str, metrics: dict
) -> None:
    conn.execute(_TABLE)
    conn.execute(
        "INSERT INTO run_metrics (command, source, metrics_json) VALUES (?, ?, ?)",
        [command, source, json.dumps(metrics, default=str)],
    )
