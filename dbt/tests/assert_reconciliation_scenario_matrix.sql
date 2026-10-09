with expected as (

    select *
    from (
        values
            ('baseline',            'MATCHED',              1533),
            ('late_backfill',       'MATCHED',              1533),
            ('schema_recovery',     'MATCHED',              1533),
            ('amount_mismatch',     'MATCHED',              1532),
            ('amount_mismatch',     'AMOUNT_MISMATCH',         1),
            ('count_mismatch',      'MATCHED',              1532),
            ('count_mismatch',      'COUNT_MISMATCH',          1),
            ('missing_settlement',  'MATCHED',              1532),
            ('missing_settlement',  'MISSING_SETTLEMENT',      1),
            ('missing_transaction', 'MATCHED',              1533),
            ('missing_transaction', 'MISSING_TRANSACTION',     1)
    ) as t (
        scenario,
        reconciliation_status,
        expected_rows
    )

),

actual as (

    select
        scenario,
        reconciliation_status,
        count(*) as actual_rows
    from {{ ref('fct_reconciliation') }}
    group by
        scenario,
        reconciliation_status

),

comparison as (

    select
        coalesce(
            e.scenario,
            a.scenario
        ) as scenario,

        coalesce(
            e.reconciliation_status,
            a.reconciliation_status
        ) as reconciliation_status,

        e.expected_rows,
        a.actual_rows

    from expected e

    full outer join actual a
        on e.scenario = a.scenario
        and e.reconciliation_status
            = a.reconciliation_status

)

select *
from comparison
where expected_rows is distinct from actual_rows
