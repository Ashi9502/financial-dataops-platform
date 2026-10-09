import argparse
import csv
import hashlib
import io
import os
from datetime import date
from decimal import Decimal
from pathlib import Path

import boto3
import psycopg
from botocore.config import Config


REQUIRED_COLUMNS = [
    "settlement_id",
    "merchant_id",
    "settlement_date",
    "currency",
    "transaction_count",
    "gross_amount",
    "fees",
    "net_amount",
]


def load_env_file(path=".env"):
    env_path = Path(path)

    if not env_path.exists():
        return

    for line in env_path.read_text().splitlines():
        line = line.strip()

        if (
            not line
            or line.startswith("#")
            or "=" not in line
        ):
            continue

        key, value = line.split("=", 1)

        os.environ.setdefault(
            key.strip(),
            value.strip(),
        )


def warehouse_connection_kwargs():
    return {
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


def s3_client():
    return boto3.client(
        "s3",
        endpoint_url=os.getenv(
            "S3_ENDPOINT_URL",
            "http://localhost:8333",
        ),
        aws_access_key_id=os.environ[
            "S3_ACCESS_KEY"
        ],
        aws_secret_access_key=os.environ[
            "S3_SECRET_KEY"
        ],
        region_name=os.getenv(
            "AWS_REGION",
            "us-east-1",
        ),
        config=Config(
            signature_version="s3v4",
            s3={
                "addressing_style": "path",
            },
        ),
    )


def parse_rows(file_bytes):
    text = file_bytes.decode("utf-8-sig")

    reader = csv.DictReader(
        io.StringIO(text)
    )

    if reader.fieldnames != REQUIRED_COLUMNS:
        raise ValueError(
            "Unexpected settlement columns. "
            f"Expected={REQUIRED_COLUMNS}, "
            f"actual={reader.fieldnames}"
        )

    parsed = []

    # Physical CSV line 1 is the header.
    # First data record is therefore line 2.
    for source_row_number, row in enumerate(
        reader,
        start=2,
    ):
        parsed.append(
            {
                "settlement_id":
                    row["settlement_id"].strip(),
                "merchant_id":
                    int(row["merchant_id"]),
                "settlement_date":
                    date.fromisoformat(
                        row["settlement_date"]
                    ),
                "currency":
                    row["currency"].strip().upper(),
                "transaction_count":
                    int(row["transaction_count"]),
                "gross_amount":
                    Decimal(row["gross_amount"]),
                "fees":
                    Decimal(row["fees"]),
                "net_amount":
                    Decimal(row["net_amount"]),
                "source_row_number":
                    source_row_number,
            }
        )

    return parsed


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--file",
        required=True,
    )

    parser.add_argument(
        "--scenario",
        default="baseline",
    )

    args = parser.parse_args()

    load_env_file()

    file_path = Path(args.file)

    if not file_path.exists():
        raise FileNotFoundError(file_path)

    file_bytes = file_path.read_bytes()

    content_sha256 = hashlib.sha256(
        file_bytes
    ).hexdigest()

    rows = parse_rows(file_bytes)

    object_key = (
        f"settlements/{args.scenario}/"
        f"sha256={content_sha256}/"
        f"settlements.csv"
    )

    bucket = os.environ["S3_BUCKET"]

    s3 = s3_client()

    with psycopg.connect(
        **warehouse_connection_kwargs()
    ) as conn:

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    content_sha256,
                    row_count
                FROM control.settlement_files
                WHERE object_key = %s
                """,
                (object_key,),
            )

            existing = cur.fetchone()

        if existing:
            stored_sha, stored_row_count = existing

            if stored_sha != content_sha256:
                raise RuntimeError(
                    "Existing object key has a "
                    "different SHA-256."
                )

            if stored_row_count != len(rows):
                raise RuntimeError(
                    "Existing ledger row count "
                    "does not match the file."
                )

            head = s3.head_object(
                Bucket=bucket,
                Key=object_key,
            )

            object_sha = head.get(
                "Metadata",
                {},
            ).get("sha256")

            if object_sha != content_sha256:
                raise RuntimeError(
                    "Object-store SHA metadata "
                    "does not match ledger SHA."
                )

            print(
                "settlement_ingestion=SKIPPED"
            )
            print(
                "reason=already_processed"
            )
            print(
                f"object_key={object_key}"
            )
            print(
                f"sha256={content_sha256}"
            )
            print(
                f"row_count={len(rows)}"
            )
            return

        s3.put_object(
            Bucket=bucket,
            Key=object_key,
            Body=file_bytes,
            ContentType="text/csv",
            Metadata={
                "sha256": content_sha256,
            },
        )

        head = s3.head_object(
            Bucket=bucket,
            Key=object_key,
        )

        object_sha = head.get(
            "Metadata",
            {},
        ).get("sha256")

        if object_sha != content_sha256:
            raise RuntimeError(
                "Uploaded object SHA metadata "
                "verification failed."
            )

        with conn.cursor() as cur:

            for row in rows:
                cur.execute(
                    """
                    INSERT INTO raw.settlements (
                        settlement_id,
                        merchant_id,
                        settlement_date,
                        currency,
                        transaction_count,
                        gross_amount,
                        fees,
                        net_amount,
                        scenario,
                        source_object_key,
                        source_file_sha256,
                        source_row_number
                    )
                    VALUES (
                        %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s, %s
                    )
                    """,
                    (
                        row["settlement_id"],
                        row["merchant_id"],
                        row["settlement_date"],
                        row["currency"],
                        row["transaction_count"],
                        row["gross_amount"],
                        row["fees"],
                        row["net_amount"],
                        args.scenario,
                        object_key,
                        content_sha256,
                        row["source_row_number"],
                    ),
                )

            cur.execute(
                """
                INSERT INTO control.settlement_files (
                    object_key,
                    content_sha256,
                    row_count
                )
                VALUES (%s, %s, %s)
                """,
                (
                    object_key,
                    content_sha256,
                    len(rows),
                ),
            )

    print("settlement_ingestion=SUCCESS")
    print(f"object_key={object_key}")
    print(f"sha256={content_sha256}")
    print(f"rows_loaded={len(rows)}")


if __name__ == "__main__":
    main()
