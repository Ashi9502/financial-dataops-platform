with staging_count as (
    select count(*) as row_count
    from {{ ref('stg_transactions') }}
),

fact_count as (
    select count(*) as row_count
    from {{ ref('fact_transactions') }}
)

select
    staging_count.row_count as staging_rows,
    fact_count.row_count as fact_rows

from staging_count
cross join fact_count

where staging_count.row_count <> fact_count.row_count
