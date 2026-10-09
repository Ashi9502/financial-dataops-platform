select
    transaction_date,
    merchant_key,
    currency,
    count(*) as duplicate_count

from {{ ref('mart_merchant_daily') }}

group by
    transaction_date,
    merchant_key,
    currency

having count(*) > 1
