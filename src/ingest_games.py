import json
import os
import time
from datetime import datetime, timezone

import boto3
import clickhouse_connect
import requests
from dotenv import load_dotenv

load_dotenv()
CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET")
IGDB_URL = "https://api.igdb.com/v4/games"
FIELDS = "name, first_release_date, genres.name, themes.name"


def get_token() -> str:
    resp = requests.post(
        "https://id.twitch.tv/oauth2/token",
        data={"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET, "grant_type": "client_credentials"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def igdb_query(headers: dict, body: str) -> list:
    for attempt in range(4):
        r = requests.post(IGDB_URL, headers=headers, data=body.encode("utf-8"), timeout=15)
        if r.status_code == 429:
            time.sleep(1 + attempt)
            continue
        r.raise_for_status()
        time.sleep(0.3)  # лимит IGDB: 4 запроса в секунду
        return r.json()
    raise RuntimeError("IGDB: 429 after 4 attempts")


now = datetime.now(timezone.utc)

# 1) игры из ClickHouse
ch = clickhouse_connect.get_client(
    host=os.getenv("CLICKHOUSE_HOST", "localhost"),
    port=8123,
    username=os.getenv("CLICKHOUSE_USER"),
    password=os.getenv("CLICKHOUSE_PASSWORD"),
)
rows = ch.query(
    "SELECT game_id, argMax(game_name, snapshot_ts) FROM twitch.stream_snapshots "
    "WHERE game_id != 0 GROUP BY game_id"
).result_rows
games = {str(gid): {"name": name, "igdb_id": ""} for gid, name in rows}
requested = {gid: g["name"] for gid, g in games.items()}

headers = {"Client-Id": CLIENT_ID, "Authorization": f"Bearer {get_token()}"}

# 2) Twitch Helix: игры по id, по 100 за запрос
helix_pages = []
ids = list(games)
for i in range(0, len(ids), 100):
    r = requests.get(
        "https://api.twitch.tv/helix/games",
        headers=headers,
        params=[("id", g) for g in ids[i:i + 100]],
        timeout=15,
    )
    r.raise_for_status()
    page = r.json()
    helix_pages.append(page)
    for g in page["data"]:
        if g["id"] in games:
            games[g["id"]]["name"] = g["name"]
            games[g["id"]]["igdb_id"] = g["igdb_id"]

# 3) IGDB: только по igdb_id, по 200 за запрос
link_ids = sorted({g["igdb_id"] for g in games.values() if g["igdb_id"]})
igdb_items = []
for i in range(0, len(link_ids), 200):
    chunk = link_ids[i:i + 200]
    body = f"fields {FIELDS}; where id = ({','.join(chunk)}); limit 200;"
    igdb_items.extend(igdb_query(headers, body))
by_id = {str(x["id"]): x for x in igdb_items}

# 4) сырой слой в S3: ответы API как есть
s3 = boto3.client(
    "s3",
    endpoint_url=os.getenv("MINIO_ENDPOINT", "http://localhost:9000"),
    aws_access_key_id=os.getenv("MINIO_ROOT_USER"),
    aws_secret_access_key=os.getenv("MINIO_ROOT_PASSWORD"),
    region_name="us-east-1",
)
key = f"raw/games/dt={now:%Y-%m-%d}/games_{now:%H%M%S}.json"
payload = {
    "fetched_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    "requested": [{"game_id": gid, "name": n} for gid, n in requested.items()],
    "helix": helix_pages,
    "igdb": igdb_items,
}
s3.put_object(
    Bucket="twitch-data",
    Key=key,
    Body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
    ContentType="application/json",
)

# 5) строки справочника
print(f"Raw saved: s3://twitch-data/{key}")
print(f"Games requested: {len(requested)}, with igdb_id: {sum(1 for g in games.values() if g['igdb_id'])}, found in IGDB: {len(by_id)}")