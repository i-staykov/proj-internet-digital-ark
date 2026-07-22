"""Run metrics land in the run_metrics table for later report queries."""

import json

from ark.db import connect, init_db
from ark.metrics import record_metrics


def test_record_and_read_back() -> None:
    conn = connect(":memory:")
    init_db(conn)
    record_metrics(conn, "verify", "ia_cdx", {"claimed": 5, "failed": 1})
    command, source, payload = conn.execute(
        "SELECT command, source, metrics_json FROM run_metrics"
    ).fetchone()
    assert (command, source) == ("verify", "ia_cdx")
    assert json.loads(payload) == {"claimed": 5, "failed": 1}
