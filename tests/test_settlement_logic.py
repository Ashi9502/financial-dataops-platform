from datetime import date
from decimal import Decimal

import pytest

from src.ingestion.load_settlement_file import (
    REQUIRED_COLUMNS,
    parse_rows,
)
from scripts.generate_partner_settlements import (
    money,
    settlement_id,
)


def csv_bytes(*rows):
    header = ",".join(REQUIRED_COLUMNS)
    body = "\n".join(rows)

    return (
        header + "\n" + body + "\n"
    ).encode("utf-8")


def test_parse_rows_valid_record():
    data = csv_bytes(
        "STL-20261001-000007-INR,"
        "7,"
        "2026-10-01,"
        "INR,"
        "3,"
        "1000.25,"
        "15.00,"
        "985.25"
    )

    rows = parse_rows(data)

    assert len(rows) == 1

    row = rows[0]

    assert row["settlement_id"] == (
        "STL-20261001-000007-INR"
    )
    assert row["merchant_id"] == 7
    assert row["settlement_date"] == date(
        2026, 10, 1
    )
    assert row["currency"] == "INR"
    assert row["transaction_count"] == 3
    assert row["gross_amount"] == Decimal(
        "1000.25"
    )
    assert row["fees"] == Decimal("15.00")
    assert row["net_amount"] == Decimal(
        "985.25"
    )
    assert row["source_row_number"] == 2


def test_parse_rows_normalizes_currency():
    data = csv_bytes(
        "STL-20261001-000001-INR,"
        "1,"
        "2026-10-01,"
        " inr ,"
        "1,"
        "100.00,"
        "1.50,"
        "98.50"
    )

    row = parse_rows(data)[0]

    assert row["currency"] == "INR"


def test_parse_rows_tracks_physical_line_numbers():
    data = csv_bytes(
        "STL-A,1,2026-10-01,INR,1,"
        "100.00,1.50,98.50",
        "STL-B,2,2026-10-02,INR,2,"
        "200.00,3.00,197.00",
    )

    rows = parse_rows(data)

    assert [
        row["source_row_number"]
        for row in rows
    ] == [2, 3]


def test_parse_rows_rejects_missing_column():
    invalid_header = (
        "settlement_id,"
        "merchant_id,"
        "settlement_date,"
        "currency,"
        "transaction_count,"
        "gross_amount,"
        "fees\n"
    )

    data = (
        invalid_header
        + "STL-A,1,2026-10-01,INR,"
        + "1,100.00,1.50\n"
    ).encode("utf-8")

    with pytest.raises(
        ValueError,
        match="Unexpected settlement columns",
    ):
        parse_rows(data)


def test_parse_rows_rejects_invalid_date():
    data = csv_bytes(
        "STL-A,"
        "1,"
        "not-a-date,"
        "INR,"
        "1,"
        "100.00,"
        "1.50,"
        "98.50"
    )

    with pytest.raises(ValueError):
        parse_rows(data)


def test_parse_rows_preserves_decimal_precision():
    data = csv_bytes(
        "STL-A,"
        "1,"
        "2026-10-01,"
        "INR,"
        "1,"
        "123456789.12,"
        "1851851.84,"
        "121604937.28"
    )

    row = parse_rows(data)[0]

    assert row["gross_amount"] == Decimal(
        "123456789.12"
    )
    assert row["fees"] == Decimal(
        "1851851.84"
    )


def test_money_uses_half_up_rounding():
    assert money("10.005") == Decimal(
        "10.01"
    )

    assert money("10.004") == Decimal(
        "10.00"
    )


def test_settlement_id_format():
    result = settlement_id(
        date(2026, 10, 9),
        42,
        "INR",
    )

    assert result == (
        "STL-20261009-000042-INR"
    )
