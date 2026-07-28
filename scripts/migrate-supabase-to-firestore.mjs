import { initializeApp, cert, getApps } from 'firebase-admin/app';
import { getFirestore, FieldValue } from 'firebase-admin/firestore';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Initialize Firebase Admin SDK
if (!getApps().length) {
  if (process.env.FIREBASE_SERVICE_ACCOUNT_KEY) {
    const serviceAccount = JSON.parse(process.env.FIREBASE_SERVICE_ACCOUNT_KEY);
    initializeApp({ credential: cert(serviceAccount) });
  } else {
    initializeApp();
  }
}

const db = getFirestore();

async function migrate() {
  const dataDir = path.join(__dirname, '../data_export');
  const empPath = path.join(dataDir, 'employees.json');
  const payPath = path.join(dataDir, 'payouts.json');

  if (!fs.existsSync(empPath) || !fs.existsSync(payPath)) {
    console.error('Exported data files not found in data_export directory.');
    process.exit(1);
  }

  const employees = JSON.parse(fs.readFileSync(empPath, 'utf8'));
  const payouts = JSON.parse(fs.readFileSync(payPath, 'utf8'));

  console.log(`Starting migration: ${employees.length} employees, ${payouts.length} payout records.`);

  // 1. Migrate Employees
  let empCount = 0;
  for (let i = 0; i < employees.length; i += 400) {
    const chunk = employees.slice(i, i + 400);
    const batch = db.batch();
    for (const emp of chunk) {
      if (!emp.employee_id) continue;
      const ref = db.collection('employees').doc(String(emp.employee_id));
      batch.set(ref, {
        employeeId: String(emp.employee_id),
        name: emp.name || '',
        email: emp.email || '',
        role: emp.role || 'Consultant',
        updatedAt: FieldValue.serverTimestamp()
      }, { merge: true });
      empCount++;
    }
    await batch.commit();
  }
  console.log(`Migrated ${empCount} employees to Firestore.`);

  // 2. Migrate Payouts
  let payCount = 0;
  let totalGrossSum = 0;
  let totalNetSum = 0;

  for (let i = 0; i < payouts.length; i += 400) {
    const chunk = payouts.slice(i, i + 400);
    const batch = db.batch();

    for (const pay of chunk) {
      if (!pay.employee_id || !pay.month || !pay.year) continue;

      const empId = String(pay.employee_id).trim();
      const month = String(pay.month).trim();
      const year = parseInt(pay.year, 10);
      const gross = parseFloat(pay.gross_pay) || 0;
      const tds = parseFloat(pay.tds) || 0;
      const net = parseFloat(pay.net_pay) || (gross - tds);

      totalGrossSum += gross;
      totalNetSum += net;

      // Composite document ID: {year}_{month}_{employeeId}
      const docId = `${year}_${month}_${empId}`;
      const ref = db.collection('payouts').doc(docId);

      batch.set(ref, {
        employeeId: empId,
        employeeName: pay.name || '',
        employeeType: 'Consultant',
        payrollMonth: month,
        payrollYear: year,
        grossPayout: gross,
        tds: tds,
        deductions: 0,
        netPayout: net,
        paymentStatus: pay.status || 'paid',
        sourceSheet: `${month} ${year}`,
        createdAt: pay.created_at || new Date().toISOString(),
        updatedAt: FieldValue.serverTimestamp()
      }, { merge: true });

      payCount++;
    }
    await batch.commit();
  }

  console.log(`Migrated ${payCount} payout records to Firestore.`);
  console.log(`Reconciliation Totals: Total Gross: ₹${totalGrossSum.toLocaleString('en-IN')}, Total Net: ₹${totalNetSum.toLocaleString('en-IN')}`);
}

migrate().catch(console.error);
