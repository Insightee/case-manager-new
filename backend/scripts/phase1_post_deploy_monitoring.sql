-- Phase 1 post-deploy monitoring (run at T+0, T+24h, T+48h after merge)
-- Postgres; adjust schema if table names differ.

-- Stale IN_PROGRESS from prior IST calendar days
SELECT COUNT(*) AS stale_in_progress_prior_days
FROM sessions
WHERE status = 'IN_PROGRESS'
  AND actual_start_at IS NOT NULL
  AND (actual_start_at AT TIME ZONE 'Asia/Kolkata')::date
      < (now() AT TIME ZONE 'Asia/Kolkata')::date;

-- Auto-end reason distribution (last 7 days)
SELECT auto_end_reason, COUNT(*) AS n
FROM sessions
WHERE auto_ended = true
  AND actual_end_at >= now() - interval '7 days'
GROUP BY auto_end_reason
ORDER BY n DESC;

-- COMPLETED without daily log (needs-log backlog)
SELECT COUNT(*) AS completed_without_log
FROM sessions s
LEFT JOIN daily_logs d ON d.session_id = s.id
WHERE s.status = 'COMPLETED'
  AND d.id IS NULL;

-- Child absence duplicate rate (structured 409s — check app logs / API metrics)
-- Pending absence requests
SELECT status, COUNT(*) FROM session_absence_requests GROUP BY status;
