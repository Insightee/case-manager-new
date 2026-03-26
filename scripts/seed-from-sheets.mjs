/**
 * Seed Script v6: Uses JSON overrides for months where CSV is incomplete.
 * 
 * - April–January: Parsed from Google Sheets CSV (gviz API)
 * - February–March: Loaded from local JSON file (more complete)
 * 
 * Run: node scripts/seed-from-sheets.mjs
 */

import { createClient } from '@supabase/supabase-js';
import { readFileSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const SUPABASE_URL = 'https://dhlxkzvgdkytcyguxvxr.supabase.co';
const SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRobHhrenZnZGt5dGN5Z3V4dnhyIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzM1ODM0NzYsImV4cCI6MjA4OTE1OTQ3Nn0.GQybPpaAFMiePAneZhoVejM0SLVEPYW7W5gLeOiUY1A';
const supabase = createClient(SUPABASE_URL, SUPABASE_KEY);

const SHEET_ID = '11ABJe6Hvno0AjOxXgOxmlg-waCkpTixzSH8qUdsCOPo';

// Months to fetch from Google Sheets CSV
const CSV_MONTHS = [
  { sheet: 'April 2025',     month: 'April',     year: 2025 },
  { sheet: 'May 2025',       month: 'May',       year: 2025 },
  { sheet: 'June 2025',      month: 'June',      year: 2025 },
  { sheet: 'July 2025',      month: 'July',      year: 2025 },
  { sheet: 'August 2025',    month: 'August',     year: 2025 },
  { sheet: 'September 2025', month: 'September',  year: 2025 },
  { sheet: 'October 2025',   month: 'October',    year: 2025 },
  { sheet: 'November 2025',  month: 'November',   year: 2025 },
  { sheet: 'December 2025',  month: 'December',   year: 2025 },
  { sheet: 'January 2026',   month: 'January',    year: 2026 },
];

// Months loaded from local JSON (more accurate than CSV export)
const JSON_MONTHS = [
  { key: 'February', month: 'February', year: 2026 },
  { key: 'March',    month: 'March',    year: 2026 },
];

function clean(s) { return s.replace(/"/g, '').replace(/\r/g, '').replace(/\n/g, ' ').replace(/\s+/g, ' ').trim(); }
function isNumericId(val) { return /^\d{3,5}$/.test(val.trim()); }
function isRoleField(val) {
  const v = val.toLowerCase().trim();
  return v.startsWith('consultant') || v.startsWith('employee') || v.startsWith('consul');
}

function splitCSVRecords(text) {
  const records = [];
  let current = '';
  let inQuotes = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (ch === '"') { inQuotes = !inQuotes; current += ch; }
    else if (ch === '\n' && !inQuotes) { if (current.trim()) records.push(current); current = ''; }
    else { current += ch; }
  }
  if (current.trim()) records.push(current);
  return records;
}

function parseCSVLine(line) {
  const parts = [];
  let field = '';
  let q = false;
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
    if (!employeeId || !name) return null;
    const grossPay = parseFloat(parts[3]?.replace(/,/g, '')) || 0;
    const tds = parseFloat(parts[4]?.replace(/,/g, '')) || 0;
    const netPay = parseFloat(parts[5]?.replace(/,/g, '')) || 0;
    return { employeeId, name, grossPay, tds, netPay, role, reference: parts[6] || 'paid' };
  }
  
  let employeeId, name;
  if (isNumericId(parts[0])) { employeeId = parts[0]; name = parts[1]; }
  else if (isNumericId(parts[1])) { employeeId = parts[1]; name = parts[0]; }
  else return null;
  if (!employeeId || !name) return null;
  const grossPay = parseFloat(parts[2]?.replace(/,/g, '')) || 0;
  const tds = parseFloat(parts[3]?.replace(/,/g, '')) || 0;
  const netPay = parseFloat(parts[4]?.replace(/,/g, '')) || 0;
  return { employeeId, name, grossPay, tds, netPay, role: 'Consultant', reference: parts[5] || 'paid' };
}

function parseCSV(text, sheetName) {
  const records = splitCSVRecords(text);
  if (records.length < 2) return [];
  const rows = [];
  for (let i = 1; i < records.length; i++) {
    const parts = parseCSVLine(records[i]);
    const extracted = extractRow(parts);
    if (extracted && extracted.grossPay > 0) rows.push(extracted);
  }
  return rows;
}

async function fetchSheet(sheetName) {
  const url = `https://docs.google.com/spreadsheets/d/${SHEET_ID}/gviz/tq?tqx=out:csv&sheet=${encodeURIComponent(sheetName)}`;
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 30000);
    const res = await fetch(url, { signal: controller.signal });
    clearTimeout(timeout);
    if (!res.ok) return [];
    return parseCSV(await res.text(), sheetName);
  } catch (e) {
    console.error(`  ✗ Fetch error: ${e.message}`);
    return [];
  }
}

