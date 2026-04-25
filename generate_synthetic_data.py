from __future__ import annotations

import argparse
import logging
import random
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Sequence

import pandas as pd

logger = logging.getLogger(__name__)

DEFAULT_NUM_CUSTOMERS = 1000
DEFAULT_NUM_PRODUCTS = 300
DEFAULT_NUM_ORDERS = 5000
DEFAULT_OUTPUT_DIR = "random_date"
DEFAULT_SEED = 42

STATES: dict[str, list[str]] = {
    "SP": ["Sao Paulo", "Campinas", "Santos", "Ribeirao Preto"],
    "RJ": ["Rio de Janeiro", "Niteroi", "Petropolis"],
    "MG": ["Belo Horizonte", "Uberlandia", "Juiz de Fora"],
    "BA": ["Salvador", "Feira de Santana"],
    "PE": ["Recife", "Olinda"],
    "CE": ["Fortaleza", "Caucaia"],
}

CUSTOMER_SEGMENTS = ["regular", "premium", "vip"]

CATEGORIES: dict[str, list[str]] = {
    "electronics": ["Headphone", "Notebook", "Mouse", "Keyboard", "Monitor"],
    "home": ["Chair", "Table", "Lamp", "Sofa", "Shelf"],
    "fashion": ["Tshirt", "Jeans", "Sneakers", "Jacket", "Dress"],
    "beauty": ["Perfume", "Shampoo", "Cream", "Lipstick"],
    "sports": ["Ball", "Bike", "Dumbbell", "Mat"],
}

BRANDS = ["Alpha", "Beta", "Gamma", "Delta", "Prime", "Neo"]
SALES_CHANNELS = ["site", "app", "pdv"]
ORDER_STATUSES = ["delivered", "shipped", "processing", "cancelled"]
PAYMENT_METHODS = ["credit_card", "pix", "boleto", "debit_card"]
CUSTOMER_COLUMNS = [
    "customer_id",
    "customer_name",
    "age",
    "gender",
    "city",
    "state",
    "signup_date",
    "customer_segment",
    "device_preference",
]
PRODUCT_COLUMNS = [
    "product_id",
    "product_name",
    "color",
    "weight_kg",
    "category",
    "brand",
    "unit_price",
    "cost_price",
]
ORDER_COLUMNS = [
    "order_id",
    "customer_id",
    "order_date",
    "order_status",
    "sales_channel",
    "coupon_code",
    "shipping_cost",
]
ORDER_ITEM_COLUMNS = [
    "order_item_id",
    "order_id",
    "product_id",
    "quantity",
    "unit_price",
    "discount",
    "total_price",
]
PAYMENT_COLUMNS = [
    "payment_id",
    "order_id",
    "payment_method",
    "installments",
    "payment_status",
    "paid_amount",
]


@dataclass(frozen=True)
class GeneratorConfig:
    num_customers: int
    num_products: int
    num_orders: int
    start_date: date
    end_date: date
    output_dir: Path
    seed: int
    log_level: str


def parse_iso_date(value: str) -> date:
    """Parse YYYY-MM-DD into a date object."""
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"Invalid date {value!r}. Expected format: YYYY-MM-DD."
        ) from exc

def positive_int(value: str) -> int:
    """Argparse helper for values that must be > 0."""
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Expected integer, got {value!r}.") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError(f"Expected value > 0, got {parsed}.")
    return parsed

def non_negative_int(value: str) -> int:
    """Argparse helper for values that must be >= 0."""
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Expected integer, got {value!r}.") from exc
    if parsed < 0:
        raise argparse.ArgumentTypeError(f"Expected value >= 0, got {parsed}.")
    return parsed

