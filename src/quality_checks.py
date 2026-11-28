import os
import sys
from datetime import datetime, timezone

import clickhouse_connect
from dotenv import load_dotenv

load_dotenv()

ch = clickhouse_connect.get_client(
    host=os.getenv("CLICKHOUSE_HOST", "localhost"),
    port=8123,
    username=os.getenv("CLICKHOUSE_USER"),
    password=os.getenv("CLICKHOUSE_PASSWORD"),
)

GAPS_SQL = """
SELECT countIf(gap > 900) FROM (
    SELECT dateDiff('second',
        lagInFrame(snapshot_ts, 1, snapshot_ts) OVER (
            ORDER BY snapshot_ts
            ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING),
        snapshot_ts) AS gap
    FROM (SELECT DISTINCT snapshot_ts FROM twitch.last_day)
)
"""

# name, sql, warn_if, error_if, description
CHECKS = [
    ("freshness_minutes",
     "SELECT dateDiff('minute', max(snapshot_ts), now()) FROM twitch.stream_snapshots",
     lambda v: v > 90, lambda v: v > 150,
     "minutes since the last snapshot in ClickHouse"),
    ("gaps_last_24h",
     GAPS_SQL,
     lambda v: v > 0, lambda v: False,
     "intervals longer than 15 min in the last 24h"),
    ("duplicate_snapshots",
     "SELECT count() FROM (SELECT snapshot_ts FROM twitch.last_day "
     "GROUP BY snapshot_ts HAVING count() != uniqExact(stream_id))",
     lambda v: False, lambda v: v > 0,
     "snapshots with repeated stream_id"),
    ("min_streams_per_snapshot",
     "SELECT min(c) FROM (SELECT count() AS c FROM twitch.last_day GROUP BY snapshot_ts)",
     lambda v: v < 1950, lambda v: v < 1850,
     "smallest snapshot in the last 24h"),
    ("dim_games_age_hours",
     "SELECT dateDiff('hour', max(updated_at), now()) FROM twitch.dim_games",
     lambda v: v > 30, lambda v: v > 54,
     "hours since dim_games was rebuilt"),
    ("dim_games_coverage_gap_pct",
     "SELECT round(100 * sumIf(viewer_count, game_id NOT IN (SELECT game_id FROM twitch.dim_games)) "
     "/ sum(viewer_count), 1) FROM twitch.last_day WHERE game_id != 0",
     lambda v: v > 5, lambda v: False,
     "% of viewers in games missing from dim_games"),
]

# Test mode: QC_FORCE_FAIL=<check name> replaces that value with a huge number
# and skips writing to the log table, so a failure can be tested safely.
forced = os.getenv("QC_FORCE_FAIL")
checked_at = datetime.now(timezone.utc)
log_rows = []
errors = 0
warnings = 0

for name, sql, warn_if, error_if, note in CHECKS:
    try:
        value = ch.query(sql).result_rows[0][0]
    except Exception as exc:
        print(f"ERROR {name:28} query failed: {exc}")
        errors += 1
        log_rows.append([checked_at, name, None, "ERROR"])
        continue

    is_forced = forced == name
    if is_forced:
        value = 10 ** 6

    if value is None:
        status = "ERROR"
    elif error_if(value):
        status = "ERROR"
    elif warn_if(value):
        status = "WARN"
    else:
        status = "OK"

    errors += status == "ERROR"
    warnings += status == "WARN"
    tag = "  (forced)" if is_forced else ""
    print(f"{status:5} {name:28} {value!s:>8}   {note}{tag}")
    if not is_forced:
        log_rows.append([checked_at, name, None if value is None else float(value), status])

if log_rows:
    ch.insert("twitch.data_quality_log", log_rows,
              column_names=["checked_at", "check_name", "value", "status"])

print(f"\nResult: {errors} error(s), {warnings} warning(s)")
sys.exit(1 if errors else (99 if warnings else 0))