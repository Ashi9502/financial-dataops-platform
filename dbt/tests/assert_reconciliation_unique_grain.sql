select
    scenario,
    settlement_date,
    merchant_id,
    currency,
    count(*) as row_count
from {{ ref('fct_reconciliation') }}
group by
    scenario,
    settlement_date,
    merchant_id,
    currency
having count(*) > 1
