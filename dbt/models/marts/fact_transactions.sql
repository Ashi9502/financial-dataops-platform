select
    transaction_id,

    customer_key,
    merchant_key,

    customer_id,
    merchant_id,

    transaction_ts,
    transaction_date,

    amount,
    signed_amount,

    currency,
    transaction_status,
    payment_method,

    source_created_at,
    source_updated_at,
    source_object_key,
    loaded_at

from {{ ref('int_transaction_enriched') }}
