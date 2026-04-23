import random
import uuid
from datetime import datetime, timedelta
import pandas as pd

random.seed(42)

NUM_CUSTOMERS = 1000
NUM_PRODUCTS = 300
NUM_ORDERS = 5000

states = {
    "SP": ["Sao Paulo", "Campinas", "Santos", "Ribeirao Preto"],
    "RJ": ["Rio de Janeiro", "Niteroi", "Petropolis"],
    "MG": ["Belo Horizonte", "Uberlandia", "Juiz de Fora"],
    "BA": ["Salvador", "Feira de Santana"],
    "PE": ["Recife", "Olinda"],
    "CE": ["Fortaleza", "Caucaia"]
}

customer_segments = ["regular", "premium", "vip"]

categories = {
    "electronics": ["Headphone", "Notebook", "Mouse", "Keyboard", "Monitor"],
    "home": ["Chair", "Table", "Lamp", "Sofa", "Shelf"],
    "fashion": ["Tshirt", "Jeans", "Sneakers", "Jacket", "Dress"],
    "beauty": ["Perfume", "Shampoo", "Cream", "Lipstick"],
    "sports": ["Ball", "Bike", "Dumbbell", "Mat"]
}

brands = ["Alpha", "Beta", "Gamma", "Delta", "Prime", "Neo"]

sales_channels = ["site", "app", "pdv"]

order_statuses = ["delivered", "shipped", "processing", "cancelled"]

payment_methods = ["credit_card", "pix", "boleto", "debit_card"]

def get_date_array():
    today = datetime.today()
    start_of_month = today.replace(day=1)
    dates = []
    curr = start_of_month
    while curr <= today:
        dates.append(curr)
        curr += timedelta(days=1)
    return dates

def random_time_for_date(date_obj):
    return date_obj + timedelta(seconds=random.randint(0, 86399))

def weighted_choice(choices, weights):
    return random.choices(choices, weights=weights, k=1)[0]

def seasonality_multiplier(dt):
    if dt.month in [11, 12]:
        return 1.4
    if dt.month in [1, 7]:
        return 0.9
    return 1.0

def generate_customers(n):
    rows = []
    for i in range(1, n + 1):
        state = random.choice(list(states.keys()))
        city = random.choice(states[state])
        segment = weighted_choice(customer_segments, [0.7, 0.25, 0.05])
        signup_delta = random.randint(10, 1000)
        signup_date_obj = datetime.today() - timedelta(days=signup_delta)
        
        age = random.randint(18, 75)
        gender = random.choice(["M", "F", "Other"])
        device = weighted_choice(["Mobile", "Desktop", "Tablet"], [0.6, 0.35, 0.05])

        rows.append({
            "customer_id": i,
            "customer_name": f"Customer_{i}",
            "age": age,
            "gender": gender,
            "city": city,
            "state": state,
            "signup_date": signup_date_obj.date(),
            "customer_segment": segment,
            "device_preference": device
        })
    return pd.DataFrame(rows)

def generate_products(n):
    rows = []
    product_id = 1
    for _ in range(n):
        category = random.choice(list(categories.keys()))
        product_base = random.choice(categories[category])
        brand = random.choice(brands)

        base_price = {
            "electronics": random.uniform(80, 5000),
            "home": random.uniform(50, 2000),
            "fashion": random.uniform(30, 600),
            "beauty": random.uniform(20, 300),
            "sports": random.uniform(40, 2500)
        }[category]

        cost_price = round(base_price * random.uniform(0.45, 0.75), 2)
        unit_price = round(base_price, 2)
        
        colors = ["Black", "White", "Silver", "Blue", "Red", "Green"]
        chosen_color = random.choice(colors)
        weight_kg_val = round(random.uniform(0.1, 15.0), 2)

        rows.append({
            "product_id": product_id,
            "product_name": f"{brand}_{product_base}_{product_id}",
            "color": chosen_color,
            "weight_kg": weight_kg_val,
            "category": category,
            "brand": brand,
            "unit_price": unit_price,
            "cost_price": cost_price
        })
        product_id += 1
    return pd.DataFrame(rows)

def choose_customer(customers_df):
    weights = []
    for seg in customers_df["customer_segment"]:
        if seg == "vip":
            weights.append(8)
        elif seg == "premium":
            weights.append(4)
        else:
            weights.append(1)
    return customers_df.sample(n=1, weights=weights).iloc[0]

