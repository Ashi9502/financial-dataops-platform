from io import BytesIO
import os
from pathlib import Path

import boto3
import pandas as pd
import psycopg
from botocore.config import Config


PIPELINE_NAME = "transactions_incremental"


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

    # Runtime environment wins over .env.
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


def get_s3_client(env):
    return boto3.client(
        "s3",
        endpoint_url=env.get(
            "S3_ENDPOINT_URL",
            "http://localhost:8333",
        ),
        aws_access_key_id=env["S3_ACCESS_KEY"],
        aws_secret_access_key=env["S3_SECRET_KEY"],
        region_name="us-east-1",
        config=Config(
            s3={"addressing_style": "path"}
        ),
    )


def main():
    env = read_env()
    run_id = None

    try:
        # 1. Start run + read durable watermark.
        with psycopg.connect(warehouse_conninfo(env)) as warehouse:
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

                cur.execute(
                    """
                    SELECT
                        last_watermark,
                        last_transaction_id
                    FROM control.pipeline_watermarks
                    WHERE pipeline_name = %s
                    """,
                    (PIPELINE_NAME,),
                )

                watermark = cur.fetchone()

                if watermark is None:
                    raise RuntimeError(
                        f"Missing watermark for {PIPELINE_NAME}"
                    )

                last_watermark, last_transaction_id = watermark

            warehouse.commit()

        print(f"run_id={run_id}")
        print(f"from_watermark={last_watermark}")
        print(f"from_transaction_id={last_transaction_id}")

        # 2. Extract rows after composite watermark.
        with psycopg.connect(source_conninfo(env)) as source:
            with source.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        transaction_id,
                        customer_id,
                        merchant_id,
                        transaction_ts,
                        amount,
                        currency,
                        status,
                        payment_method,
                        created_at,
                        updated_at
                    FROM transactions
                    WHERE
                        (updated_at, transaction_id) > (%s, %s)
                    ORDER BY
                        updated_at,
                        transaction_id
                    """,
                    (
                        last_watermark,
                        last_transaction_id,
                    ),
                )

                columns = [desc.name for desc in cur.description]
                rows = cur.fetchall()

        row_count = len(rows)

        print(f"rows_extracted={row_count}")

        # No-data run is still successful.
        if row_count == 0:
            with psycopg.connect(warehouse_conninfo(env)) as warehouse:
                with warehouse.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE control.pipeline_runs
                        SET
                            completed_at = NOW(),
                            status = 'SUCCESS',
                            rows_read = 0,
                            rows_written = 0
                        WHERE run_id = %s
                        """,
                        (run_id,),
                    )

                warehouse.commit()

            print("no_new_rows=true")
            print("status=SUCCESS")
            return

        df = pd.DataFrame(rows, columns=columns)

        end_watermark = df.iloc[-1]["updated_at"]
        end_transaction_id = int(
            df.iloc[-1]["transaction_id"]
        )

        # 3. Immutable/deterministic batch path.
        start_ts = last_watermark.strftime(
            "%Y%m%dT%H%M%S%fZ"
        )

        end_ts = end_watermark.strftime(
            "%Y%m%dT%H%M%S%fZ"
        )

        object_key = (
            "transactions/"
            f"from_ts={start_ts}/"
            f"from_id={last_transaction_id}/"
            f"to_ts={end_ts}/"
            f"to_id={end_transaction_id}/"
            "transactions.parquet"
        )

        # 4. Serialize to Parquet.
        parquet_buffer = BytesIO()

        df.to_parquet(
            parquet_buffer,
            engine="pyarrow",
            index=False,
        )

        parquet_bytes = parquet_buffer.getvalue()

        # 5. Persist to S3-compatible raw storage.
        s3 = get_s3_client(env)
        bucket = env["S3_BUCKET"]

        s3.put_object(
            Bucket=bucket,
            Key=object_key,
            Body=parquet_bytes,
            ContentType="application/octet-stream",
        )

        metadata = s3.head_object(
            Bucket=bucket,
            Key=object_key,
        )

        object_size = metadata["ContentLength"]

        print(f"s3_bucket={bucket}")
        print(f"s3_key={object_key}")
        print(f"object_size_bytes={object_size}")

        # 6. Advance watermark only AFTER durable object write.
        with psycopg.connect(warehouse_conninfo(env)) as warehouse:
            with warehouse.cursor() as cur:
                cur.execute(
                    """
                    UPDATE control.pipeline_watermarks
                    SET
                        last_watermark = %s,
                        last_transaction_id = %s,
                        updated_at = NOW()
                    WHERE pipeline_name = %s
                    """,
                    (
                        end_watermark,
                        end_transaction_id,
                        PIPELINE_NAME,
                    ),
                )

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
                        row_count,
                        row_count,
                        run_id,
                    ),
                )

            warehouse.commit()

        print(f"to_watermark={end_watermark}")
        print(f"to_transaction_id={end_transaction_id}")
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
