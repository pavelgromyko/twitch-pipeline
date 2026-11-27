import os
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

spark = (
    SparkSession.builder.appName("flatten")
    .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000")
    .config("spark.hadoop.fs.s3a.access.key", os.environ["MINIO_ROOT_USER"])
    .config("spark.hadoop.fs.s3a.secret.key", os.environ["MINIO_ROOT_PASSWORD"])
    .config("spark.hadoop.fs.s3a.path.style.access", "true")
    .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
    .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
    .getOrCreate()
)
spark.sparkContext.setLogLevel("WARN")

raw = spark.read.option("multiLine", "true").json("s3a://twitch-data/raw/streams/")

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
)

streams.printSchema()
streams.orderBy("rank").show(5, truncate=40)

total = streams.count()
distinct = streams.select("stream_id").distinct().count()
print("Всего строк:", total)
print("Уникальных stream_id:", distinct)
print("Без игры (game_id пустой):", streams.filter(F.col("game_id") == "").count())

spark.stop()