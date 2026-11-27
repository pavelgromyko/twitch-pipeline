import os
import requests
from dotenv import load_dotenv

load_dotenv()  # читает .env и кладёт значения в переменные окружения

CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET")


def get_token() -> str:
    """Получаем временный токен доступа (Client Credentials flow)."""
    resp = requests.post(
        "https://id.twitch.tv/oauth2/token",
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "client_credentials",
        },
        timeout=10,
    )
    resp.raise_for_status()  # при ошибке (400, 401...) скрипт упадёт с понятным сообщением
    return resp.json()["access_token"]


def get_top_streams(token: str, limit: int = 5) -> dict:
    """Запрашиваем стримы. Twitch сортирует их по числу зрителей по убыванию."""
    resp = requests.get(
        "https://api.twitch.tv/helix/streams",
        headers={
            "Client-Id": CLIENT_ID,
            "Authorization": f"Bearer {token}",
        },
        params={"first": limit},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


if __name__ == "__main__":
    token = get_token()
    data = get_top_streams(token)
    print("data - ", data)

    print("Ключи верхнего уровня:", list(data.keys()))
    print("Есть ли следующая страница:", bool(data["pagination"].get("cursor")))
    print()
    for s in data["data"]:
        print(f'{s["user_name"]:<25} {s["game_name"]:<30} {s["viewer_count"]:>7} viewers [{s["language"]}]')

    print("\nПример одной записи целиком:")
    print(data["data"][0])