function loadJSON() {
  const filePath = join(__dirname, 'payslip_feb_march.json');
  const raw = readFileSync(filePath, 'utf-8');
  return JSON.parse(raw);
}

async function seed() {
  console.log('╔══════════════════════════════════════════════════╗');
  console.log('║   INSIGHTE PAYOUT PORTAL — SEEDER v6            ║');
  console.log('║   CSV + JSON Hybrid (Complete Data)             ║');
  console.log('╚══════════════════════════════════════════════════╝\n');

  // Clear
  console.log('🗑️  Clearing existing data...');
  await supabase.from('payouts').delete().neq('id', '00000000-0000-0000-0000-000000000000');
  await supabase.from('employees').delete().neq('employee_id', '0000');

  const empNameVariations = new Map();
  const empRoles = new Map();
  const allPayouts = [];

  // ──── PHASE 1: CSV months (April–January) ────
  for (const { sheet, month, year } of CSV_MONTHS) {
    process.stdout.write(`📥 [CSV] ${sheet}...`);
    const rows = await fetchSheet(sheet);
    console.log(` ${rows.length} records`);
    for (const row of rows) {
      if (!empNameVariations.has(row.employeeId)) empNameVariations.set(row.employeeId, new Map());
      empNameVariations.get(row.employeeId).set(row.name, (empNameVariations.get(row.employeeId).get(row.name) || 0) + 1);
      if (row.role) empRoles.set(row.employeeId, row.role);
      allPayouts.push({
        employee_id: row.employeeId, raw_name: row.name,
        month, year, gross_pay: row.grossPay, tds: row.tds, net_pay: row.netPay,
        status: (row.reference || '').toLowerCase() === 'paid' ? 'paid' : 'pending'
      });
    }
  }

  // ──── PHASE 2: JSON months (February–March) ────
  const jsonData = loadJSON();
  for (const { key, month, year } of JSON_MONTHS) {
    const records = jsonData[key] || [];
    console.log(`📥 [JSON] ${month} ${year}: ${records.length} records`);
    for (const r of records) {
      const empId = String(r.employee_id).trim();
      const name = (r.employee_name || '').trim();
      if (!empId || !name) continue;
      
      const role = (r.category || '').toLowerCase().includes('employee') ? 'Employee' : 'Consultant';
      
      if (!empNameVariations.has(empId)) empNameVariations.set(empId, new Map());
      empNameVariations.get(empId).set(name, (empNameVariations.get(empId).get(name) || 0) + 1);
      empRoles.set(empId, role);
      
      allPayouts.push({
        employee_id: empId, raw_name: name,
        month, year,
        gross_pay: Number(r.gross) || 0,
        tds: Number(r.tds) || 0,
        net_pay: Number(r.net_pay) || 0,
        status: (r.status || 'paid').toLowerCase()
      });
    }
  }

  // ──── PHASE 3: Standardize names ────
  const standardNames = new Map();
  let fixes = 0;
  for (const [empId, nameMap] of empNameVariations) {
    const sorted = [...nameMap.entries()].sort((a, b) => b[1] - a[1] || b[0].length - a[0].length);
    standardNames.set(empId, sorted[0][0]);
    if (nameMap.size > 1) {
      fixes++;
      if (fixes <= 15) {
        const variants = sorted.map(([n, c]) => `"${n}"(${c})`).join(' / ');
        console.log(`  📌 ${empId}: ${variants} → "${sorted[0][0]}"`);
      }
    }
  }
  if (fixes > 15) console.log(`  ... +${fixes - 15} more`);
  console.log(`\n🔧 ${fixes} name variations standardized`);
  console.log(`📊 ${standardNames.size} employees, ${allPayouts.length} payouts\n`);

  // Build employee array
  const empArray = [...standardNames.entries()].map(([id, name]) => ({
    employee_id: id, name,
    email: `${name.toLowerCase().replace(/[^a-z0-9]/g, '.')}@insighte.in`,
    role: empRoles.get(id) || 'Consultant'
  }));

  // Build payouts with canonical name
  const payouts = allPayouts
    .filter(p => p.gross_pay > 0)
    .map(p => ({
      employee_id: p.employee_id,
      name: standardNames.get(p.employee_id) || p.raw_name,
      month: p.month, year: p.year,
      gross_pay: p.gross_pay, tds: p.tds, net_pay: p.net_pay,
      status: p.status
    }));

  // ──── PHASE 4: Insert ────
  console.log(`👤 Inserting ${empArray.length} employees...`);
  let empOk = 0;
  for (let i = 0; i < empArray.length; i += 50) {
    const b = empArray.slice(i, i + 50);
    const { error } = await supabase.from('employees').upsert(b, { onConflict: 'employee_id' });
    if (error) console.error(`  ✗`, error.message);
    else empOk += b.length;
  }
  console.log(`  ✓ ${empOk}/${empArray.length}\n`);

  console.log(`💰 Inserting ${payouts.length} payouts...`);
  let payOk = 0, payFail = 0;
  for (let i = 0; i < payouts.length; i += 100) {
    const b = payouts.slice(i, i + 100);
    const { error } = await supabase.from('payouts').insert(b);
    if (error) { console.error(`  ✗ Batch ${i}: ${error.message}`); payFail += b.length; }
    else { payOk += b.length; process.stdout.write(`\r  ⏳ ${payOk}/${payouts.length}`); }
  }
  console.log(`\n  ✓ ${payOk}/${payouts.length} (${payFail} failed)\n`);

  // ──── PHASE 5: Verify ────
  const { count: ec } = await supabase.from('employees').select('*', { count: 'exact', head: true });
  const { count: pc } = await supabase.from('payouts').select('*', { count: 'exact', head: true });
  console.log('═══════════════════════════════════════════');
  console.log(`✅ DB: ${ec} employees, ${pc} payouts`);
  console.log('═══════════════════════════════════════════');

  // Spot checks
  for (const [testId, label] of [['1082', 'Nikita Nath'], ['1425', 'Ananya Sreedhar'], ['1009', 'Balambal Ganesh']]) {
    const { data } = await supabase.from('payouts').select('month, year, gross_pay, tds, net_pay')
      .eq('employee_id', testId).order('year').order('month');
    console.log(`\n🔍 ${label} (${testId}): ${data?.length} records`);
    data?.forEach(r => console.log(`   ${r.month} ${r.year}: Gross ₹${r.gross_pay}, TDS ₹${r.tds}, Net ₹${r.net_pay}`));
  }

  // Per-month verification
  console.log('\n📅 Records per month:');
  const { data: allP } = await supabase.from('payouts').select('month, year');
  const monthMap = new Map();
  allP?.forEach(r => { const k = `${r.month} ${r.year}`; monthMap.set(k, (monthMap.get(k) || 0) + 1); });
  const allMonths = [...CSV_MONTHS.map(m => `${m.month} ${m.year}`), ...JSON_MONTHS.map(m => `${m.month} ${m.year}`)];
  for (const key of allMonths) console.log(`   ${key}: ${monthMap.get(key) || 0}`);
}

seed().catch(console.error);
