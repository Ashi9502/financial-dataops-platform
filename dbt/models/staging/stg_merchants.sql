select
    merchant_id,
    trim(merchant_name) as merchant_name,
    lower(trim(merchant_category)) as merchant_category,
    upper(trim(country_code)) as country_code,
    active,
    source_created_at,
    source_updated_at,
    loaded_at

from {{ source('raw', 'merchants') }}
