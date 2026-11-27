import os
from pyspark.sql import SparkSession

spark = (
    SparkSession.builder.appName("read_raw")
    .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000")
    .config("spark.hadoop.fs.s3a.access.key", os.environ["MINIO_ROOT_USER"])
    .config("spark.hadoop.fs.s3a.secret.key", os.environ["MINIO_ROOT_PASSWORD"])
    .config("spark.hadoop.fs.s3a.path.style.access", "true")
    .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
    .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
    .getOrCreate()
)
spark.sparkContext.setLogLevel("WARN")  # меньше шума в выводе

df = (
    spark.read.option("multiLine", "true")
    .json("s3a://twitch-data/raw/streams/")
)

df.printSchema()
df.select("snapshot_ts", "dt", "hour").show(truncate=False)
print("Строк (снимков):", df.count())

spark.stop()