with fact_count as (
    select count(*) as row_count
    from {{ ref('fact_transactions') }}
),

mart_count as (
    select
        coalesce(
            sum(transaction_count),
            0
        ) as row_count
    from {{ ref('mart_merchant_daily') }}
)

select
    fact_count.row_count as fact_rows,
    mart_count.row_count as mart_transaction_count

from fact_count
cross join mart_count

where fact_count.row_count <> mart_count.row_count
