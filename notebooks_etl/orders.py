from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql import types as T

try:
    from .common_etl import EntityJobConfig, PARTITION_COLUMNS, parse_common_args, run_entity_job
except ImportError:
    from common_etl import EntityJobConfig, PARTITION_COLUMNS, parse_common_args, run_entity_job

RAW_SCHEMA = T.StructType(
    [
        T.StructField("order_id", T.StringType(), True),
        T.StructField("customer_id", T.StringType(), True),
        T.StructField("order_date", T.StringType(), True),
        T.StructField("order_status", T.StringType(), True),
        T.StructField("sales_channel", T.StringType(), True),
        T.StructField("coupon_code", T.StringType(), True),
        T.StructField("shipping_cost", T.StringType(), True),
    ]
)


def transform(df: DataFrame) -> DataFrame:
    standardized = df.select(
        F.col("order_id").cast("int").alias("order_id"),
        F.col("customer_id").cast("int").alias("customer_id"),
        F.to_timestamp("order_date").alias("order_date"),
        F.lower(F.trim("order_status")).alias("order_status"),
        F.lower(F.trim("sales_channel")).alias("sales_channel"),
        F.when(F.trim("coupon_code") == "", F.lit(None))
        .otherwise(F.upper(F.trim("coupon_code")))
        .alias("coupon_code"),
        F.round(F.col("shipping_cost").cast("double"), 2).alias("shipping_cost"),
        *[F.col(col) for col in PARTITION_COLUMNS],
        F.col("_source_path"),
    )

    return (
        standardized.filter(F.col("order_id").isNotNull() & (F.col("order_id") > 0))
        .filter(F.col("customer_id").isNotNull() & (F.col("customer_id") > 0))
        .filter(F.col("order_date").isNotNull())
        .filter(F.col("order_status").isin("delivered", "shipped", "processing", "cancelled"))
        .filter(F.col("sales_channel").isin("site", "app", "pdv"))
        .filter(F.col("shipping_cost").isNotNull() & (F.col("shipping_cost") >= 0))
    )


def main() -> None:
    args = parse_common_args("orders")
    config = EntityJobConfig(
        entity_name="orders",
        primary_keys=("order_id",),
        raw_schema=RAW_SCHEMA,
    )
    run_entity_job(config=config, transform_fn=transform, args=args)


if __name__ == "__main__":
    main()

