
import { createClient } from '@supabase/supabase-js';

const SUPABASE_URL = 'https://riukjenrqfdsbvsessmk.supabase.co';
const SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJpdWtqZW5ycWZkc2J2c2Vzc21rIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQ4OTAyMzgsImV4cCI6MjA5MDQ2NjIzOH0.3gndRl_qYo7BERiDQvb7V0PSCnsaNw2DZ93Vp-uCpPA';
const supabase = createClient(SUPABASE_URL, SUPABASE_KEY);

const SHEET_ID = '11ABJe6Hvno0AjOxXgOxmlg-waCkpTixzSH8qUdsCOPo';

function clean(s) { return s.replace(/"/g, '').replace(/\r/g, '').replace(/\n/g, ' ').replace(/\s+/g, ' ').trim(); }
function isNumericId(val) { return /^\d{3,5}$/.test(val.trim()); }
function isRoleField(val) {
  const v = val.toLowerCase().trim();
  return v.startsWith('consultant') || v.startsWith('employee') || v.startsWith('consul');
}

function parseCSVLine(line) {
  const parts = [];
  let field = '', q = false;
  for (const ch of line) {
    if (ch === '"') { q = !q; }
    else if (ch === ',' && !q) { parts.push(clean(field)); field = ''; }
    else { field += ch; }
  }
  parts.push(clean(field));
  return parts;
}

function extractRow(parts) {
  const first = parts[0] || '';
  if (isRoleField(first)) {
    const role = first.toLowerCase().includes('employee') ? 'Employee' : 'Consultant';
    let employeeId, name;
    if (isNumericId(parts[1])) { employeeId = parts[1]; name = parts[2]; }
    else if (isNumericId(parts[2])) { employeeId = parts[2]; name = parts[1]; }
    else return null;
    const grossPay = parseFloat(parts[3]?.replace(/,/g, '')) || 0;
    const tds = parseFloat(parts[4]?.replace(/,/g, '')) || 0;
    const netPay = parseFloat(parts[5]?.replace(/,/g, '')) || 0;
    return { employeeId, name, grossPay, tds, netPay, role };
  }
  let employeeId, name;
  if (isNumericId(parts[0])) { employeeId = parts[0]; name = parts[1]; }
  else if (isNumericId(parts[1])) { employeeId = parts[1]; name = parts[0]; }
  else return null;
  const grossPay = parseFloat(parts[2]?.replace(/,/g, '')) || 0;
  const tds = parseFloat(parts[3]?.replace(/,/g, '')) || 0;
  const netPay = parseFloat(parts[4]?.replace(/,/g, '')) || 0;
  return { employeeId, name, grossPay, tds, netPay, role: 'Consultant' };
}

async function testApril() {
  const url = `https://docs.google.com/spreadsheets/d/${SHEET_ID}/gviz/tq?tqx=out:csv&sheet=April%202026`;
  const res = await fetch(url);
  const text = await res.text();
  const lines = text.split('\n');
  console.log(`Total lines: ${lines.length}`);
  let count = 0;
  for (let i = 1; i < lines.length; i++) {
    const parts = parseCSVLine(lines[i]);
    const row = extractRow(parts);
    if (row && row.grossPay > 0) {
      count++;
      if (row.employeeId === '1642') console.log(`Found 1642:`, row);
    }
  }
  console.log(`Parsed rows: ${count}`);
}

testApril();
