from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql import types as T

try:
    from .common_etl import EntityJobConfig, PARTITION_COLUMNS, parse_common_args, run_entity_job
except ImportError:
    from common_etl import EntityJobConfig, PARTITION_COLUMNS, parse_common_args, run_entity_job

RAW_SCHEMA = T.StructType(
    [
        T.StructField("order_item_id", T.StringType(), True),
        T.StructField("order_id", T.StringType(), True),
        T.StructField("product_id", T.StringType(), True),
        T.StructField("quantity", T.StringType(), True),
        T.StructField("unit_price", T.StringType(), True),
        T.StructField("discount", T.StringType(), True),
        T.StructField("total_price", T.StringType(), True),
    ]
)


def transform(df: DataFrame) -> DataFrame:
    standardized = df.select(
        F.col("order_item_id").cast("int").alias("order_item_id"),
        F.col("order_id").cast("int").alias("order_id"),
        F.col("product_id").cast("int").alias("product_id"),
        F.col("quantity").cast("int").alias("quantity"),
        F.round(F.col("unit_price").cast("double"), 2).alias("unit_price"),
        F.round(F.col("discount").cast("double"), 2).alias("discount"),
        F.round(F.col("total_price").cast("double"), 2).alias("total_price"),
        *[F.col(col) for col in PARTITION_COLUMNS],
        F.col("_source_path"),
    )

    expected_total = F.round((F.col("quantity") * F.col("unit_price")) - F.col("discount"), 2)

    return (
        standardized.filter(F.col("order_item_id").isNotNull() & (F.col("order_item_id") > 0))
        .filter(F.col("order_id").isNotNull() & (F.col("order_id") > 0))
        .filter(F.col("product_id").isNotNull() & (F.col("product_id") > 0))
        .filter(F.col("quantity").isNotNull() & (F.col("quantity") > 0))
        .filter(F.col("unit_price").isNotNull() & (F.col("unit_price") >= 0))
        .filter(F.col("discount").isNotNull() & (F.col("discount") >= 0))
        .filter(F.col("total_price").isNotNull() & (F.col("total_price") >= 0))
        .filter(F.abs(expected_total - F.col("total_price")) <= F.lit(0.05))
    )


def main() -> None:
    args = parse_common_args("order_items")
    config = EntityJobConfig(
        entity_name="order_items",
        primary_keys=("order_item_id",),
        raw_schema=RAW_SCHEMA,
    )
    run_entity_job(config=config, transform_fn=transform, args=args)


if __name__ == "__main__":
    main()

