# Database & Backend Architecture (Firebase & Cloud Run)

## 1. Client Configuration
- **Database Engine**: Firebase Firestore
- **Client Configuration Utility**: `utils/firebase.ts`
- **Security Rules**: Read-only access to `/employees` and `/payouts` collections for client frontend.

## 2. Backend Cloud Run API
- **Location**: `server/`
- **Service Name**: `insighte-payout-backend`
- **Endpoints**:
  - `POST /api/sync/sheet`: Batch sync payouts from Google Apps Script with financial reconciliation & deduplication.
  - `POST /api/admin/payout`: Authenticated admin overrides.
- **Authentication**: `X-Sync-Secret` header verified against Google Secret Manager / Environment variable (`SYNC_SECRET`).

## 3. Collections Schema
- `employees/{employeeId}`: Employee profile documents.
- `payouts/{year}_{month}_{employeeId}`: Monthly payout documents.
- `syncRuns/{syncRunId}`: Audit log of every Google Apps Script sync execution.

## 4. Google Apps Script Integration
- **Script File**: `scripts/sync-to-firebase.gs.js`
- **Configuration**: Uses `ScriptProperties` (`BACKEND_URL`, `SYNC_SECRET`).
