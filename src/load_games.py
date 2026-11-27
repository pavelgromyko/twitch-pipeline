import json
import os
from datetime import datetime, timezone

import boto3
import clickhouse_connect
from dotenv import load_dotenv

load_dotenv()

s3 = boto3.client(
    "s3",
    endpoint_url=os.getenv("MINIO_ENDPOINT", "http://localhost:9000"),
    aws_access_key_id=os.getenv("MINIO_ROOT_USER"),
    aws_secret_access_key=os.getenv("MINIO_ROOT_PASSWORD"),
    region_name="us-east-1",
)

keys = []
for page in s3.get_paginator("list_objects_v2").paginate(Bucket="twitch-data", Prefix="raw/games/"):
    keys += [o["Key"] for o in page.get("Contents", [])]
if not keys:
    raise SystemExit("No files in raw/games/")
key = max(keys)  # в имени дата и время в UTC, максимум = самый свежий файл
payload = json.loads(s3.get_object(Bucket="twitch-data", Key=key)["Body"].read())
print("Reading", key)

games = {r["game_id"]: {"name": r["name"], "igdb_id": ""} for r in payload["requested"]}
for page in payload["helix"]:
    for g in page["data"]:
        if g["id"] in games:
            games[g["id"]] = {"name": g["name"], "igdb_id": g["igdb_id"]}
by_id = {str(x["id"]): x for x in payload["igdb"]}

now = datetime.now(timezone.utc).replace(tzinfo=None)
rows = []
for gid, g in games.items():
    item = by_id.get(g["igdb_id"]) if g["igdb_id"] else None
    ts = item.get("first_release_date") if item else None
    rows.append([
        int(gid),
        g["name"],
        int(g["igdb_id"]) if g["igdb_id"] else 0,
        item["name"] if item else "",
        datetime.fromtimestamp(ts, tz=timezone.utc).date() if ts else None,
        [x["name"] for x in item.get("genres", [])] if item else [],
        [x["name"] for x in item.get("themes", [])] if item else [],
        "igdb_id" if item else "unknown",
        now,
    ])

ch = clickhouse_connect.get_client(
    host=os.getenv("CLICKHOUSE_HOST", "localhost"),
    port=8123,
    username=os.getenv("CLICKHOUSE_USER"),
    password=os.getenv("CLICKHOUSE_PASSWORD"),
)
ch.command("TRUNCATE TABLE twitch.dim_games")
ch.insert(
    "twitch.dim_games",
    rows,
    column_names=["game_id", "game_name", "igdb_id", "igdb_name", "first_release_date",
                  "genres", "themes", "genre_source", "updated_at"],
)
print(f"Loaded {len(rows)} games, with genres: {sum(1 for r in rows if r[7] == 'igdb_id')}")