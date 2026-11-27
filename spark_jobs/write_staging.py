import os
import sys
from datetime import datetime, timedelta, timezone

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

RAW = "s3a://twitch-data/raw/streams/"
STAGING = "s3a://twitch-data/staging/streams/"

# --last-days N: обработать только последние N дней (UTC). Без аргумента: весь raw.
last_days = None
if "--last-days" in sys.argv:
    last_days = int(sys.argv[sys.argv.index("--last-days") + 1])

spark = (
    SparkSession.builder.appName("write_staging")
    .config("spark.hadoop.fs.s3a.endpoint", os.environ.get("MINIO_ENDPOINT", "http://minio:9000"))
    .config("spark.hadoop.fs.s3a.access.key", os.environ["MINIO_ROOT_USER"])
    .config("spark.hadoop.fs.s3a.secret.key", os.environ["MINIO_ROOT_PASSWORD"])
    .config("spark.hadoop.fs.s3a.path.style.access", "true")
    .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
    .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
    .config("spark.sql.sources.partitionOverwriteMode", "dynamic")
    .getOrCreate()
)
spark.sparkContext.setLogLevel("WARN")

reader = spark.read.option("multiLine", "true")
if last_days:
    today = datetime.now(timezone.utc).date()
    dates = [(today - timedelta(days=i)).isoformat() for i in range(last_days)]
    path = RAW + "dt={" + ",".join(dates) + "}/*/*.json"
    print("Processing dates:", dates)
    raw = reader.option("basePath", RAW).json(path)
else:
    print("Processing all raw data")
    raw = reader.json(RAW)

streams = (
    raw
    .select("snapshot_ts", F.posexplode("pages").alias("page_idx", "page"))
    .select("snapshot_ts", "page_idx", F.posexplode("page.data").alias("pos", "s"))
    .select(
        F.to_timestamp("snapshot_ts").alias("snapshot_ts"),
        (F.col("page_idx") * 100 + F.col("pos") + 1).alias("rank"),
        F.col("s.id").alias("stream_id"),
        F.col("s.user_id").alias("user_id"),
        F.col("s.user_login").alias("user_login"),
        F.col("s.game_id").alias("game_id"),
        F.col("s.game_name").alias("game_name"),
        F.col("s.language").alias("language"),
        F.col("s.viewer_count").alias("viewer_count"),
        F.to_timestamp("s.started_at").alias("started_at"),
        F.col("s.title").alias("title"),
        F.col("s.is_mature").alias("is_mature"),
        F.col("s.tags").alias("tags"),
    )
    .withColumn(
        "game_id",
        F.when(F.col("game_id").isNull() | (F.col("game_id") == ""), "0").otherwise(F.col("game_id")),
    )
    .withColumn(
        "game_name",
        F.when(F.col("game_name").isNull() | (F.col("game_name") == ""), "(no category)").otherwise(F.col("game_name")),
    )
    .dropDuplicates(["snapshot_ts", "stream_id"])
    .withColumn("dt", F.to_date("snapshot_ts"))
)

streams.write.mode("overwrite").partitionBy("dt").parquet(STAGING)

check = spark.read.parquet(STAGING)
print("Rows in staging:", check.count())
check.groupBy("dt").count().orderBy("dt").show()

spark.stop()