def configure_logging(level_name: str) -> None:
    """Configure process-level logging."""
    logging.basicConfig(
        level=level_name.upper(),
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

def build_date_range(start: date, end: date) -> list[date]:
    """Return all dates from start to end (inclusive)."""
    if start > end:
        raise ValueError("start date cannot be after end date.")
    dates: list[date] = []
    current = start
    while current <= end:
        dates.append(current)
        current += timedelta(days=1)
    return dates

def allocate_orders(total_orders: int, num_days: int) -> list[int]:
    """Distribute total orders across days while preserving exact total."""
    if num_days <= 0:
        raise ValueError("num_days must be > 0.")
    base, remainder = divmod(total_orders, num_days)
    return [base + (1 if idx < remainder else 0) for idx in range(num_days)]

def random_time_for_date(target_date: date, rng: random.Random) -> datetime:
    """Generate a timestamp within the same day (00:00:00 to 23:59:59)."""
    day_start = datetime.combine(target_date, time.min)
    return day_start + timedelta(seconds=rng.randint(0, 86399))

def weighted_choice(choices: Sequence[str], weights: Sequence[float], rng: random.Random) -> str:
    """Select one element from choices according to weights."""
    return rng.choices(list(choices), weights=weights, k=1)[0]

def seasonality_multiplier(order_dt: datetime) -> float:
    """Simple seasonal multiplier based on month."""
    if order_dt.month in (11, 12):
        return 1.4
    if order_dt.month in (1, 7):
        return 0.9
    return 1.0

def generate_customers(n_customers: int, rng: random.Random, reference_date: date) -> pd.DataFrame:
    """Generate deterministic customer master data."""
    rows: list[dict[str, object]] = []
    for customer_id in range(1, n_customers + 1):
        state = rng.choice(list(STATES.keys()))
        city = rng.choice(STATES[state])
        segment = weighted_choice(CUSTOMER_SEGMENTS, [0.7, 0.25, 0.05], rng)
        signup_delta = rng.randint(10, 1000)
        signup_date = reference_date - timedelta(days=signup_delta)

        rows.append(
            {
                "customer_id": customer_id,
                "customer_name": f"Customer_{customer_id}",
                "age": rng.randint(18, 75),
                "gender": rng.choice(["M", "F", "Other"]),
                "city": city,
                "state": state,
                "signup_date": signup_date,
                "customer_segment": segment,
                "device_preference": weighted_choice(
                    ["Mobile", "Desktop", "Tablet"], [0.6, 0.35, 0.05], rng
                ),
            }
        )
    return pd.DataFrame(rows, columns=CUSTOMER_COLUMNS)

def generate_products(n_products: int, rng: random.Random) -> pd.DataFrame:
    """Generate deterministic product master data."""
    rows: list[dict[str, object]] = []
    for product_id in range(1, n_products + 1):
        category = rng.choice(list(CATEGORIES.keys()))
        product_base = rng.choice(CATEGORIES[category])
        brand = rng.choice(BRANDS)

        base_price = {
            "electronics": rng.uniform(80, 5000),
            "home": rng.uniform(50, 2000),
            "fashion": rng.uniform(30, 600),
            "beauty": rng.uniform(20, 300),
            "sports": rng.uniform(40, 2500),
        }[category]

        rows.append(
            {
                "product_id": product_id,
                "product_name": f"{brand}_{product_base}_{product_id}",
                "color": rng.choice(["Black", "White", "Silver", "Blue", "Red", "Green"]),
                "weight_kg": round(rng.uniform(0.1, 15.0), 2),
                "category": category,
                "brand": brand,
                "unit_price": round(base_price, 2),
                "cost_price": round(base_price * rng.uniform(0.45, 0.75), 2),
            }
        )
    return pd.DataFrame(rows, columns=PRODUCT_COLUMNS)

def build_customer_weights(customers_df: pd.DataFrame) -> list[int]:
    """Build a precomputed weight vector for customer sampling."""
    segment_weight = {"vip": 8, "premium": 4, "regular": 1}
    return [segment_weight.get(segment, 1) for segment in customers_df["customer_segment"].tolist()]

def choose_customer(
    customers_records: list[dict[str, object]],
    customer_weights: list[int],
    rng: random.Random,
) -> dict[str, object]:
    """Choose one customer using precomputed weights."""
    chosen_index = rng.choices(range(len(customers_records)), weights=customer_weights, k=1)[0]
    return customers_records[chosen_index]

def build_deterministic_payment_id(run_token: str, order_id: int) -> str:
    """Generate deterministic UUIDs for reproducible runs."""
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{run_token}:{order_id}"))

def generate_orders_for_date(
    customers_records: list[dict[str, object]],
    customer_weights: list[int],
    products_records: list[dict[str, object]],
    n_orders: int,
    target_date: date,
    start_order_id: int,
    start_order_item_id: int,
    rng: random.Random,
    run_token: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, int, int]:
    """Generate orders, order_items and payments for one date."""
    orders: list[dict[str, object]] = []
    order_items: list[dict[str, object]] = []
    payments: list[dict[str, object]] = []

    order_id = start_order_id
    order_item_id = start_order_item_id

    for _ in range(n_orders):
        customer = choose_customer(customers_records, customer_weights, rng)
        order_dt = random_time_for_date(target_date, rng)
        status = weighted_choice(ORDER_STATUSES, [0.78, 0.10, 0.08, 0.04], rng)
        channel = weighted_choice(SALES_CHANNELS, [0.55, 0.30, 0.15], rng)

        shipping_cost = round(rng.uniform(8, 60), 2)
        coupon_code = rng.choice([None, None, None, "DISC10", "SHIP15", "VIP20"])

        num_items = weighted_choice(["1", "2", "3", "4", "5"], [0.50, 0.25, 0.15, 0.07, 0.03], rng)
        item_count = min(int(num_items), len(products_records))
        chosen_products = rng.sample(products_records, k=item_count)

        order_total = 0.0

        for product in chosen_products:
            quantity = int(weighted_choice(["1", "2", "3", "4"], [0.65, 0.22, 0.09, 0.04], rng))
            seasonal = seasonality_multiplier(order_dt)
            price_variation = rng.uniform(0.95, 1.10)
            base_unit_price = float(product["unit_price"])
            unit_price = round(base_unit_price * seasonal * price_variation, 2)

            discount_pct = rng.choice([0, 0, 0, 0.05, 0.10, 0.15])
            if customer["customer_segment"] == "vip":
                discount_pct = max(discount_pct, rng.choice([0.05, 0.10, 0.15]))

            gross_value = unit_price * quantity
            discount_value = round(gross_value * discount_pct, 2)
            total_price = round(gross_value - discount_value, 2)

            order_items.append(
                {
                    "order_item_id": order_item_id,
                    "order_id": order_id,
                    "product_id": int(product["product_id"]),
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "discount": discount_value,
                    "total_price": total_price,
                }
            )

            order_total += total_price
            order_item_id += 1

        if status == "cancelled":
            paid_amount = 0.0
            payment_status = "refused"
        else:
            paid_amount = round(order_total + shipping_cost, 2)
            payment_status = weighted_choice(["paid", "pending"], [0.92, 0.08], rng)

        orders.append(
            {
                "order_id": order_id,
                "customer_id": int(customer["customer_id"]),
                "order_date": order_dt,
                "order_status": status,
                "sales_channel": channel,
                "coupon_code": coupon_code,
                "shipping_cost": shipping_cost,
            }
        )

        payment_method = weighted_choice(PAYMENT_METHODS, [0.45, 0.30, 0.15, 0.10], rng)
        installments = rng.choice([1, 1, 1, 2, 3, 4, 6, 10]) if payment_method == "credit_card" else 1
        payments.append(
            {
                "payment_id": build_deterministic_payment_id(run_token, order_id),
                "order_id": order_id,
                "payment_method": payment_method,
                "installments": installments,
                "payment_status": payment_status,
                "paid_amount": paid_amount,
            }
        )

        order_id += 1

    orders_df = pd.DataFrame(orders, columns=ORDER_COLUMNS)
    order_items_df = pd.DataFrame(order_items, columns=ORDER_ITEM_COLUMNS)
    payments_df = pd.DataFrame(payments, columns=PAYMENT_COLUMNS)

    return orders_df, order_items_df, payments_df, order_id, order_item_id

def validate_daily_data(
    target_date: date,
    orders_df: pd.DataFrame,
    order_items_df: pd.DataFrame,
    payments_df: pd.DataFrame,
) -> None:
    """Run basic data quality checks before writing files."""
    errors: list[str] = []

    if not orders_df["order_id"].is_unique:
        errors.append("order_id is not unique in orders.")
    if not order_items_df["order_item_id"].is_unique:
        errors.append("order_item_id is not unique in order_items.")
    if not payments_df["payment_id"].is_unique:
        errors.append("payment_id is not unique in payments.")
    if len(orders_df) != len(payments_df):
        errors.append("orders and payments row counts differ.")
    if (order_items_df["quantity"] <= 0).any():
        errors.append("order_items has non-positive quantity.")
    if (order_items_df["total_price"] < 0).any():
        errors.append("order_items has negative total_price.")
    if (payments_df["paid_amount"] < 0).any():
        errors.append("payments has negative paid_amount.")

    if not order_items_df["order_id"].isin(orders_df["order_id"]).all():
        errors.append("order_items references missing order_id values.")
    if not payments_df["order_id"].isin(orders_df["order_id"]).all():
        errors.append("payments references missing order_id values.")

    payment_orders = payments_df.merge(
        orders_df[["order_id", "order_status"]],
        on="order_id",
        how="left",
        validate="one_to_one",
    )
    cancelled = payment_orders[payment_orders["order_status"] == "cancelled"]
    if not cancelled.empty:
        invalid_amount = (cancelled["paid_amount"] != 0.0).any()
        invalid_status = (cancelled["payment_status"] != "refused").any()
        if invalid_amount or invalid_status:
            errors.append("Cancelled orders must have paid_amount=0.0 and payment_status='refused'.")

    if errors:
        joined = " | ".join(errors)
        raise ValueError(f"Data validation failed for {target_date.isoformat()}: {joined}")

def write_daily_files(
    output_dir: Path,
    run_date: date,
    customers_df: pd.DataFrame,
    products_df: pd.DataFrame,
    orders_df: pd.DataFrame,
    order_items_df: pd.DataFrame,
    payments_df: pd.DataFrame,
) -> None:
    """Write all entity files for one run date."""
    date_str = run_date.isoformat()
    customers_df.to_csv(output_dir / f"{date_str}-customers.csv", index=False)
    products_df.to_csv(output_dir / f"{date_str}-products.csv", index=False)
    orders_df.to_csv(output_dir / f"{date_str}-orders.csv", index=False)
    order_items_df.to_csv(output_dir / f"{date_str}-order_items.csv", index=False)
    payments_df.to_csv(output_dir / f"{date_str}-payments.csv", index=False)

def parse_args(argv: Sequence[str] | None = None) -> GeneratorConfig:
    """Parse CLI args into a GeneratorConfig."""
    parser = argparse.ArgumentParser(
        description="Generate synthetic e-commerce CSV snapshots for a date range."
    )
    parser.add_argument("--num-customers", type=positive_int, default=DEFAULT_NUM_CUSTOMERS)
    parser.add_argument("--num-products", type=positive_int, default=DEFAULT_NUM_PRODUCTS)
    parser.add_argument("--num-orders", type=non_negative_int, default=DEFAULT_NUM_ORDERS)
    parser.add_argument("--start-date", type=parse_iso_date, default=None)
    parser.add_argument("--end-date", type=parse_iso_date, default=date.today())
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
    )

    args = parser.parse_args(argv)
    end_date = args.end_date
    start_date = args.start_date or end_date.replace(day=1)
    if start_date > end_date:
        parser.error("--start-date cannot be after --end-date.")

    return GeneratorConfig(
        num_customers=args.num_customers,
        num_products=args.num_products,
        num_orders=args.num_orders,
        start_date=start_date,
        end_date=end_date,
        output_dir=Path(args.output_dir),
        seed=args.seed,
        log_level=args.log_level,
    )

