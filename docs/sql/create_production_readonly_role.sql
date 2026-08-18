-- Create a SELECT-only role for cutover sizing + finance dashboard read probes.
-- Run once against PRODUCTION Postgres as a superuser / DB owner (Railway Postgres).
-- Does NOT mutate application data. Does NOT grant INSERT/UPDATE/DELETE.
--
-- After running: put the connection string in Cursor agent secrets as
--   READONLY_DATABASE_URL
-- Never commit the password. Never point staging APP DATABASE_URL at production.

-- 0) Note the database name (run first; use it in GRANT CONNECT below)
-- SELECT current_database();

-- 1) Role (change password before running)
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'insightcase_readonly') THEN
    CREATE ROLE insightcase_readonly LOGIN PASSWORD 'REPLACE_WITH_STRONG_PASSWORD'
      NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
  END IF;
END $$;

-- 2) Connect (replace <PROD_DB> with current_database() from step 0)
-- GRANT CONNECT ON DATABASE <PROD_DB> TO insightcase_readonly;

GRANT USAGE ON SCHEMA public TO insightcase_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO insightcase_readonly;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO insightcase_readonly;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT ON TABLES TO insightcase_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT ON SEQUENCES TO insightcase_readonly;

-- 3) Session safety default for this role
ALTER ROLE insightcase_readonly SET default_transaction_read_only = on;

-- 4) Verify (reconnect as insightcase_readonly)
-- SELECT current_user, current_database();
-- SELECT has_table_privilege(current_user, 'cases', 'SELECT');  -- expect true
-- SELECT has_table_privilege(current_user, 'cases', 'INSERT');  -- expect false
-- SHOW default_transaction_read_only;  -- expect on
-- SELECT COUNT(*) FROM cases;
-- SELECT to_regclass('public.monthly_case_review');
