-- Read-only: sessions auto-closed ~4h before scheduled end (likely category mis-map).
-- Run against production/staging with a read-only role.

SELECT
    c.case_code,
    c.id AS case_id,
    c.service_type,
    c.product_module,
    s.id AS session_id,
    s.scheduled_date,
    s.start_time AS scheduled_start,
    s.end_time AS scheduled_end,
    s.actual_start_at,
    s.actual_end_at,
    ROUND(EXTRACT(EPOCH FROM (s.actual_end_at - s.actual_start_at)) / 60.0) AS duration_minutes,
    s.auto_end_reason
FROM sessions s
JOIN cases c ON c.id = s.case_id
WHERE s.auto_ended = TRUE
  AND s.actual_start_at IS NOT NULL
  AND s.actual_end_at IS NOT NULL
  AND s.end_time IS NOT NULL
  AND s.auto_end_reason IN ('slot_duration_limit', 'category_duration_limit', 'homecare_3h_limit')
  AND s.actual_end_at < (
      (s.scheduled_date + s.end_time) AT TIME ZONE 'Asia/Kolkata'
  )
  AND ROUND(EXTRACT(EPOCH FROM (s.actual_end_at - s.actual_start_at)) / 60.0) BETWEEN 235 AND 245
ORDER BY s.actual_end_at DESC;
