from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from datetime import date
from typing import Callable, Sequence

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql import types as T
from pyspark.sql.window import Window

logger = logging.getLogger(__name__)

PARTITION_COLUMNS = ("year", "month", "day")
_YEAR_PATTERN = r"[\\/]year=(\d{4})[\\/]"
_MONTH_PATTERN = r"[\\/]month=(\d{2})[\\/]"
_DAY_PATTERN = r"[\\/]day=(\d{2})[\\/]"


@dataclass(frozen=True)
class EntityJobConfig:
    entity_name: str
    primary_keys: tuple[str, ...]
    raw_schema: T.StructType


def parse_iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"Invalid date {value!r}. Expected format YYYY-MM-DD."
        ) from exc


def positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Expected integer, got {value!r}.") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError(f"Expected value > 0, got {parsed}.")
    return parsed


def parse_common_args(entity_name: str, argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=f"Transform raw CSV files for '{entity_name}' into partitioned Parquet."
    )
    parser.add_argument("--input-root", required=True, help="Raw root path (example: s3://bucket/raw).")
    parser.add_argument(
        "--output-root", required=True, help="Processed root path (example: s3://bucket/processed)."
    )
    parser.add_argument("--start-date", type=parse_iso_date, default=None, help="Filter start date (YYYY-MM-DD).")
    parser.add_argument("--end-date", type=parse_iso_date, default=None, help="Filter end date (YYYY-MM-DD).")
    parser.add_argument("--write-mode", choices=["append", "overwrite"], default="append")
    parser.add_argument("--compression", choices=["snappy", "gzip", "zstd", "uncompressed"], default="snappy")
    parser.add_argument("--repartition", type=positive_int, default=None, help="Optional target partition count.")
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
    )

    args = parser.parse_args(argv)
    if args.start_date and args.end_date and args.start_date > args.end_date:
        parser.error("--start-date cannot be after --end-date.")
    return args


def configure_logging(level_name: str) -> None:
    logging.basicConfig(
        level=level_name.upper(),
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def normalize_root_path(root_path: str) -> str:
    return root_path.rstrip("/\\")


def input_glob(input_root: str, entity_name: str) -> str:
    root = normalize_root_path(input_root)
    return f"{root}/{entity_name}/year=*/month=*/day=*/*.csv"


def output_path(output_root: str, entity_name: str) -> str:
    root = normalize_root_path(output_root)
    return f"{root}/{entity_name}"


def create_spark_session(app_name: str) -> SparkSession:
    spark = SparkSession.builder.appName(app_name).getOrCreate()
    spark.conf.set("spark.sql.sources.partitionOverwriteMode", "dynamic")
    return spark


def read_raw_csv(spark: SparkSession, path_glob: str, schema: T.StructType) -> DataFrame:
    logger.info("Reading CSV files from %s", path_glob)
    return spark.read.option("header", "true").schema(schema).csv(path_glob)


def add_partitions_from_path(df: DataFrame) -> DataFrame:
    source_path = F.input_file_name()
    return (
        df.withColumn("_source_path", source_path)
        .withColumn("year", F.regexp_extract(source_path, _YEAR_PATTERN, 1).cast("int"))
        .withColumn("month", F.regexp_extract(source_path, _MONTH_PATTERN, 1).cast("int"))
        .withColumn("day", F.regexp_extract(source_path, _DAY_PATTERN, 1).cast("int"))
        .filter(
            F.col("year").isNotNull()
            & F.col("month").isNotNull()
            & F.col("day").isNotNull()
        )
    )


def with_partition_date(df: DataFrame) -> DataFrame:
    return df.withColumn(
        "_partition_date",
        F.to_date(F.format_string("%04d-%02d-%02d", F.col("year"), F.col("month"), F.col("day"))),
    )


def apply_date_filter(df: DataFrame, start_date: date | None, end_date: date | None) -> DataFrame:
    if start_date is None and end_date is None:
        return df

    filtered = with_partition_date(df)
    if start_date is not None:
        filtered = filtered.filter(F.col("_partition_date") >= F.lit(start_date.isoformat()))
    if end_date is not None:
        filtered = filtered.filter(F.col("_partition_date") <= F.lit(end_date.isoformat()))
    return filtered.drop("_partition_date")


def deduplicate(df: DataFrame, primary_keys: Sequence[str]) -> DataFrame:
    if not primary_keys:
        return df

    order_columns = [
        F.col("year").desc_nulls_last(),
        F.col("month").desc_nulls_last(),
        F.col("day").desc_nulls_last(),
        F.col("_source_path").desc_nulls_last(),
    ]
    window_spec = Window.partitionBy(*primary_keys).orderBy(*order_columns)

    return (
        df.withColumn("_row_number", F.row_number().over(window_spec))
        .filter(F.col("_row_number") == 1)
        .drop("_row_number")
    )


def write_partitioned_parquet(
    df: DataFrame,
    target_path: str,
    write_mode: str,
    compression: str,
    repartition: int | None,
) -> None:
    output_df = df
    if repartition is not None:
        output_df = output_df.repartition(repartition, *PARTITION_COLUMNS)

    logger.info(
        "Writing Parquet to %s (mode=%s, compression=%s, partitionBy=%s)",
        target_path,
        write_mode,
        compression,
        PARTITION_COLUMNS,
    )
    (
        output_df.write.mode(write_mode)
        .option("compression", compression)
        .partitionBy(*PARTITION_COLUMNS)
        .parquet(target_path)
    )


def run_entity_job(
    config: EntityJobConfig,
    transform_fn: Callable[[DataFrame], DataFrame],
    args: argparse.Namespace,
) -> None:
    configure_logging(args.log_level)
    spark = create_spark_session(app_name=f"etl_{config.entity_name}")

    source_glob = input_glob(args.input_root, config.entity_name)
    target_path = output_path(args.output_root, config.entity_name)

    try:
        raw_df = read_raw_csv(spark, source_glob, config.raw_schema)
        staged_df = add_partitions_from_path(raw_df)
        filtered_df = apply_date_filter(staged_df, args.start_date, args.end_date)
        transformed_df = transform_fn(filtered_df)
        deduped_df = deduplicate(transformed_df, config.primary_keys)

        final_df = deduped_df.drop("_source_path")
        final_count = final_df.count()
        if final_count == 0:
            logger.warning("No rows to write for entity '%s'.", config.entity_name)
            return

        write_partitioned_parquet(
            final_df,
            target_path=target_path,
            write_mode=args.write_mode,
            compression=args.compression,
            repartition=args.repartition,
        )
        logger.info("Entity '%s' completed successfully. Rows written: %d", config.entity_name, final_count)
    finally:
        spark.stop()
