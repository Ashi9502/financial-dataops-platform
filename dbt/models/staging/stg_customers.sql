select
    customer_id,
    trim(full_name) as customer_name,
    lower(trim(email)) as email,
    upper(trim(country_code)) as country_code,
    source_created_at,
    source_updated_at,
    loaded_at

from {{ source('raw', 'customers') }}
