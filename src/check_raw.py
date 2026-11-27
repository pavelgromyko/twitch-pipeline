import os
import sys
from datetime import datetime
from statistics import median

import boto3
from dotenv import load_dotenv

load_dotenv()

since = sys.argv[1] if len(sys.argv) > 1 else "2000-01-01"
GAP_MIN = 15  # интервал больше 15 минут считаем дырой (штатный = 10)

s3 = boto3.client(
    "s3",
    endpoint_url=os.getenv("MINIO_ENDPOINT"),
    aws_access_key_id=os.getenv("MINIO_ROOT_USER"),
    aws_secret_access_key=os.getenv("MINIO_ROOT_PASSWORD"),
    region_name="us-east-1",
)

rows = []
for page in s3.get_paginator("list_objects_v2").paginate(Bucket="twitch-data", Prefix="raw/streams/"):
    for obj in page.get("Contents", []):
        parts = obj["Key"].split("/")          # raw/streams/dt=.../hour=.../snapshot_XXXX.json
        dt = parts[2].split("=")[1]
        stem = parts[4][len("snapshot_"):-len(".json")]
        fmt = "%Y-%m-%d %H%M" if len(stem) == 4 else "%Y-%m-%d %H%M%S"
        ts = datetime.strptime(f"{dt} {stem}", fmt)
        if dt >= since:
            rows.append((ts, obj["Size"]))

rows.sort()
if not rows:
    sys.exit("Нет файлов за выбранный период")

sizes = [r[1] for r in rows]
med = median(sizes)
print(f"Файлов: {len(rows)}")
print(f"Первый: {rows[0][0]} UTC, последний: {rows[-1][0]} UTC")
print(f"Размер, KiB: min {min(sizes)/1024:.0f}, медиана {med/1024:.0f}, max {max(sizes)/1024:.0f}")

small = [(t, s) for t, s in rows if s < 0.8 * med]
print(f"\nПодозрительно маленьких файлов (< 80% медианы): {len(small)}")
for t, s in small[:10]:
    print(f"  {t}  {s/1024:.0f} KiB")

gaps = []
for (t1, _), (t2, _) in zip(rows, rows[1:]):
    minutes = (t2 - t1).total_seconds() / 60
    if minutes > GAP_MIN:
        gaps.append((t1, t2, minutes))
print(f"\nДыр (интервал > {GAP_MIN} мин): {len(gaps)}")
for t1, t2, m in gaps[:15]:
    print(f"  {t1} -> {t2}  ({m:.0f} мин)")