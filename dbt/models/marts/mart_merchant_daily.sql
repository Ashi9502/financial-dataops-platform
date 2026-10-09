select
    f.transaction_date,

    f.merchant_key,
    f.merchant_id,

    m.merchant_name,
    m.merchant_category,
    m.country_code as merchant_country_code,

    f.currency,

    count(*) as transaction_count,

    sum(
        case
            when f.transaction_status = 'completed'
                then 1
            else 0
        end
    ) as completed_transaction_count,

    sum(
        case
            when f.transaction_status = 'refunded'
                then 1
            else 0
        end
    ) as refunded_transaction_count,

    sum(
        case
            when f.transaction_status = 'completed'
                then f.amount
            else 0
        end
    )::numeric(18,2) as completed_gross_amount,

    sum(
        case
            when f.transaction_status = 'refunded'
                then f.amount
            else 0
        end
    )::numeric(18,2) as refunded_amount,

    sum(f.signed_amount)::numeric(18,2)
        as net_transaction_amount,

    avg(f.amount)::numeric(18,2)
        as average_transaction_amount

from {{ ref('fact_transactions') }} f

inner join {{ ref('dim_merchant') }} m
    on f.merchant_key = m.merchant_key

group by
    f.transaction_date,
    f.merchant_key,
    f.merchant_id,
    m.merchant_name,
    m.merchant_category,
    m.country_code,
    f.currency