def run_generation(config: GeneratorConfig) -> None:
    """Generate dataset snapshots according to config."""
    rng = random.Random(config.seed)
    config.output_dir.mkdir(parents=True, exist_ok=True)

    date_array = build_date_range(config.start_date, config.end_date)
    orders_per_day = allocate_orders(config.num_orders, len(date_array))

    logger.info(
        "Starting generation: start=%s end=%s days=%d num_customers=%d num_products=%d num_orders=%d seed=%d output=%s",
        config.start_date.isoformat(),
        config.end_date.isoformat(),
        len(date_array),
        config.num_customers,
        config.num_products,
        config.num_orders,
        config.seed,
        config.output_dir,
    )

    customers_df = generate_customers(config.num_customers, rng, config.end_date)
    products_df = generate_products(config.num_products, rng)

    customers_records = customers_df.to_dict(orient="records")
    customer_weights = build_customer_weights(customers_df)
    products_records = products_df.to_dict(orient="records")

    run_token = (
        f"seed={config.seed}|start={config.start_date.isoformat()}|"
        f"end={config.end_date.isoformat()}|customers={config.num_customers}|"
        f"products={config.num_products}|orders={config.num_orders}"
    )

    order_id_counter = 1
    order_item_id_counter = 1

    for run_date, n_orders in zip(date_array, orders_per_day):
        (
            orders_df,
            order_items_df,
            payments_df,
            order_id_counter,
            order_item_id_counter,
        ) = generate_orders_for_date(
            customers_records=customers_records,
            customer_weights=customer_weights,
            products_records=products_records,
            n_orders=n_orders,
            target_date=run_date,
            start_order_id=order_id_counter,
            start_order_item_id=order_item_id_counter,
            rng=rng,
            run_token=run_token,
        )

        validate_daily_data(run_date, orders_df, order_items_df, payments_df)
        write_daily_files(
            config.output_dir,
            run_date,
            customers_df,
            products_df,
            orders_df,
            order_items_df,
            payments_df,
        )

        logger.info(
            "[%s] orders=%d items=%d payments=%d -> saved",
            run_date.isoformat(),
            len(orders_df),
            len(order_items_df),
            len(payments_df),
        )

    logger.info(
        "Generation completed: %d days, %d total orders, output=%s",
        len(date_array),
        sum(orders_per_day),
        config.output_dir.resolve(),
    )

def main(argv: Sequence[str] | None = None) -> None:
    """CLI entrypoint."""
    config = parse_args(argv)
    configure_logging(config.log_level)
    run_generation(config)

if __name__ == "__main__":
    main()
