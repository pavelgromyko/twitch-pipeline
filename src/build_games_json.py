import json
import os
import time
from datetime import datetime, timezone

import clickhouse_connect
import requests
from dotenv import load_dotenv

load_dotenv()
CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET")
OUT_PATH = "data/games_igdb.json"
IGDB_URL = "https://api.igdb.com/v4/games"
FIELDS = "name, slug, first_release_date, genres.name, themes.name"


def get_token() -> str:
    resp = requests.post(
        "https://id.twitch.tv/oauth2/token",
        data={"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET, "grant_type": "client_credentials"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def igdb_query(headers: dict, body: str) -> list:
    """Один запрос к IGDB. Лимит 4 запроса в секунду, поэтому пауза и повтор при 429."""
    for attempt in range(4):
        r = requests.post(IGDB_URL, headers=headers, data=body.encode("utf-8"), timeout=15)
        if r.status_code == 429:
            time.sleep(1 + attempt)
            continue
        r.raise_for_status()
        time.sleep(0.3)
        return r.json()
    raise RuntimeError("IGDB: 429 after 4 attempts")


def clean(item: dict) -> dict:
    ts = item.get("first_release_date")
    return {
        "igdb_id": item["id"],
        "name": item.get("name"),
        "slug": item.get("slug"),
        "first_release_date": datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat() if ts else None,
        "genres": [g["name"] for g in item.get("genres", [])],
        "themes": [t["name"] for t in item.get("themes", [])],
    }


# 1) все игры из ClickHouse; вес игры = сумма зрителей по всем снимкам
ch = clickhouse_connect.get_client(
    host=os.getenv("CLICKHOUSE_HOST", "localhost"),
    port=8123,
    username=os.getenv("CLICKHOUSE_USER"),
    password=os.getenv("CLICKHOUSE_PASSWORD"),
)
rows = ch.query(
    "SELECT game_id, argMax(game_name, snapshot_ts), sum(viewer_count) "
    "FROM twitch.stream_snapshots WHERE game_id != 0 GROUP BY game_id"
).result_rows
games = {
    str(gid): {"twitch_game_id": int(gid), "twitch_name": name, "viewers_total": int(v), "igdb_link": ""}
    for gid, name, v in rows
}

headers = {"Client-Id": CLIENT_ID, "Authorization": f"Bearer {get_token()}"}

# 2) Twitch Helix: igdb_id, по 100 игр за запрос
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
        games[g["id"]]["igdb_link"] = g["igdb_id"]

# 3) IGDB по igdb_id, по 200 игр за запрос
link_ids = sorted({g["igdb_link"] for g in games.values() if g["igdb_link"]})
by_id = {}
for i in range(0, len(link_ids), 200):
    chunk = link_ids[i:i + 200]
    body = f"fields {FIELDS}; where id = ({','.join(chunk)}); limit 200;"
    for item in igdb_query(headers, body):
        by_id[str(item["id"])] = clean(item)

# 4) собираем результат; для игр без связки ищем по названию
result = []
for g in games.values():
    entry = {
        "twitch_game_id": g["twitch_game_id"],
        "twitch_name": g["twitch_name"],
        "viewers_total": g["viewers_total"],
        "source": "not_found",
        "igdb": None,
        "candidates": [],
    }
    link = g["igdb_link"]
    name = g["twitch_name"]
    if link and link in by_id:
        entry["source"] = "igdb_id"
        entry["igdb"] = by_id[link]
    elif name == "(no category)":
        entry["note"] = "empty name in Twitch"
    else:
        if link:
            entry["note"] = "igdb_id from Twitch not found in IGDB"
        safe = name.replace('"', '\\"')
        items = [clean(x) for x in igdb_query(headers, f'search "{safe}"; fields {FIELDS}; limit 5;')]
        exact = [x for x in items if (x["name"] or "").casefold() == name.casefold()]
        entry["candidates"] = items[:3]
        entry["exact_matches"] = len(exact)
        if exact:
            entry["source"] = "name_search"
            entry["igdb"] = exact[0]
    result.append(entry)

result.sort(key=lambda e: -e["viewers_total"])
os.makedirs("data", exist_ok=True)
with open(OUT_PATH, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

# 5) сводка
total_v = sum(e["viewers_total"] for e in result)
print(f"Saved {len(result)} games to {OUT_PATH}")
for src in ("igdb_id", "name_search", "not_found"):
    part = [e for e in result if e["source"] == src]
    share = sum(e["viewers_total"] for e in part) / total_v
    print(f"  {src:12} games: {len(part):4}   viewers share: {share:.1%}")
with_genres = sum(e["viewers_total"] for e in result if e["igdb"] and e["igdb"]["genres"])
print(f"  games with genres: viewers share {with_genres / total_v:.1%}")

print("\nname_search matches:")
for e in result:
    if e["source"] == "name_search":
        print(f"  {e['twitch_name']} -> {e['igdb']['name']} | {e['igdb']['genres']} | exact: {e['exact_matches']}")

print("\nnot_found, top 25 by viewers:")
for e in [x for x in result if x["source"] == "not_found"][:25]:
    cand = [c["name"] for c in e["candidates"]]
    print(f"  {e['twitch_name']} ({e['viewers_total']}) candidates: {cand}")