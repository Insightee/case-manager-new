import { createClient } from '@supabase/supabase-js';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const SUPABASE_URL = 'https://riukjenrqfdsbvsessmk.supabase.co';
const SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJpdWtqZW5ycWZkc2J2c2Vzc21rIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQ4OTAyMzgsImV4cCI6MjA5MDQ2NjIzOH0.3gndRl_qYo7BERiDQvb7V0PSCnsaNw2DZ93Vp-uCpPA';

const supabase = createClient(SUPABASE_URL, SUPABASE_KEY);

async function exportData() {
  console.log('Fetching employees from Supabase...');
  const { data: employees, error: empError } = await supabase
    .from('employees')
    .select('*');
  
  if (empError) {
    console.error('Error fetching employees:', empError);
    process.exit(1);
  }
  console.log(`Fetched ${employees.length} employees.`);

  console.log('Fetching payouts from Supabase...');
  let payouts = [];
  let from = 0;
  const limit = 1000;
  while (true) {
    const { data, error } = await supabase
      .from('payouts')
      .select('*')
      .range(from, from + limit - 1);
    if (error) {
      console.error('Error fetching payouts:', error);
      process.exit(1);
    }
    payouts = payouts.concat(data);
    if (data.length < limit) break;
    from += limit;
  }
  console.log(`Fetched ${payouts.length} payout records.`);

  const outputDir = path.join(__dirname, '../data_export');
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  fs.writeFileSync(
    path.join(outputDir, 'employees.json'),
    JSON.stringify(employees, null, 2)
  );
  fs.writeFileSync(
    path.join(outputDir, 'payouts.json'),
    JSON.stringify(payouts, null, 2)
  );

  console.log(`Exported successfully to ${outputDir}`);
}

exportData();
