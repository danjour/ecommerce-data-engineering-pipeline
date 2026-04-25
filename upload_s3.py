from typing import Literal
import boto3
from botocore.config import Config
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from datetime import datetime, timedelta
from dotenv import load_dotenv
from config import required_env, int_env
from upload_tracking import load_uploaded_ids, save_uploaded_ids

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

BUCKET_NAME = required_env("BUCKET_NAME")
TRACK_FILE = os.getenv("TRACK_FILE", "uploaded_files.json")
LOCAL_DATA_DIR = required_env("LOCAL_DATA_DIR")
MAX_WORKERS = int_env("MAX_WORKERS", 8)

FILES = ["customers.csv","products.csv","orders.csv","order_items.csv","payments.csv",]
UploadStatus = Literal["uploaded", "skipped_existing", "skipped_missing", "failed"]

if not os.path.isdir(LOCAL_DATA_DIR):
    raise ValueError(f"LOCAL_DATA_DIR does not exist: {LOCAL_DATA_DIR}")

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

def upload_file(s3_client,date: str,file_name: str,uploaded_ids: set[str],ids_lock: Lock,) -> tuple[str | None, UploadStatus, str]:
    year, month, day = date.split("-")
    table_name = file_name.replace(".csv", "")

    local_path = os.path.join(LOCAL_DATA_DIR, f"{date}-{file_name}")

    s3_key = f"raw/{table_name}/year={year}/month={month}/day={day}/{file_name}"

    with ids_lock:
        if s3_key in uploaded_ids:
            return s3_key, "skipped_existing", "already uploaded"

    if not os.path.exists(local_path):
        return s3_key, "skipped_missing", f"File not found: {local_path}"

    try:
        s3_client.upload_file(local_path, BUCKET_NAME, s3_key)
        with ids_lock:
            uploaded_ids.add(s3_key)
        return s3_key, "uploaded", ""
    except Exception as exc:
        return s3_key, "failed", f"{type(exc).__name__}: {exc}"
        
# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    s3 = boto3.client(
        "s3",
        config=Config(
            max_pool_connections=MAX_WORKERS,
            retries={"max_attempts": 10, "mode": "standard"},
        ),
    )

    today = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)

    start_of_month = today.replace(day=1)

    date_range = build_date_range(start_of_month, today)
    uploaded_ids = load_uploaded_ids(TRACK_FILE)
    ids_lock = Lock()

    logger.info("Uploading files from %s to %s", date_range[0], date_range[-1])

    tasks = [(date, file_name) for date in date_range for file_name in FILES]
    total = len(tasks)

    uploaded = 0
    skipped = 0
    failed = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(upload_file, s3, date, file_name, uploaded_ids, ids_lock): (date, file_name)
            for date, file_name in tasks
        }

        for future in as_completed(futures):
            s3_key, success, error = future.result()

            if success == "uploaded":
                logger.info("[OK]      %s", s3_key)
                uploaded += 1
            elif success == "skipped_existing":
                logger.info("[SKIP]    %s", s3_key)
                skipped += 1
            elif success == "skipped_missing":
                logger.warning("[SKIP]    %s", error)
                skipped += 1
            else:
                logger.error("[FAILED]  %s — %s", s3_key, error)
                failed += 1
        
    save_uploaded_ids(TRACK_FILE, uploaded_ids)

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
