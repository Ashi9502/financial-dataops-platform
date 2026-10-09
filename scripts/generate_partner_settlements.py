import argparse
import csv
import os
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import psycopg


FEE_RATE = Decimal("0.015")
MONEY_QUANTUM = Decimal("0.01")


def load_env_file(path=".env"):
    env_path = Path(path)

    if not env_path.exists():
        return

    for line in env_path.read_text().splitlines():
        line = line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)

        os.environ.setdefault(
            key.strip(),
            value.strip(),
        )


def money(value):
    return Decimal(value).quantize(
        MONEY_QUANTUM,
        rounding=ROUND_HALF_UP,
    )


def settlement_id(
    settlement_date,
    merchant_id,
    currency,
):
    return (
        f"STL-"
        f"{settlement_date:%Y%m%d}-"
        f"{merchant_id:06d}-"
        f"{currency}"
    )


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--output",
        default=(
            "data/raw/partner_settlements/"
            "settlements_baseline.csv"
        ),
    )

    args = parser.parse_args()

    load_env_file()

    conn_kwargs = {
        "host": os.getenv(
            "WAREHOUSE_POSTGRES_HOST",
            "localhost",
        ),
        "port": int(
            os.getenv(
                "WAREHOUSE_POSTGRES_PORT",
                "5434",
            )
        ),
        "dbname": os.environ[
            "WAREHOUSE_POSTGRES_DB"
        ],
        "user": os.environ[
            "WAREHOUSE_POSTGRES_USER"
        ],
        "password": os.environ[
            "WAREHOUSE_POSTGRES_PASSWORD"
        ],
    }

    query = """
        SELECT
            transaction_date AS settlement_date,
            merchant_id,
            currency,
            COUNT(*) AS transaction_count,
            SUM(amount) AS gross_amount
        FROM marts.fact_transactions
        WHERE transaction_status = 'completed'
        GROUP BY
            transaction_date,
            merchant_id,
            currency
        ORDER BY
            transaction_date,
            merchant_id,
            currency
    """

    with psycopg.connect(**conn_kwargs) as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()

    output_path = Path(args.output)
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    total_transactions = 0
    total_gross = Decimal("0.00")
    total_fees = Decimal("0.00")
    total_net = Decimal("0.00")

    with output_path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as handle:
        writer = csv.writer(handle)

        writer.writerow(
            [
                "settlement_id",
                "merchant_id",
                "settlement_date",
                "currency",
                "transaction_count",
                "gross_amount",
                "fees",
                "net_amount",
            ]
        )

        for (
            settlement_date,
            merchant_id,
            currency,
            transaction_count,
            gross_amount,
        ) in rows:

            gross = money(gross_amount)

            fees = money(
                gross * FEE_RATE
            )

            net = money(
                gross - fees
            )

            writer.writerow(
                [
                    settlement_id(
                        settlement_date,
                        merchant_id,
                        currency,
                    ),
                    merchant_id,
                    settlement_date.isoformat(),
                    currency,
                    transaction_count,
                    f"{gross:.2f}",
                    f"{fees:.2f}",
                    f"{net:.2f}",
                ]
            )

            total_transactions += transaction_count
            total_gross += gross
            total_fees += fees
            total_net += net

    print("partner_settlement_generation=SUCCESS")
    print(f"output={output_path}")
    print(f"settlement_rows={len(rows)}")
    print(
        f"completed_transactions="
        f"{total_transactions}"
    )
    print(
        f"gross_amount="
        f"{money(total_gross):.2f}"
    )
    print(
        f"fees="
        f"{money(total_fees):.2f}"
    )
    print(
        f"net_amount="
        f"{money(total_net):.2f}"
    )
    print(
        f"fee_rate="
        f"{FEE_RATE}"
    )


if __name__ == "__main__":
    main()
