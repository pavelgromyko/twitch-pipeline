import os
import requests
import clickhouse_connect
from dotenv import load_dotenv

load_dotenv()
CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET")


def get_token() -> str:
    resp = requests.post(
        "https://id.twitch.tv/oauth2/token",
        data={"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET, "grant_type": "client_credentials"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


# 1) все игры из ClickHouse, вес = сумма зрителей по всем снимкам
ch = clickhouse_connect.get_client(
    host="localhost", port=8123,
    username=os.getenv("CLICKHOUSE_USER"), password=os.getenv("CLICKHOUSE_PASSWORD"),
)
rows = ch.query(
    "SELECT game_id, argMax(game_name, snapshot_ts), sum(viewer_count) "
    "FROM twitch.stream_snapshots WHERE game_id != 0 GROUP BY game_id"
).result_rows
games = {str(r[0]): {"name": r[1], "viewers": int(r[2]), "igdb_id": ""} for r in rows}

headers = {"Client-Id": CLIENT_ID, "Authorization": f"Bearer {get_token()}"}

# 2) Helix: igdb_id для всех игр, по 100 за запрос
ids = list(games)
for i in range(0, len(ids), 100):
    r = requests.get(
        "https://api.twitch.tv/helix/games",
        headers=headers,
        params=[("id", g) for g in ids[i:i + 100]],
        timeout=15,
    )
    r.raise_for_status()
    for g in r.json()["data"]:
        games[g["id"]]["igdb_id"] = g["igdb_id"]

total = len(games)
with_id = sum(1 for g in games.values() if g["igdb_id"])
v_total = sum(g["viewers"] for g in games.values())
v_with = sum(g["viewers"] for g in games.values() if g["igdb_id"])
print(f"Games: {total}, with igdb_id: {with_id}")
print(f"Viewer share covered: {v_with / v_total:.1%}")
print("Top without igdb_id:")
missing = sorted((g for g in games.values() if not g["igdb_id"]), key=lambda g: -g["viewers"])
for g in missing[:60]:
    print("  ", g["name"], g["viewers"])

# 3) IGDB: поиск по названию
for name in ["Dota 2", "Counter-Strike"]:
    body = f'search "{name}"; fields id, name, first_release_date, genres.name; limit 5;'
    r = requests.post("https://api.igdb.com/v4/games", headers=headers, data=body, timeout=10)
    print(f"\nIGDB search '{name}': status {r.status_code}")
    for x in r.json():
        print("  ", x)