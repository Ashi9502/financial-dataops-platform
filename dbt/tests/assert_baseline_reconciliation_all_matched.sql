select *
from {{ ref('fct_reconciliation') }}
where scenario = 'baseline'
  and reconciliation_status <> 'MATCHED'
