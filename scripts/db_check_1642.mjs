import { createClient } from '@supabase/supabase-js';

const SUPABASE_URL = 'https://riukjenrqfdsbvsessmk.supabase.co';
const SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJpdWtqZW5ycWZkc2J2c2Vzc21rIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQ4OTAyMzgsImV4cCI6MjA5MDQ2NjIzOH0.3gndRl_qYo7BERiDQvb7V0PSCnsaNw2DZ93Vp-uCpPA';
const supabase = createClient(SUPABASE_URL, SUPABASE_KEY);

async function check1642() {
  const { data, error } = await supabase.from('payouts').select('*').eq('employee_id', '1642').order('year').order('month');
  if (error) {
    console.error(error);
    return;
  }
  console.log(`Found ${data.length} records for 1642:`);
  data.forEach(r => {
    console.log(`  ${r.month} ${r.year}: Gross ₹${r.gross_pay}, TDS ₹${r.tds}, Net ₹${r.net_pay}, Status: ${r.status}`);
  });
}

check1642();
