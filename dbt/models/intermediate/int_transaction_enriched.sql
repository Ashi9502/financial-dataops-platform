select
    t.transaction_id,

    md5(t.customer_id::text) as customer_key,
    md5(t.merchant_id::text) as merchant_key,

    t.customer_id,
    t.merchant_id,

    t.transaction_ts,
    t.transaction_date,

    t.amount,

    case
        when t.transaction_status = 'completed'
            then t.amount
        when t.transaction_status = 'refunded'
            then -t.amount
    end as signed_amount,

    t.currency,
    t.transaction_status,
    t.payment_method,

    c.customer_name,
    c.country_code as customer_country_code,

    m.merchant_name,
    m.merchant_category,
    m.country_code as merchant_country_code,
    m.active as merchant_active,

    t.source_created_at,
    t.source_updated_at,
    t.source_object_key,
    t.loaded_at

from {{ ref('stg_transactions') }} t

inner join {{ ref('stg_customers') }} c
    on t.customer_id = c.customer_id

inner join {{ ref('stg_merchants') }} m
    on t.merchant_id = m.merchant_id
