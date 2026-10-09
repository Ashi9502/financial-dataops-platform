with scenarios as (

    select distinct
        scenario
    from {{ ref('stg_settlements') }}

),

expected as (

    select
        settlement_date,
        merchant_id,
        currency,
        expected_transaction_count,
        expected_gross_amount,
        expected_fees,
        expected_net_amount
    from {{ ref('int_expected_settlements') }}

),

expected_by_scenario as (

    select
        s.scenario,
        e.settlement_date,
        e.merchant_id,
        e.currency,
        e.expected_transaction_count,
        e.expected_gross_amount,
        e.expected_fees,
        e.expected_net_amount
    from scenarios s
    cross join expected e

),

partner as (

    select
        scenario,
        settlement_id,
        settlement_date,
        merchant_id,
        currency,
        transaction_count
            as actual_transaction_count,
        gross_amount
            as actual_gross_amount,
        fees
            as actual_fees,
        net_amount
            as actual_net_amount,
        source_object_key,
        source_file_sha256
    from {{ ref('stg_settlements') }}

),

reconciled as (

    select
        coalesce(
            e.scenario,
            p.scenario
        ) as scenario,

        coalesce(
            e.settlement_date,
            p.settlement_date
        ) as settlement_date,

        coalesce(
            e.merchant_id,
            p.merchant_id
        ) as merchant_id,

        coalesce(
            e.currency,
            p.currency
        ) as currency,

        p.settlement_id,

        e.expected_transaction_count,
        p.actual_transaction_count,

        e.expected_gross_amount,
        p.actual_gross_amount,

        e.expected_fees,
        p.actual_fees,

        e.expected_net_amount,
        p.actual_net_amount,

        p.source_object_key,
        p.source_file_sha256,

        case
            when e.merchant_id is null
                then 'MISSING_TRANSACTION'

            when p.merchant_id is null
                then 'MISSING_SETTLEMENT'

            when
                e.expected_transaction_count
                <> p.actual_transaction_count
                then 'COUNT_MISMATCH'

            when
                e.expected_gross_amount
                    <> p.actual_gross_amount
                or e.expected_fees
                    <> p.actual_fees
                or e.expected_net_amount
                    <> p.actual_net_amount
                then 'AMOUNT_MISMATCH'

            else 'MATCHED'
        end as reconciliation_status

    from expected_by_scenario e

    full outer join partner p
        on e.scenario = p.scenario
        and e.settlement_date
            = p.settlement_date
        and e.merchant_id
            = p.merchant_id
        and e.currency
            = p.currency

)

select
    *,

    coalesce(
        actual_transaction_count,
        0
    )
    -
    coalesce(
        expected_transaction_count,
        0
    ) as transaction_count_difference,

    coalesce(
        actual_gross_amount,
        0
    )
    -
    coalesce(
        expected_gross_amount,
        0
    ) as gross_amount_difference,

    coalesce(
        actual_net_amount,
        0
    )
    -
    coalesce(
        expected_net_amount,
        0
    ) as net_amount_difference

from reconciled
