import os
from pathlib import Path
from urllib.parse import quote_plus

import great_expectations as gx


def read_env(path=".env"):
    values = {}

    env_file = Path(path)

    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()

            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            values[key] = value

    values.update(os.environ)

    return values


def postgres_connection_string(env):
    user = quote_plus(env["WAREHOUSE_POSTGRES_USER"])
    password = quote_plus(env["WAREHOUSE_POSTGRES_PASSWORD"])

    host = env.get(
        "WAREHOUSE_POSTGRES_HOST",
        "localhost",
    )

    port = env.get(
        "WAREHOUSE_POSTGRES_PORT",
        "5434",
    )

    database = env["WAREHOUSE_POSTGRES_DB"]

    return (
        f"postgresql+psycopg2://"
        f"{user}:{password}"
        f"@{host}:{port}/{database}"
    )


def add_not_null(suite, column):
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToNotBeNull(
            column=column,
            severity="critical",
        )
    )


def main():
    env = read_env()

    context = gx.get_context(
        mode="ephemeral",
    )

    datasource = context.data_sources.add_postgres(
        name="financial_warehouse",
        connection_string=postgres_connection_string(env),
    )

    # Query assets let us target schema-qualified dbt models directly.
    fact_asset = datasource.add_query_asset(
        name="fact_transactions",
        query="""
            SELECT *
            FROM marts.fact_transactions
        """,
    )

    mart_asset = datasource.add_query_asset(
        name="mart_merchant_daily",
        query="""
            SELECT *
            FROM marts.mart_merchant_daily
        """,
    )

    fact_batch = fact_asset.add_batch_definition_whole_table(
        name="fact_transactions_whole_table",
    )

    mart_batch = mart_asset.add_batch_definition_whole_table(
        name="mart_merchant_daily_whole_table",
    )

    # ---------------------------------------------------------
    # fact_transactions quality contract
    # ---------------------------------------------------------

    fact_suite = context.suites.add(
        gx.ExpectationSuite(
            name="fact_transactions_quality",
        )
    )

    fact_suite.add_expectation(
        gx.expectations.ExpectTableRowCountToBeBetween(
            min_value=1,
            severity="critical",
        )
    )

    add_not_null(
        fact_suite,
        "transaction_id",
    )

    fact_suite.add_expectation(
        gx.expectations.ExpectColumnValuesToBeUnique(
            column="transaction_id",
            severity="critical",
        )
    )

    add_not_null(
        fact_suite,
        "customer_key",
    )

    add_not_null(
        fact_suite,
        "merchant_key",
    )

    add_not_null(
        fact_suite,
        "amount",
    )

    fact_suite.add_expectation(
        gx.expectations.ExpectColumnValuesToBeBetween(
            column="amount",
            min_value=0,
            severity="critical",
        )
    )

    add_not_null(
        fact_suite,
        "signed_amount",
    )

    add_not_null(
        fact_suite,
        "transaction_status",
    )

    fact_suite.add_expectation(
        gx.expectations.ExpectColumnValuesToBeInSet(
            column="transaction_status",
            value_set=[
                "completed",
                "refunded",
            ],
            severity="critical",
        )
    )

    # ---------------------------------------------------------
    # mart_merchant_daily quality contract
    # ---------------------------------------------------------

    mart_suite = context.suites.add(
        gx.ExpectationSuite(
            name="mart_merchant_daily_quality",
        )
    )

    mart_suite.add_expectation(
        gx.expectations.ExpectTableRowCountToBeBetween(
            min_value=1,
            severity="critical",
        )
    )

    add_not_null(
        mart_suite,
        "transaction_date",
    )

    add_not_null(
        mart_suite,
        "merchant_key",
    )

    add_not_null(
        mart_suite,
        "currency",
    )

    add_not_null(
        mart_suite,
        "transaction_count",
    )

    mart_suite.add_expectation(
        gx.expectations.ExpectColumnValuesToBeBetween(
            column="transaction_count",
            min_value=1,
            severity="critical",
        )
    )

    mart_suite.add_expectation(
        gx.expectations.ExpectColumnValuesToBeBetween(
            column="completed_transaction_count",
            min_value=0,
            severity="critical",
        )
    )

    mart_suite.add_expectation(
        gx.expectations.ExpectColumnValuesToBeBetween(
            column="refunded_transaction_count",
            min_value=0,
            severity="critical",
        )
    )

    add_not_null(
        mart_suite,
        "net_transaction_amount",
    )

    fact_validation = context.validation_definitions.add(
        gx.ValidationDefinition(
            name="validate_fact_transactions",
            data=fact_batch,
            suite=fact_suite,
        )
    )

    mart_validation = context.validation_definitions.add(
        gx.ValidationDefinition(
            name="validate_mart_merchant_daily",
            data=mart_batch,
            suite=mart_suite,
        )
    )

    checkpoint = context.checkpoints.add(
        gx.Checkpoint(
            name="financial_quality_gate",
            validation_definitions=[
                fact_validation,
                mart_validation,
            ],
        )
    )

    result = checkpoint.run()

    print(result.describe())
    print(
        "quality_gate_success =",
        result.success,
    )

    if result.success is not True:
        print("status=FAILED")
        raise SystemExit(1)

    print("status=SUCCESS")


if __name__ == "__main__":
    main()
