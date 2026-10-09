import csv
from copy import deepcopy
from decimal import Decimal
from pathlib import Path


BASELINE = Path(
    "data/raw/partner_settlements/"
    "settlements_baseline.csv"
)

OUTPUT_DIR = Path(
    "data/raw/partner_settlements"
)

FIELDNAMES = [
    "settlement_id",
    "merchant_id",
    "settlement_date",
    "currency",
    "transaction_count",
    "gross_amount",
    "fees",
    "net_amount",
]


def read_baseline():
    with BASELINE.open(
        newline="",
        encoding="utf-8",
    ) as handle:
        return list(csv.DictReader(handle))


def write_scenario(name, rows):
    path = OUTPUT_DIR / f"settlements_{name}.csv"

    with path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=FIELDNAMES,
        )

        writer.writeheader()
        writer.writerows(rows)

    print(
        f"scenario={name} "
        f"rows={len(rows)} "
        f"output={path}"
    )


def main():
    baseline = read_baseline()

    if len(baseline) < 3:
        raise RuntimeError(
            "Baseline settlement file is too small."
        )

    # -------------------------------------------------
    # 1. AMOUNT_MISMATCH
    # Keep count unchanged.
    # Increase gross and net by the same amount so
    # partner-side gross - fees = net still holds.
    # -------------------------------------------------
    amount_rows = deepcopy(baseline)

    amount_target = amount_rows[0]

    amount_target["gross_amount"] = (
        f"{Decimal(amount_target['gross_amount']) + Decimal('10.00'):.2f}"
    )

    amount_target["net_amount"] = (
        f"{Decimal(amount_target['net_amount']) + Decimal('10.00'):.2f}"
    )

    write_scenario(
        "amount_mismatch",
        amount_rows,
    )

    print(
        "amount_mismatch_target="
        f"{amount_target['settlement_id']}"
    )

    # -------------------------------------------------
    # 2. COUNT_MISMATCH
    # Amounts remain unchanged.
    # -------------------------------------------------
    count_rows = deepcopy(baseline)

    count_target = count_rows[1]

    count_target["transaction_count"] = str(
        int(count_target["transaction_count"]) + 1
    )

    write_scenario(
        "count_mismatch",
        count_rows,
    )

    print(
        "count_mismatch_target="
        f"{count_target['settlement_id']}"
    )

    # -------------------------------------------------
    # 3. MISSING_SETTLEMENT
    # Remove one settlement that internal transactions
    # expect to exist.
    # -------------------------------------------------
    missing_settlement_rows = deepcopy(
        baseline
    )

    removed = missing_settlement_rows.pop(2)

    write_scenario(
        "missing_settlement",
        missing_settlement_rows,
    )

    print(
        "missing_settlement_target="
        f"{removed['settlement_id']}"
    )

    # -------------------------------------------------
    # 4. MISSING_TRANSACTION
    # Add one partner settlement at a grain with no
    # matching internal completed transactions.
    #
    # Merchant 1 exists, so the raw FK-style dbt
    # relationship test remains valid.
    # -------------------------------------------------
    missing_transaction_rows = deepcopy(
        baseline
    )

    extra = {
        "settlement_id":
            "STL-20990101-000001-INR-EXTRA",
        "merchant_id": "1",
        "settlement_date": "2099-01-01",
        "currency": "INR",
        "transaction_count": "1",
        "gross_amount": "100.00",
        "fees": "1.50",
        "net_amount": "98.50",
    }

    missing_transaction_rows.append(extra)

    write_scenario(
        "missing_transaction",
        missing_transaction_rows,
    )

    print(
        "missing_transaction_target="
        f"{extra['settlement_id']}"
    )


if __name__ == "__main__":
    main()