def generate_orders_for_date(customers_df, products_df, n_orders, target_date, start_order_id, start_order_item_id):
    orders = []
    order_items = []
    payments = []

    order_id = start_order_id
    order_item_id = start_order_item_id

    for _ in range(n_orders):
        customer = choose_customer(customers_df)
        order_dt = random_time_for_date(target_date)

        status = weighted_choice(order_statuses, [0.78, 0.1, 0.08, 0.04])
        channel = weighted_choice(sales_channels, [0.55, 0.30, 0.15])

        shipping_cost = round(random.uniform(8, 60), 2)
        coupon_code = random.choice([None, None, None, "DISC10", "SHIP15", "VIP20"])

        num_items = weighted_choice([1, 2, 3, 4, 5], [0.50, 0.25, 0.15, 0.07, 0.03])
        chosen_products = products_df.sample(n=num_items, replace=False)

        order_total = 0.0

        for _, product in chosen_products.iterrows():
            quantity = weighted_choice([1, 2, 3, 4], [0.65, 0.22, 0.09, 0.04])

            seasonal = seasonality_multiplier(order_dt)
            price_variation = random.uniform(0.95, 1.10)
            unit_price = round(product["unit_price"] * seasonal * price_variation, 2)

            discount_pct = random.choice([0, 0, 0, 0.05, 0.10, 0.15])
            if customer["customer_segment"] == "vip":
                discount_pct = max(discount_pct, random.choice([0.05, 0.10, 0.15]))

            gross_value = unit_price * quantity
            discount_value = round(gross_value * discount_pct, 2)
            total_price = round(gross_value - discount_value, 2)

            order_items.append({
                "order_item_id": order_item_id,
                "order_id": order_id,
                "product_id": int(product["product_id"]),
                "quantity": quantity,
                "unit_price": unit_price,
                "discount": discount_value,
                "total_price": total_price
            })

            order_total += total_price
            order_item_id += 1

        if status == "cancelled":
            paid_amount = 0.0
            payment_status = "refused"
        else:
            paid_amount = round(order_total + shipping_cost, 2)
            payment_status = weighted_choice(["paid", "pending"], [0.92, 0.08])

        orders.append({
            "order_id": order_id,
            "customer_id": int(customer["customer_id"]),
            "order_date": order_dt,
            "order_status": status,
            "sales_channel": channel,
            "coupon_code": coupon_code,
            "shipping_cost": shipping_cost
        })

        payment_method = weighted_choice(payment_methods, [0.45, 0.30, 0.15, 0.10])
        installments = random.choice([1, 1, 1, 2, 3, 4, 6, 10]) if payment_method == "credit_card" else 1

        payments.append({
            "payment_id": str(uuid.uuid4()),
            "order_id": order_id,
            "payment_method": payment_method,
            "installments": installments,
            "payment_status": payment_status,
            "paid_amount": paid_amount
        })
        
        order_id += 1

    return (
        pd.DataFrame(orders),
        pd.DataFrame(order_items),
        pd.DataFrame(payments),
        order_id,
        order_item_id
    )

def main():
    import os
    if not os.path.exists("random_date"):
        os.makedirs("random_date")

    # Generate the master customer and product base (fixed seed = same data)
    customers_df = generate_customers(NUM_CUSTOMERS)
    products_df = generate_products(NUM_PRODUCTS)

    date_array = get_date_array()

    daily_orders = max(1, NUM_ORDERS // len(date_array))

    order_id_counter = 1
    order_item_id_counter = 1

    for db_date in date_array:
        date_str = db_date.strftime('%Y-%m-%d')

        # Daily snapshot: save customers and products for every date
        # This follows the Data Lake "daily snapshot" pattern, allowing
        # point-in-time reconstruction of the full dataset.
        customers_df.to_csv(f"random_date/{date_str}-customers.csv", index=False)
        products_df.to_csv(f"random_date/{date_str}-products.csv", index=False)

        orders_df, order_items_df, payments_df, order_id_counter, order_item_id_counter = generate_orders_for_date(
            customers_df, products_df, daily_orders, db_date, order_id_counter, order_item_id_counter
        )

        orders_df.to_csv(f"random_date/{date_str}-orders.csv", index=False)
        order_items_df.to_csv(f"random_date/{date_str}-order_items.csv", index=False)
        payments_df.to_csv(f"random_date/{date_str}-payments.csv", index=False)

        print(f"  [{date_str}] customers, products, orders, order_items, payments -> saved")

    print(f"\nAll files generated from {date_array[0].strftime('%Y-%m-%d')} to {date_array[-1].strftime('%Y-%m-%d')}")

if __name__ == "__main__":
    main()