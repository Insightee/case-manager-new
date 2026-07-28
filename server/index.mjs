import express from 'express';
import cors from 'cors';
import { initializeApp, cert, getApps } from 'firebase-admin/app';
import { getFirestore, FieldValue } from 'firebase-admin/firestore';

const app = express();
app.use(cors({ origin: true }));
app.use(express.json({ limit: '10mb' }));

// Request logging middleware
app.use((req, res, next) => {
  console.log(`[${new Date().toISOString()}] ${req.method} ${req.url}`);
  next();
});

// Initialize Firebase Admin SDK
if (!getApps().length) {
  if (process.env.FIREBASE_SERVICE_ACCOUNT_KEY) {
    try {
      const serviceAccount = JSON.parse(process.env.FIREBASE_SERVICE_ACCOUNT_KEY);
      initializeApp({ credential: cert(serviceAccount) });
      console.log('Initialized Firebase Admin with FIREBASE_SERVICE_ACCOUNT_KEY');
    } catch (e) {
      console.error('Failed to parse FIREBASE_SERVICE_ACCOUNT_KEY, falling back to default:', e.message);
      initializeApp();
    }
  } else {
    initializeApp();
    console.log('Initialized Firebase Admin with default credentials');
  }
}

const db = getFirestore();

const SYNC_SECRET = process.env.SYNC_SECRET || 'insighte_payout_portal_secret_2026';
const VALID_MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'
];

// Root Endpoint
app.get('/', (req, res) => {
  res.json({
    service: 'Insighte Payout Backend',
    status: 'active',
    version: '1.0.0',
    endpoints: ['/health', '/api/sync/sheet', '/api/admin/payout']
  });
});

