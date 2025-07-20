import os
import sys
import argparse
from pyspark.sql import SparkSession
import pyspark.sql.functions as F
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, IntegerType, TimestampType

# -------- Argument parsing --------
parser = argparse.ArgumentParser()
parser.add_argument("input_path", help="GCS path to the input CSV file")
parser.add_argument("--temp_gcs_bucket", required=True, help="Temporary GCS bucket for BigQuery connector")
parser.add_argument("--project_id", required=True, help="GCP project ID")
parser.add_argument("--bq_dataset", required=True, help="BigQuery dataset ID")
parser.add_argument("--bq_table", required=True, help="BigQuery table name")

args = parser.parse_args()

# -------- Spark Init --------
spark = SparkSession.builder \
    .appName("CSV to BigQuery") \
    .config("temporaryGcsBucket", args.temp_gcs_bucket) \
    .getOrCreate()

# -------- Schema --------
columns = StructType([
    StructField("product", StringType(), True),
    StructField("price", DoubleType(), True),
    StructField("quantity", IntegerType(), True),
    StructField("total", DoubleType(), True),
    StructField("ordered_at", TimestampType(), True),
    StructField("delivery_at", TimestampType(), True)
])

# -------- Read Input --------
df = spark.read.csv(args.input_path, header=True, schema=columns)

# -------- Data Cleaning --------
df_filtered = df.filter(~(
    df['quantity'].isNull() & df.price.isNull() & df.total.isNull()
))

df_cleaned = df_filtered.withColumn(
    'quantity',
    F.when(F.col('quantity').isNull(), F.floor(F.col("total") / F.col("price")))
     .otherwise(F.col('quantity'))
).withColumn(
    'total',
    F.when(F.col('total').isNull(), F.round(F.col('price') * F.col('quantity'), 2))
     .otherwise(F.col('total'))
).withColumn(
    "processed_at", F.current_timestamp()
)

# -------- Cast types --------
df_cast = df_cleaned.select(
    F.col("product"),
    F.col("price").cast("float"),
    F.col("quantity").cast("int"),
    F.col("total").cast("float"),
    F.col("ordered_at").cast("timestamp"),
    F.col("delivery_at").cast("timestamp"),
    F.col("processed_at")
)

# -------- Write to BigQuery --------
df_cast.write.format("bigquery") \
    .option("table", f"{args.project_id}.{args.bq_dataset}.{args.bq_table}") \
    .mode("append") \
    .save()
