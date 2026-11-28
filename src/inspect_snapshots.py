import json
import os
import sys

import boto3
from dotenv import load_dotenv

load_dotenv()
dt, hour = sys.argv[1], sys.argv[2]

s3 = boto3.client(
    "s3",
    endpoint_url=os.getenv("MINIO_ENDPOINT"),
    aws_access_key_id=os.getenv("MINIO_ROOT_USER"),
    aws_secret_access_key=os.getenv("MINIO_ROOT_PASSWORD"),
    region_name="us-east-1",
)
prefix = f"raw/streams/dt={dt}/hour={hour}/"
resp = s3.list_objects_v2(Bucket="twitch-data", Prefix=prefix)
print(f"{'file':26} {'in_pages':>9} {'unique':>7} {'dups':>5} {'short_pages':>12}")
for obj in sorted(resp.get("Contents", []), key=lambda o: o["Key"]):
    payload = json.loads(s3.get_object(Bucket="twitch-data", Key=obj["Key"])["Body"].read())
    pages = payload["pages"]
    ids = [s["id"] for p in pages for s in p["data"]]
    short = sum(1 for p in pages if len(p["data"]) < 100)
    name = obj["Key"].split("/")[-1]
    print(f"{name:26} {len(ids):>9} {len(set(ids)):>7} {len(ids) - len(set(ids)):>5} {short:>12}")