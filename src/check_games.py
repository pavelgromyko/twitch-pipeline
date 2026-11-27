import os
import requests
from dotenv import load_dotenv

load_dotenv()
CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET")

# id из наших данных: GTA VI, Dota 2, Counter-Strike, Just Chatting
GAME_IDS = ["1867279146", "29595", "32399", "509658"]


def get_token() -> str:
    resp = requests.post(
        "https://id.twitch.tv/oauth2/token",
        data={"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET, "grant_type": "client_credentials"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


token = get_token()
headers = {"Client-Id": CLIENT_ID, "Authorization": f"Bearer {token}"}

# 1) Twitch Helix: игры по id
r = requests.get(
    "https://api.twitch.tv/helix/games",
    headers=headers,
    params=[("id", g) for g in GAME_IDS],
    timeout=10,
)
r.raise_for_status()
games = r.json()["data"]
for g in games:
    print(g["id"], g["name"], "igdb_id =", repr(g["igdb_id"]))

# 2) IGDB: жанры и темы по igdb_id
igdb_ids = [g["igdb_id"] for g in games if g["igdb_id"]]
body = (
    "fields name, genres.name, themes.name, first_release_date; "
    f"where id = ({','.join(igdb_ids)}); limit 50;"
)
r = requests.post("https://api.igdb.com/v4/games", headers=headers, data=body, timeout=10)
print("IGDB status:", r.status_code)
r.raise_for_status()
for item in r.json():
    print(item)