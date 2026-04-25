from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql import types as T

try:
    from .common_etl import EntityJobConfig, PARTITION_COLUMNS, parse_common_args, run_entity_job
except ImportError:
    from common_etl import EntityJobConfig, PARTITION_COLUMNS, parse_common_args, run_entity_job

RAW_SCHEMA = T.StructType(
    [
        T.StructField("customer_id", T.StringType(), True),
        T.StructField("customer_name", T.StringType(), True),
        T.StructField("age", T.StringType(), True),
        T.StructField("gender", T.StringType(), True),
        T.StructField("city", T.StringType(), True),
        T.StructField("state", T.StringType(), True),
        T.StructField("signup_date", T.StringType(), True),
        T.StructField("customer_segment", T.StringType(), True),
        T.StructField("device_preference", T.StringType(), True),
    ]
)


def transform(df: DataFrame) -> DataFrame:
    return (
        df.select(
            F.col("customer_id").cast("int").alias("customer_id"),
            F.trim("customer_name").alias("customer_name"),
            F.col("age").cast("int").alias("age"),
            F.initcap(F.trim("gender")).alias("gender"),
            F.initcap(F.trim("city")).alias("city"),
            F.upper(F.trim("state")).alias("state"),
            F.to_date("signup_date").alias("signup_date"),
            F.lower(F.trim("customer_segment")).alias("customer_segment"),
            F.lower(F.trim("device_preference")).alias("device_preference"),
            *[F.col(col) for col in PARTITION_COLUMNS],
            F.col("_source_path"),
        )
        .filter(F.col("customer_id").isNotNull() & (F.col("customer_id") > 0))
        .filter(F.col("age").between(18, 100))
        .filter(F.col("signup_date").isNotNull())
        .filter(F.col("customer_name").isNotNull() & (F.length("customer_name") > 0))
        .filter(F.col("state").rlike("^[A-Z]{2}$"))
        .filter(F.col("customer_segment").isin("regular", "premium", "vip"))
        .filter(F.col("device_preference").isin("mobile", "desktop", "tablet"))
    )


def main() -> None:
    args = parse_common_args("customers")
    config = EntityJobConfig(
        entity_name="customers",
        primary_keys=("customer_id",),
        raw_schema=RAW_SCHEMA,
    )
    run_entity_job(config=config, transform_fn=transform, args=args)


if __name__ == "__main__":
    main()

