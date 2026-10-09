import os
from pathlib import Path

import psycopg


PIPELINE_NAME = "reference_data_sync"


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


def source_conninfo(env):
    return (
        f"host={env.get('SOURCE_POSTGRES_HOST', 'localhost')} "
        f"port={env.get('SOURCE_POSTGRES_PORT', '5433')} "
        f"dbname={env['SOURCE_POSTGRES_DB']} "
        f"user={env['SOURCE_POSTGRES_USER']} "
        f"password={env['SOURCE_POSTGRES_PASSWORD']}"
    )


def warehouse_conninfo(env):
    return (
        f"host={env.get('WAREHOUSE_POSTGRES_HOST', 'localhost')} "
        f"port={env.get('WAREHOUSE_POSTGRES_PORT', '5434')} "
        f"dbname={env['WAREHOUSE_POSTGRES_DB']} "
        f"user={env['WAREHOUSE_POSTGRES_USER']} "
        f"password={env['WAREHOUSE_POSTGRES_PASSWORD']}"
    )


def main():
    env = read_env()
    run_id = None

    try:
        with psycopg.connect(
            warehouse_conninfo(env)
        ) as warehouse:
            with warehouse.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO control.pipeline_runs (
                        pipeline_name,
                        status
                    )
                    VALUES (%s, 'RUNNING')
                    RETURNING run_id
                    """,
                    (PIPELINE_NAME,),
                )

                run_id = cur.fetchone()[0]

            warehouse.commit()

        with psycopg.connect(
            source_conninfo(env)
        ) as source:
            with source.cursor() as cur:

                cur.execute(
                    """
                    SELECT
                        customer_id,
                        full_name,
                        email,
                        country_code,
                        created_at,
                        updated_at
                    FROM customers
                    ORDER BY customer_id
                    """
                )

                customers = cur.fetchall()

                cur.execute(
                    """
                    SELECT
                        merchant_id,
                        merchant_name,
                        merchant_category,
                        country_code,
                        active,
                        created_at,
                        updated_at
                    FROM merchants
                    ORDER BY merchant_id
                    """
                )

                merchants = cur.fetchall()

        with psycopg.connect(
            warehouse_conninfo(env)
        ) as warehouse:
            with warehouse.cursor() as cur:

                cur.executemany(
                    """
                    INSERT INTO raw.customers (
                        customer_id,
                        full_name,
                        email,
                        country_code,
                        source_created_at,
                        source_updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (customer_id)
                    DO UPDATE SET
                        full_name = EXCLUDED.full_name,
                        email = EXCLUDED.email,
                        country_code = EXCLUDED.country_code,
                        source_created_at = EXCLUDED.source_created_at,
                        source_updated_at = EXCLUDED.source_updated_at,
                        loaded_at = NOW()
                    WHERE
                        EXCLUDED.source_updated_at
                        >= raw.customers.source_updated_at
                    """,
                    customers,
                )

                cur.executemany(
                    """
                    INSERT INTO raw.merchants (
                        merchant_id,
                        merchant_name,
                        merchant_category,
                        country_code,
                        active,
                        source_created_at,
                        source_updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (merchant_id)
                    DO UPDATE SET
                        merchant_name = EXCLUDED.merchant_name,
                        merchant_category = EXCLUDED.merchant_category,
                        country_code = EXCLUDED.country_code,
                        active = EXCLUDED.active,
                        source_created_at = EXCLUDED.source_created_at,
                        source_updated_at = EXCLUDED.source_updated_at,
                        loaded_at = NOW()
                    WHERE
                        EXCLUDED.source_updated_at
                        >= raw.merchants.source_updated_at
                    """,
                    merchants,
                )

                total_rows = len(customers) + len(merchants)

                cur.execute(
                    """
                    UPDATE control.pipeline_runs
                    SET
                        completed_at = NOW(),
                        status = 'SUCCESS',
                        rows_read = %s,
                        rows_written = %s
                    WHERE run_id = %s
                    """,
                    (
                        total_rows,
                        total_rows,
                        run_id,
                    ),
                )

            warehouse.commit()

        print(f"customers_synced={len(customers)}")
        print(f"merchants_synced={len(merchants)}")
        print("status=SUCCESS")

    except Exception as exc:
        if run_id is not None:
            try:
                with psycopg.connect(
                    warehouse_conninfo(env)
                ) as warehouse:
                    with warehouse.cursor() as cur:
                        cur.execute(
                            """
                            UPDATE control.pipeline_runs
                            SET
                                completed_at = NOW(),
                                status = 'FAILED',
                                error_message = %s
                            WHERE run_id = %s
                            """,
                            (
                                str(exc),
                                run_id,
                            ),
                        )

                    warehouse.commit()
            except Exception:
                pass

        raise


if __name__ == "__main__":
    main()
