from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql import types as T

try:
    from .common_etl import EntityJobConfig, PARTITION_COLUMNS, parse_common_args, run_entity_job
except ImportError:
    from common_etl import EntityJobConfig, PARTITION_COLUMNS, parse_common_args, run_entity_job

RAW_SCHEMA = T.StructType(
    [
        T.StructField("payment_id", T.StringType(), True),
        T.StructField("order_id", T.StringType(), True),
        T.StructField("payment_method", T.StringType(), True),
        T.StructField("installments", T.StringType(), True),
        T.StructField("payment_status", T.StringType(), True),
        T.StructField("paid_amount", T.StringType(), True),
    ]
)


def transform(df: DataFrame) -> DataFrame:
    standardized = df.select(
        F.trim("payment_id").alias("payment_id"),
        F.col("order_id").cast("int").alias("order_id"),
        F.lower(F.trim("payment_method")).alias("payment_method"),
        F.col("installments").cast("int").alias("installments"),
        F.lower(F.trim("payment_status")).alias("payment_status"),
        F.round(F.col("paid_amount").cast("double"), 2).alias("paid_amount"),
        *[F.col(col) for col in PARTITION_COLUMNS],
        F.col("_source_path"),
    )

    return (
        standardized.filter(F.col("payment_id").isNotNull() & (F.length("payment_id") > 0))
        .filter(F.col("order_id").isNotNull() & (F.col("order_id") > 0))
        .filter(F.col("payment_method").isin("credit_card", "pix", "boleto", "debit_card"))
        .filter(F.col("installments").isNotNull() & (F.col("installments") >= 1) & (F.col("installments") <= 24))
        .filter(F.col("payment_status").isin("paid", "pending", "refused"))
        .filter(F.col("paid_amount").isNotNull() & (F.col("paid_amount") >= 0))
    )


def main() -> None:
    args = parse_common_args("payments")
    config = EntityJobConfig(
        entity_name="payments",
        primary_keys=("payment_id",),
        raw_schema=RAW_SCHEMA,
    )
    run_entity_job(config=config, transform_fn=transform, args=args)


if __name__ == "__main__":
    main()

