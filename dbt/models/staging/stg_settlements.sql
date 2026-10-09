select
    raw_settlement_row_id,
    settlement_id,
    scenario,
    merchant_id,
    settlement_date,
    trim(currency) as currency,
    transaction_count,
    gross_amount,
    fees,
    net_amount,
    source_object_key,
    source_file_sha256,
    source_row_number,
    loaded_at
from {{ source('raw', 'settlements') }}
