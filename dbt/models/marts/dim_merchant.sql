select
    md5(merchant_id::text) as merchant_key,
    merchant_id,
    merchant_name,
    merchant_category,
    country_code,
    active,
    source_created_at,
    source_updated_at,
    loaded_at

from {{ ref('stg_merchants') }}
