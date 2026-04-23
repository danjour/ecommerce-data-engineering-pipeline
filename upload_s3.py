import boto3
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

BUCKET_NAME = os.getenv("BUCKET_NAME")
LOCAL_DATA_DIR = "random_date"
MAX_WORKERS = 8

FILES = [
    "customers.csv",
    "products.csv",
    "orders.csv",
    "order_items.csv",
    "payments.csv",
]

if not BUCKET_NAME:
    raise ValueError("BUCKET_NAME not found in .env — please set it before running.")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def build_date_range(start: datetime, end: datetime) -> list[str]:
    """Return a list of date strings (YYYY-MM-DD) from start to end, inclusive."""
    dates = []
    current = start
    while current <= end:
        dates.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)
    return dates

def upload_file(s3_client, date: str, file_name: str) -> tuple[str, bool, str]:
    """
    Upload a single file to S3 using Hive-style partitioning.

    S3 key format: raw/<table>/year=YYYY/month=MM/day=DD/<file_name>

    Returns:
        (s3_key, success: bool, error_message: str)
    """
    year, month, day = date.split("-")
    table_name = file_name.replace(".csv", "")

    local_path = os.path.join(LOCAL_DATA_DIR, f"{date}-{file_name}")
    s3_key = f"raw/{table_name}/year={year}/month={month}/day={day}/{file_name}"

    # Skip if the local file does not exist
    if not os.path.exists(local_path):
        return s3_key, False, f"File not found: {local_path}"

    try:
        s3_client.upload_file(local_path, BUCKET_NAME, s3_key)
        return s3_key, True, ""
    except Exception as exc:
        return s3_key, False, str(exc)

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    s3 = boto3.client("s3")

    today = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)
    start_of_month = today.replace(day=1)

    date_range = build_date_range(start_of_month, today)
    logger.info("Uploading files from %s to %s", date_range[0], date_range[-1])

    # Build the full list of (date, file) upload tasks
    tasks = [(date, file_name) for date in date_range for file_name in FILES]
    total = len(tasks)

    uploaded = 0
    skipped = 0
    failed = 0

    # Upload files in parallel to maximise throughput
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(upload_file, s3, date, file_name): (date, file_name)
            for date, file_name in tasks
        }

        for future in as_completed(futures):
            s3_key, success, error = future.result()

            if success:
                logger.info("[OK]      %s", s3_key)
                uploaded += 1
            elif "File not found" in error:
                logger.warning("[SKIP]    %s", error)
                skipped += 1
            else:
                logger.error("[FAILED]  %s — %s", s3_key, error)
                failed += 1

    # ---------------------------------------------------------------------------
    # Summary
    # ---------------------------------------------------------------------------
    logger.info("-" * 60)
    logger.info(
        "Done. Total: %d | Uploaded: %d | Skipped: %d | Failed: %d",
        total, uploaded, skipped, failed,
    )

    if failed > 0:
        raise SystemExit(f"{failed} file(s) failed to upload. Check logs above.")

if __name__ == "__main__":
    main()