// Health Check Endpoint
app.get('/health', (req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

// Middleware: Authenticate Sync Secret
function authenticateSyncSecret(req, res, next) {
  const secretHeader = req.headers['x-sync-secret'];
  if (!secretHeader || secretHeader !== SYNC_SECRET) {
    return res.status(401).json({ error: 'Unauthorized: Invalid or missing sync secret header.' });
  }
  next();
}

/**
 * Endpoint: POST /api/sync/sheet
 * Accepts batch payout records from Google Apps Script for a specific sheet/month.
 */
app.post('/api/sync/sheet', authenticateSyncSecret, async (req, res) => {
  const startTime = Date.now();
  const { idempotencyKey, sheetName, month, year, rows } = req.body;

  if (!month || !year || !Array.isArray(rows)) {
    return res.status(400).json({ error: 'Malformed request: month, year, and rows array are required.' });
  }

  const normalizedMonth = month.charAt(0).toUpperCase() + month.slice(1).toLowerCase();
  if (!VALID_MONTHS.includes(normalizedMonth)) {
    return res.status(400).json({ error: `Invalid month: ${month}` });
  }

  const parsedYear = parseInt(year, 10);
  if (isNaN(parsedYear) || parsedYear < 2020 || parsedYear > 2035) {
    return res.status(400).json({ error: `Invalid year: ${year}` });
  }

  const syncRunId = idempotencyKey || `sync_${normalizedMonth}_${parsedYear}_${startTime}`;
  const syncRunRef = db.collection('syncRuns').doc(syncRunId);

  let rowsCreated = 0;
  let rowsUpdated = 0;
  let rowsRejected = 0;
  const errors = [];

  const batch = db.batch();

  for (let i = 0; i < rows.length; i++) {
    const row = rows[i];
    const rowNum = row.rowNumber || (i + 2);
    const employeeId = String(row.employeeId || '').trim();
    const name = String(row.name || '').trim();
    const role = String(row.role || 'Consultant').trim();

    if (!employeeId || !/^\d{3,5}$/.test(employeeId)) {
      rowsRejected++;
      errors.push({ row: rowNum, employeeId, error: 'Invalid or missing employee ID format.' });
      continue;
    }

    if (!name) {
      rowsRejected++;
      errors.push({ row: rowNum, employeeId, error: 'Missing employee name.' });
      continue;
    }

    const grossPay = parseFloat(row.grossPay) || 0;
    const tds = parseFloat(row.tds) || 0;
    const deductions = parseFloat(row.deductions) || 0;
    const netPay = parseFloat(row.netPay) || 0;

    if (grossPay <= 0) {
      rowsRejected++;
      errors.push({ row: rowNum, employeeId, error: 'Gross payout must be greater than 0.' });
      continue;
    }

    // Financial Reconciliation Check: grossPay - tds - deductions === netPay (allowing ±1.0 rounding tolerance)
    const expectedNet = grossPay - tds - deductions;
    if (Math.abs(expectedNet - netPay) > 1.0) {
      rowsRejected++;
      errors.push({
        row: rowNum,
        employeeId,
        error: `Financial reconciliation failed: Gross (${grossPay}) - TDS (${tds}) - Deductions (${deductions}) != Net (${netPay})`
      });
      continue;
    }

    // Upsert Employee Record
    const empRef = db.collection('employees').doc(employeeId);
    const empEmail = row.email || `${name.toLowerCase().replace(/[^a-z0-9]/g, '.')}@insighte.in`;
    batch.set(empRef, {
      employeeId,
      name,
      email: empEmail,
      role,
      updatedAt: FieldValue.serverTimestamp()
    }, { merge: true });

    // Document ID format: payouts/{year}_{month}_{employeeId}
    const docId = `${parsedYear}_${normalizedMonth}_${employeeId}`;
    const payoutRef = db.collection('payouts').doc(docId);

    const payoutData = {
      employeeId,
      employeeName: name,
      employeeType: role,
      payrollMonth: normalizedMonth,
      payrollYear: parsedYear,
      grossPayout: grossPay,
      tds: tds,
      deductions: deductions,
      netPayout: netPay,
      paymentStatus: 'paid',
      sourceSheet: sheetName || `${normalizedMonth} ${parsedYear}`,
      sourceRow: rowNum,
      updatedAt: FieldValue.serverTimestamp()
    };

    batch.set(payoutRef, payoutData, { merge: true });
    rowsUpdated++;
  }

  // Commit Batch
  try {
    await batch.commit();
  } catch (err) {
    console.error('Batch commit failed:', err);
    return res.status(500).json({ error: 'Database transaction failed: ' + err.message });
  }

  const completedAt = new Date().toISOString();
  const syncRunSummary = {
    syncRunId,
    sheetName: sheetName || `${normalizedMonth} ${parsedYear}`,
    payrollMonth: normalizedMonth,
    payrollYear: parsedYear,
    startedAt: new Date(startTime).toISOString(),
    completedAt,
    rowsReceived: rows.length,
    rowsCreated,
    rowsUpdated,
    rowsRejected,
    errors,
    initiatedBy: 'Google Apps Script'
  };

  try {
    await syncRunRef.set(syncRunSummary);
  } catch (logErr) {
    console.error('Failed to save sync log:', logErr);
  }

  res.json({
    status: 'success',
    summary: {
      syncRunId,
      month: normalizedMonth,
      year: parsedYear,
      rowsReceived: rows.length,
      rowsSynced: rowsUpdated,
      rowsRejected,
      errorsCount: errors.length
    }
  });
});

/**
 * Endpoint: POST /api/admin/payout
 * Endpoint for authenticated manual admin modifications (overrides).
 */
app.post('/api/admin/payout', authenticateSyncSecret, async (req, res) => {
  const { action, employeeId, name, month, year, grossPay, tds, netPay } = req.body;

  if (!employeeId || !month || !year) {
    return res.status(400).json({ error: 'employeeId, month, and year are required.' });
  }

  const docId = `${year}_${month}_${employeeId}`;
  const payoutRef = db.collection('payouts').doc(docId);

  if (action === 'delete') {
    await payoutRef.delete();
    return res.json({ status: 'success', message: `Deleted payout ${docId}` });
  }

  const parsedGross = parseFloat(grossPay) || 0;
  const parsedTds = parseFloat(tds) || 0;
  const parsedNet = parseFloat(netPay) || (parsedGross - parsedTds);

  await payoutRef.set({
    employeeId,
    employeeName: name,
    payrollMonth: month,
    payrollYear: parseInt(year, 10),
    grossPayout: parsedGross,
    tds: parsedTds,
    netPayout: parsedNet,
    paymentStatus: 'paid',
    updatedAt: FieldValue.serverTimestamp()
  }, { merge: true });

  res.json({ status: 'success', message: `Upserted payout ${docId}` });
});

// JSON 404 Catch-All Handler
app.use((req, res) => {
  res.status(404).json({
    error: 'Not Found',
    message: `Endpoint ${req.method} ${req.url} does not exist.`
  });
});

const PORT = process.env.PORT || 8080;
app.listen(PORT, () => {
  console.log(`Insighte Payout Backend running on port ${PORT}`);
});
