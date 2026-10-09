select
    md5(customer_id::text) as customer_key,
    customer_id,
    customer_name,
    email,
    country_code,
    source_created_at,
    source_updated_at,
    loaded_at

from {{ ref('stg_customers') }}
