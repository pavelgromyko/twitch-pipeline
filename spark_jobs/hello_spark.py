from pyspark.sql import SparkSession

spark = SparkSession.builder.appName("hello").getOrCreate()
print("Spark version:", spark.version)

df = spark.createDataFrame(
    [("Grand Theft Auto VI", 23643), ("Counter-Strike", 19327), ("Splatoon 3", 18685)],
    ["game", "viewers"],
)

df.show()
print("Сумма зрителей:", df.agg({"viewers": "sum"}).collect()[0][0])

spark.stop()