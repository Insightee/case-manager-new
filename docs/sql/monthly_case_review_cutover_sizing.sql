-- Read-only cutover sizing queries for monthly_case_review + package_session_count gate.
-- NEVER run with writes. Prefer a staging/prod read-only role or replica.
-- Generated for Finance Engine cutover planning (Prompt 2).

-- 1) Total rows
SELECT COUNT(*) AS monthly_case_review_total
FROM monthly_case_review;

-- 2) Breakdown by classification_bucket
SELECT classification_bucket, COUNT(*) AS n
FROM monthly_case_review
GROUP BY 1
ORDER BY n DESC;

-- 3) NEEDS_REVIEW by review_reason
SELECT COALESCE(review_reason, '(null)') AS review_reason, COUNT(*) AS n
FROM monthly_case_review
WHERE classification_bucket = 'NEEDS_REVIEW'
GROUP BY 1
ORDER BY n DESC;

-- 4) NEEDS_REVIEW finance_decision null vs filled
SELECT
  COUNT(*) FILTER (WHERE finance_decision IS NULL) AS untouched_null,
  COUNT(*) FILTER (WHERE finance_decision IS NOT NULL) AS decided,
  COUNT(*) AS needs_review_total
FROM monthly_case_review
WHERE classification_bucket = 'NEEDS_REVIEW';

-- 5) Rate exposure on NEEDS_REVIEW (NOT booked monthly revenue — rate exposure only)
SELECT
  COUNT(*) AS n,
  COUNT(previous_client_rate_per_session_inr) AS n_with_rate,
  MIN(previous_client_rate_per_session_inr) AS rate_min,
  PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY previous_client_rate_per_session_inr)
    AS rate_median,
  MAX(previous_client_rate_per_session_inr) AS rate_max,
  COALESCE(SUM(previous_client_rate_per_session_inr), 0) AS rate_sum_exposure
FROM monthly_case_review
WHERE classification_bucket = 'NEEDS_REVIEW';

-- 6a) PACKAGE cases missing package_session_count
SELECT
  COUNT(*) FILTER (WHERE status = 'ACTIVE') AS active_missing,
  COUNT(*) AS all_statuses_missing
FROM cases
WHERE billing_type = 'PACKAGE'
  AND (package_session_count IS NULL OR package_session_count <= 0);

-- 6b) Of those, how many had sessions in the last 60 days (actively billing signal)
SELECT COUNT(DISTINCT c.id) AS missing_pkg_with_recent_sessions
FROM cases c
JOIN sessions s ON s.case_id = c.id
WHERE c.billing_type = 'PACKAGE'
  AND (c.package_session_count IS NULL OR c.package_session_count <= 0)
  AND s.scheduled_date >= (CURRENT_DATE - INTERVAL '60 days')
  AND s.status NOT IN ('CANCELLED', 'RESCHEDULED');

-- Finance work CSV source
-- COPY (
SELECT
  m.case_id,
  m.client_name,
  m.service_type,
  m.classification_bucket,
  m.review_reason,
  m.previous_client_rate_per_session_inr,
  m.client_monthly_rate_inr,
  m.product_billing_rule_id,
  m.finance_decision,
  m.previous_billing_type,
  m.current_billing_type,
  m.created_at
FROM monthly_case_review m
WHERE m.classification_bucket = 'NEEDS_REVIEW'
ORDER BY m.previous_client_rate_per_session_inr DESC NULLS LAST, m.case_id
-- ) TO STDOUT WITH CSV HEADER;
;
