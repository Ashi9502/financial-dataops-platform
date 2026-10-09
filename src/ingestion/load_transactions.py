from io import BytesIO
import os
from pathlib import Path

import boto3
import pandas as pd
import psycopg
from botocore.config import Config


PIPELINE_NAME = "transactions_raw_load"
PREFIX = "transactions/"


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

    s3 = get_s3_client(env)
    bucket = env["S3_BUCKET"]

    response = s3.list_objects_v2(
        Bucket=bucket,
        Prefix=PREFIX,
    )

    objects = sorted(
        [
            obj
            for obj in response.get("Contents", [])
            if obj["Key"].endswith(".parquet")
        ],
        key=lambda obj: obj["Key"],
    )

    files_loaded = 0
    files_skipped = 0
    rows_read = 0

    for obj in objects:
        object_key = obj["Key"]

        with psycopg.connect(
            warehouse_conninfo(env)
        ) as warehouse:
            with warehouse.cursor() as cur:

                cur.execute(
                    """
                    SELECT 1
                    FROM control.ingested_files
                    WHERE
                        pipeline_name = %s
                        AND object_key = %s
                    """,
                    (
                        PIPELINE_NAME,
                        object_key,
                    ),
                )

                if cur.fetchone():
                    print(f"skip={object_key}")
                    files_skipped += 1
                    continue

        result = s3.get_object(
            Bucket=bucket,
            Key=object_key,
        )

        body = result["Body"].read()

        df = pd.read_parquet(
            BytesIO(body),
            engine="pyarrow",
        )

        required_columns = {
            "transaction_id",
            "customer_id",
            "merchant_id",
            "transaction_ts",
            "amount",
            "currency",
            "status",
            "payment_method",
            "created_at",
            "updated_at",
        }

        missing = required_columns - set(df.columns)

        if missing:
            raise RuntimeError(
                f"{object_key} missing columns: "
                f"{sorted(missing)}"
            )

        records = []

        for row in df.itertuples(index=False):
            records.append(
                (
                    int(row.transaction_id),
                    int(row.customer_id),
                    int(row.merchant_id),
                    row.transaction_ts,
                    row.amount,
                    row.currency,
                    row.status,
                    row.payment_method,
                    row.created_at,
                    row.updated_at,
                    object_key,
                )
            )

        with psycopg.connect(
            warehouse_conninfo(env)
        ) as warehouse:

            with warehouse.cursor() as cur:

                cur.executemany(
                    """
                    INSERT INTO raw.transactions (
                        transaction_id,
                        customer_id,
                        merchant_id,
                        transaction_ts,
                        amount,
                        currency,
                        status,
                        payment_method,
                        source_created_at,
                        source_updated_at,
                        source_object_key
                    )
                    VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (transaction_id)
                    DO UPDATE SET
                        customer_id = EXCLUDED.customer_id,
                        merchant_id = EXCLUDED.merchant_id,
                        transaction_ts = EXCLUDED.transaction_ts,
                        amount = EXCLUDED.amount,
                        currency = EXCLUDED.currency,
                        status = EXCLUDED.status,
                        payment_method = EXCLUDED.payment_method,
                        source_created_at = EXCLUDED.source_created_at,
                        source_updated_at = EXCLUDED.source_updated_at,
                        source_object_key = EXCLUDED.source_object_key,
                        loaded_at = NOW()
                    WHERE
                        EXCLUDED.source_updated_at
                        >= raw.transactions.source_updated_at
                    """,
                    records,
                )

                cur.execute(
                    """
                    INSERT INTO control.ingested_files (
                        pipeline_name,
                        object_key,
                        etag,
                        row_count
                    )
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        PIPELINE_NAME,
                        object_key,
                        obj.get("ETag", "").strip('"'),
                        len(records),
                    ),
                )

            warehouse.commit()

        print(
            f"loaded={object_key} "
            f"rows={len(records)}"
        )

        files_loaded += 1
        rows_read += len(records)

    with psycopg.connect(
        warehouse_conninfo(env)
    ) as warehouse:

        with warehouse.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM raw.transactions"
            )

            raw_count = cur.fetchone()[0]

    print(f"files_loaded={files_loaded}")
    print(f"files_skipped={files_skipped}")
    print(f"rows_read={rows_read}")
    print(f"raw_transaction_count={raw_count}")
    print("status=SUCCESS")


if __name__ == "__main__":
    main()
