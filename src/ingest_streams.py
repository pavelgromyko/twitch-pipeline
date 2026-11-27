import json
import os
import time
from datetime import datetime, timezone

import boto3
import requests
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET")

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://localhost:9000")
MINIO_USER = os.getenv("MINIO_ROOT_USER")
MINIO_PASSWORD = os.getenv("MINIO_ROOT_PASSWORD")
BUCKET = "twitch-data"

PAGE_SIZE = 100   # максимум, который разрешает Twitch
MAX_PAGES = 20    # 10 страниц * 100 = топ-1000 стримов


def get_token() -> str:
    resp = requests.post(
        "https://id.twitch.tv/oauth2/token",
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "client_credentials",
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def fetch_page(token: str, cursor: str | None) -> dict:
    """Одна страница стримов. При временных сбоях повторяем запрос."""
    params = {"first": PAGE_SIZE}
    if cursor:
        params["after"] = cursor

    for attempt in range(3):
        resp = requests.get(
            "https://api.twitch.tv/helix/streams",
            headers={"Client-Id": CLIENT_ID, "Authorization": f"Bearer {token}"},
            params=params,
            timeout=10,
        )
        # 429 = слишком много запросов, 5xx = сбой на стороне Twitch
        if resp.status_code == 429 or resp.status_code >= 500:
            wait = 2 ** attempt
            print(f"  статус {resp.status_code}, повтор через {wait} с")
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp.json()

    raise RuntimeError("Twitch API не ответил после 3 попыток")


def fetch_snapshot(token: str) -> list[dict]:
    """Идём по страницам, пока есть cursor или не набрали MAX_PAGES."""
    pages = []
    cursor = None
    for n in range(1, MAX_PAGES + 1):
        page = fetch_page(token, cursor)
        pages.append(page)
        print(f"  страница {n}: {len(page['data'])} стримов")
        cursor = page.get("pagination", {}).get("cursor")
        if not cursor:
            break
    return pages


def upload_to_s3(payload: dict, snapshot_ts: datetime) -> str:
    s3 = boto3.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_USER,
        aws_secret_access_key=MINIO_PASSWORD,
        region_name="us-east-1",  # MinIO регион не использует, но boto3 его требует
    )
    key = (
        f"raw/streams/dt={snapshot_ts:%Y-%m-%d}/hour={snapshot_ts:%H}/"
        f"snapshot_{snapshot_ts:%H%M%S}.json"
    )
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    s3.put_object(Bucket=BUCKET, Key=key, Body=body, ContentType="application/json")
    return key


if __name__ == "__main__":
    snapshot_ts = datetime.now(timezone.utc)  # время снимка фиксируем ДО запросов
    print(f"Снимок {snapshot_ts:%Y-%m-%d %H:%M:%S} UTC")

    token = get_token()
    pages = fetch_snapshot(token)

    payload = {
        "snapshot_ts": snapshot_ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "pages": pages,
    }
    key = upload_to_s3(payload, snapshot_ts)

    total = sum(len(p["data"]) for p in pages)
    print(f"Сохранено {total} стримов в s3://{BUCKET}/{key}")