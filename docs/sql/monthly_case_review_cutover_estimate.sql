-- ESTIMATE pack: classify cases as Step-1 migration WOULD, without running the migration.
-- Use ONLY when monthly_case_review is empty/absent or fixture-only (situations b/c).
-- READ-ONLY / SELECT-ONLY. Never UPDATE/INSERT. Threshold matches y2z3a4b5c6d7 (₹8000).
--
-- NOTE on "missing rule": the migration only queues NEEDS_REVIEW for missing
-- product_billing_rule_id when client_rate_per_session_inr > 8000 (same as non-monthly).

-- 0) Identity (confirm staging vs prod yourself from host/db name — do not paste URLs)
SELECT current_database() AS db, current_user AS usr, inet_server_addr() AS addr,
       pg_is_in_recovery() AS is_replica;

-- 1) Would AUTO_MIGRATE (MONTHLY_FIXED product link) — no finance action
SELECT COUNT(*) AS would_auto_migrate
FROM cases c
JOIN product_billing_rules r ON r.id = c.product_billing_rule_id
WHERE c.product_billing_rule_id IS NOT NULL
  AND r.billing_model = 'MONTHLY_FIXED';

-- 2) Would NEEDS_REVIEW — breakdown by reason (mirrors migration WHERE)
SELECT
  CASE
    WHEN c.product_billing_rule_id IS NULL THEN 'Missing product_billing_rule_id'
    ELSE 'Non-monthly product rule with monthly-looking rate'
  END AS review_reason,
  COUNT(*) AS n,
  COUNT(c.client_rate_per_session_inr) AS n_with_rate,
  MIN(c.client_rate_per_session_inr) AS rate_min,
  PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY c.client_rate_per_session_inr) AS rate_median,
  MAX(c.client_rate_per_session_inr) AS rate_max,
  COALESCE(SUM(c.client_rate_per_session_inr), 0) AS rate_sum_exposure
FROM cases c
LEFT JOIN product_billing_rules r ON r.id = c.product_billing_rule_id
WHERE (
    c.product_billing_rule_id IS NULL
    AND c.client_rate_per_session_inr IS NOT NULL
    AND c.client_rate_per_session_inr > 8000
)
OR (
    c.product_billing_rule_id IS NOT NULL
    AND (r.billing_model IS NULL OR r.billing_model <> 'MONTHLY_FIXED')
    AND c.client_rate_per_session_inr IS NOT NULL
    AND c.client_rate_per_session_inr > 8000
)
GROUP BY 1
ORDER BY n DESC;

-- 3) Would NEEDS_REVIEW — totals (ESTIMATE of finance decisions from monthly gate)
SELECT
  COUNT(*) AS would_needs_review,
  COALESCE(SUM(c.client_rate_per_session_inr), 0) AS rate_sum_exposure
FROM cases c
LEFT JOIN product_billing_rules r ON r.id = c.product_billing_rule_id
WHERE (
    c.product_billing_rule_id IS NULL
    AND c.client_rate_per_session_inr IS NOT NULL
    AND c.client_rate_per_session_inr > 8000
)
OR (
    c.product_billing_rule_id IS NOT NULL
    AND (r.billing_model IS NULL OR r.billing_model <> 'MONTHLY_FIXED')
    AND c.client_rate_per_session_inr IS NOT NULL
    AND c.client_rate_per_session_inr > 8000
);

-- 4) PACKAGE missing package_session_count (independent second gate)
SELECT
  COUNT(*) FILTER (WHERE status = 'ACTIVE') AS active_missing,
  COUNT(*) AS all_statuses_missing
FROM cases
WHERE billing_type = 'PACKAGE'
  AND (package_session_count IS NULL OR package_session_count <= 0);

-- 5) Fixture filter helper — exclude STEP1-FIX* / demo-looking children if present
-- Adjust if your staging uses different fixture prefixes.
SELECT COUNT(*) AS fixture_like_cases
FROM cases c
LEFT JOIN children ch ON ch.id = c.child_id
WHERE COALESCE(ch.first_name, '') ILIKE 'STEP1-FIX%'
   OR COALESCE(ch.last_name, '') ILIKE 'STEP1-FIX%'
   OR CAST(c.id AS text) ILIKE '%STEP1-FIX%';
