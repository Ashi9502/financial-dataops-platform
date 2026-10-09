select
    transaction_id,
    customer_id,
    merchant_id,

    transaction_ts,
    transaction_ts::date as transaction_date,

    amount::numeric(18, 2) as amount,

    upper(trim(currency)) as currency,
    lower(trim(status)) as transaction_status,
    lower(trim(payment_method)) as payment_method,

    source_created_at,
    source_updated_at,
    source_object_key,
    loaded_at

from {{ source('raw', 'transactions') }}
