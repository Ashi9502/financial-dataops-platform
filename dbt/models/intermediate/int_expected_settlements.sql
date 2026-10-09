with completed_transactions as (

    select
        transaction_date as settlement_date,
        merchant_id,
        currency,
        amount
    from {{ ref('fact_transactions') }}
    where transaction_status = 'completed'

),

aggregated as (

    select
        settlement_date,
        merchant_id,
        currency,
        count(*) as expected_transaction_count,
        sum(amount) as expected_gross_amount
    from completed_transactions
    group by
        settlement_date,
        merchant_id,
        currency

),

with_fees as (

    select
        settlement_date,
        merchant_id,
        currency,
        expected_transaction_count,
        expected_gross_amount,

        round(
            expected_gross_amount
            * cast(0.015 as numeric),
            2
        ) as expected_fees

    from aggregated

)

select
    settlement_date,
    merchant_id,
    currency,
    expected_transaction_count,
    expected_gross_amount,
    expected_fees,
    expected_gross_amount
        - expected_fees
        as expected_net_amount
from with_fees
