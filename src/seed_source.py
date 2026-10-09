import argparse
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg


def read_env(path=".env"):
    values = {}
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value
    return values


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--customers", type=int, default=500)
    parser.add_argument("--merchants", type=int, default=50)
    parser.add_argument("--transactions", type=int, default=10000)
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()

    env = read_env()

    conninfo = (
        f"host=localhost port=5433 "
        f"dbname={env['SOURCE_POSTGRES_DB']} "
        f"user={env['SOURCE_POSTGRES_USER']} "
        f"password={env['SOURCE_POSTGRES_PASSWORD']}"
    )

    rng = random.Random(42)

    countries = ["IN", "US", "GB", "AE", "SG"]
    categories = [
        "grocery",
        "electronics",
        "fashion",
        "travel",
        "food",
        "health",
        "entertainment",
    ]
    payment_methods = ["card", "upi", "wallet", "bank_transfer"]
    statuses = ["completed", "completed", "completed", "completed", "refunded"]

    with psycopg.connect(conninfo) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM transactions")
            existing = cur.fetchone()[0]

            if existing and not args.reset:
                raise SystemExit(
                    f"Source already contains {existing} transactions. "
                    "Use --reset only when you intentionally want a fresh dataset."
                )

            if args.reset:
                cur.execute(
                    "TRUNCATE transactions, merchants, customers "
                    "RESTART IDENTITY CASCADE"
                )

            customers = []
            for i in range(1, args.customers + 1):
                customers.append(
                    (
                        f"Customer {i:04d}",
                        f"customer{i:04d}@example.com",
                        rng.choice(countries),
                    )
                )

            cur.executemany(
                """
                INSERT INTO customers (
                    full_name,
                    email,
                    country_code
                )
                VALUES (%s, %s, %s)
                """,
                customers,
            )

            merchants = []
            for i in range(1, args.merchants + 1):
                merchants.append(
                    (
                        f"Merchant {i:03d}",
                        rng.choice(categories),
                        rng.choice(countries),
                    )
                )

            cur.executemany(
                """
                INSERT INTO merchants (
                    merchant_name,
                    merchant_category,
                    country_code
                )
                VALUES (%s, %s, %s)
                """,
                merchants,
            )

            base_ts = datetime.now(timezone.utc) - timedelta(days=30)

            transactions = []
            for _ in range(args.transactions):
                transaction_ts = base_ts + timedelta(
                    seconds=rng.randint(0, 30 * 24 * 60 * 60)
                )

                transactions.append(
                    (
                        rng.randint(1, args.customers),
                        rng.randint(1, args.merchants),
                        transaction_ts,
                        round(rng.uniform(50, 25000), 2),
                        "INR",
                        rng.choice(statuses),
                        rng.choice(payment_methods),
                    )
                )

            cur.executemany(
                """
                INSERT INTO transactions (
                    customer_id,
                    merchant_id,
                    transaction_ts,
                    amount,
                    currency,
                    status,
                    payment_method
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                transactions,
            )

        conn.commit()

    print("Seed complete")
    print(f"customers={args.customers}")
    print(f"merchants={args.merchants}")
    print(f"transactions={args.transactions}")
    print("random_seed=42")


if __name__ == "__main__":
    main()
