import os
import sys
from datetime import datetime, timedelta, timezone

import clickhouse_connect
from dotenv import load_dotenv

load_dotenv()

# --last-days N: читать только последние N дней (UTC). Без аргумента: все дни.
if "--last-days" in sys.argv:
    n = int(sys.argv[sys.argv.index("--last-days") + 1])
    today = datetime.now(timezone.utc).date()
    dates = [(today - timedelta(days=i)).isoformat() for i in range(n)]
    dt = dates[0] if len(dates) == 1 else "{" + ",".join(dates) + "}"
else:
    dt = "*"

url = f"http://minio:9000/twitch-data/staging/streams/dt={dt}/*.parquet"  # адрес для сервера ClickHouse
sql = f"""
INSERT INTO twitch.stream_snapshots
SELECT
    toDateTime(snapshot_ts, 'UTC'),
    toUInt16(rank),
    toUInt64(stream_id),
    toUInt64(user_id),
    user_login,
    toUInt64(game_id),
    game_name,
    language,
    toUInt32(viewer_count),
    started_at,
    is_mature
FROM s3('{url}', '{os.environ["MINIO_ROOT_USER"]}', '{os.environ["MINIO_ROOT_PASSWORD"]}', 'Parquet')
WHERE toDateTime(snapshot_ts, 'UTC') NOT IN (SELECT DISTINCT snapshot_ts FROM twitch.stream_snapshots)
"""

ch = clickhouse_connect.get_client(
    host=os.getenv("CLICKHOUSE_HOST", "localhost"),
    port=8123,
    username=os.getenv("CLICKHOUSE_USER"),
    password=os.getenv("CLICKHOUSE_PASSWORD"),
)
count = "SELECT uniqExact(snapshot_ts) FROM twitch.stream_snapshots"
before = ch.query(count).result_rows[0][0]
ch.command(sql)
after = ch.query(count).result_rows[0][0]
print(f"Source: {url}")
print(f"Snapshots before: {before}, after: {after}, added: {after - before}")