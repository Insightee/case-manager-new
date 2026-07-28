-- Initial Supabase Migration for Insighte Payout Portal

-- 1. Employees Table
CREATE TABLE IF NOT EXISTS public.employees (
    employee_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT,
    role TEXT DEFAULT 'Consultant',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable Row Level Security (RLS)
ALTER TABLE public.employees ENABLE ROW LEVEL SECURITY;

-- Allow public read access to employees
CREATE POLICY "Allow public read access to employees"
    ON public.employees FOR SELECT
    USING (true);

-- Allow authenticated and service role full access to employees
CREATE POLICY "Allow write access to employees"
    ON public.employees FOR ALL
    USING (true)
    WITH CHECK (true);

-- 2. Payouts Table
CREATE TABLE IF NOT EXISTS public.payouts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id TEXT REFERENCES public.employees(employee_id) ON DELETE SET NULL,
    name TEXT NOT NULL,
    month TEXT NOT NULL,
    year INTEGER NOT NULL,
    gross_pay NUMERIC(10, 2) DEFAULT 0.00,
    tds NUMERIC(10, 2) DEFAULT 0.00,
    net_pay NUMERIC(10, 2) DEFAULT 0.00,
    status TEXT DEFAULT 'paid',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable Row Level Security (RLS)
ALTER TABLE public.payouts ENABLE ROW LEVEL SECURITY;

-- Allow public read access to payouts
CREATE POLICY "Allow public read access to payouts"
    ON public.payouts FOR SELECT
    USING (true);

-- Allow full write access to payouts
CREATE POLICY "Allow write access to payouts"
    ON public.payouts FOR ALL
    USING (true)
    WITH CHECK (true);

-- Create indexes for fast filtering
CREATE INDEX IF NOT EXISTS idx_payouts_employee_id ON public.payouts(employee_id);
CREATE INDEX IF NOT EXISTS idx_payouts_month_year ON public.payouts(month, year);
