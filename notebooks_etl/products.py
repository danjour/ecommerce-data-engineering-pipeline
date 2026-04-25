from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql import types as T

try:
    from .common_etl import EntityJobConfig, PARTITION_COLUMNS, parse_common_args, run_entity_job
except ImportError:
    from common_etl import EntityJobConfig, PARTITION_COLUMNS, parse_common_args, run_entity_job

RAW_SCHEMA = T.StructType(
    [
        T.StructField("product_id", T.StringType(), True),
        T.StructField("product_name", T.StringType(), True),
        T.StructField("color", T.StringType(), True),
        T.StructField("weight_kg", T.StringType(), True),
        T.StructField("category", T.StringType(), True),
        T.StructField("brand", T.StringType(), True),
        T.StructField("unit_price", T.StringType(), True),
        T.StructField("cost_price", T.StringType(), True),
    ]
)


def transform(df: DataFrame) -> DataFrame:
    standardized = df.select(
        F.col("product_id").cast("int").alias("product_id"),
        F.trim("product_name").alias("product_name"),
        F.initcap(F.trim("color")).alias("color"),
        F.round(F.col("weight_kg").cast("double"), 2).alias("weight_kg"),
        F.lower(F.trim("category")).alias("category"),
        F.trim("brand").alias("brand"),
        F.round(F.col("unit_price").cast("double"), 2).alias("unit_price"),
        F.round(F.col("cost_price").cast("double"), 2).alias("cost_price"),
        *[F.col(col) for col in PARTITION_COLUMNS],
        F.col("_source_path"),
    )

    return (
        standardized.filter(F.col("product_id").isNotNull() & (F.col("product_id") > 0))
        .filter(F.col("product_name").isNotNull() & (F.length("product_name") > 0))
        .filter(F.col("category").isin("electronics", "home", "fashion", "beauty", "sports"))
        .filter(F.col("unit_price").isNotNull() & (F.col("unit_price") > 0))
        .filter(F.col("cost_price").isNotNull() & (F.col("cost_price") >= 0))
        .filter(F.col("cost_price") <= F.col("unit_price"))
        .filter(F.col("weight_kg").isNotNull() & (F.col("weight_kg") > 0))
    )


def main() -> None:
    args = parse_common_args("products")
    config = EntityJobConfig(
        entity_name="products",
        primary_keys=("product_id",),
        raw_schema=RAW_SCHEMA,
    )
    run_entity_job(config=config, transform_fn=transform, args=args)


if __name__ == "__main__":
    main()

