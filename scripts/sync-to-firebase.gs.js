/**
 * ══════════════════════════════════════════════════════════════
 * INSIGHTE PAYOUT PORTAL — Google Sheets → Backend Sync
 * ══════════════════════════════════════════════════════════════
 * 
 * Target Endpoint: Cloud Run / Cloud Function API
 * Security: Uses X-Sync-Secret header stored in Script Properties.
 * 
 * SETUP INSTRUCTIONS:
 * 1. Open Google Sheet → Extensions → Apps Script
 * 2. Paste this code into Code.gs
 * 3. Open Project Settings (⚙️) → Script Properties
 * 4. Add the following properties:
 *    - BACKEND_URL: https://your-cloud-run-service-url.a.run.app/api/sync/sheet
 *    - SYNC_SECRET: insighte_payout_portal_secret_2026
 * 5. Save & Reload spreadsheet. A new "Insighte" menu will appear.
 */

var VALID_MONTHS = [
  "january","february","march","april","may","june",
  "july","august","september","october","november","december"
];

var MONTH_PROPER = {
  "january":"January","february":"February","march":"March",
  "april":"April","may":"May","june":"June",
  "july":"July","august":"August","september":"September",
  "october":"October","november":"November","december":"December"
};

// ─── MENU ───
function onOpen() {
  var ui = SpreadsheetApp.getUi();
  ui.createMenu("Insighte")
    .addItem("Sync Current Sheet", "syncCurrentSheet")
    .addSeparator()
    .addItem("Sync All Sheets", "syncAllSheets")
    .addToUi();
}

// ─── GET SCRIPT PROPERTIES ───
function getBackendConfig() {
  var props = PropertiesService.getScriptProperties();
  var backendUrl = props.getProperty("BACKEND_URL") || "https://insighte-payout-backend-xyz.a.run.app/api/sync/sheet";
  var syncSecret = props.getProperty("SYNC_SECRET") || "insighte_payout_portal_secret_2026";
  return { url: backendUrl, secret: syncSecret };
}

// ─── SYNC CURRENT SHEET ───
function syncCurrentSheet() {
  var ui = SpreadsheetApp.getUi();
  var sheet = SpreadsheetApp.getActiveSheet();
  var sheetName = sheet.getName();
  var parsed = parseSheetName(sheetName);

  if (!parsed) {
    ui.alert("Sheet Name Error",
      '"' + sheetName + '" does not look like a month sheet.\n\nExpected: "April 2025", "January 2026", etc.',
      ui.ButtonSet.OK);
    return;
  }

  var confirm = ui.alert("Sync to Payout Portal",
    'This will sync "' + sheetName + '" to the Payout Portal.\n\n' +
    "Data for " + parsed.month + " " + parsed.year + " will be updated.\n\nContinue?",
    ui.ButtonSet.YES_NO);

  if (confirm !== ui.Button.YES) return;

  try {
    var result = processAndSendSheet(sheet, parsed.month, parsed.year);
    ui.alert("Sync Complete",
      sheetName + " synced successfully!\n\n" +
      "Records Received: " + result.summary.rowsReceived + "\n" +
      "Records Synced: " + result.summary.rowsSynced + "\n" +
      "Records Rejected: " + result.summary.rowsRejected + "\n" +
      (result.summary.errorsCount > 0 ? "\nWarnings/Errors: " + result.summary.errorsCount : ""),
      ui.ButtonSet.OK);
  } catch (e) {
    ui.alert("Sync Failed", "Error: " + e.message, ui.ButtonSet.OK);
    Logger.log(e);
  }
}

// ─── SYNC ALL SHEETS ───
function syncAllSheets() {
  var ui = SpreadsheetApp.getUi();
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheets = ss.getSheets();
  var monthSheets = [];

  for (var i = 0; i < sheets.length; i++) {
    if (parseSheetName(sheets[i].getName())) {
      monthSheets.push(sheets[i]);
    }
  }

  if (monthSheets.length === 0) {
    ui.alert("No month sheets found.");
    return;
  }

  var names = [];
  for (var i = 0; i < monthSheets.length; i++) {
    names.push(monthSheets[i].getName());
  }

  var confirm = ui.alert("Sync ALL Sheets",
    "This will sync " + monthSheets.length + " month sheets:\n\n" +
    names.join(", ") + "\n\nContinue?",
    ui.ButtonSet.YES_NO);

  if (confirm !== ui.Button.YES) return;

  var totalSynced = 0;
  var errors = [];

  for (var i = 0; i < monthSheets.length; i++) {
    var parsed = parseSheetName(monthSheets[i].getName());
    try {
      var result = processAndSendSheet(monthSheets[i], parsed.month, parsed.year);
      totalSynced += result.summary.rowsSynced;
      SpreadsheetApp.getActiveSpreadsheet().toast(
        monthSheets[i].getName() + ": " + result.summary.rowsSynced + " records", "Syncing...", 3);
    } catch (e) {
      errors.push(monthSheets[i].getName() + ": " + e.message);
    }
  }

  var msg = "Sync complete!\n\n" +
    totalSynced + " payout records updated across " + monthSheets.length + " months.";
  if (errors.length > 0) {
    msg += "\n\nErrors:\n" + errors.join("\n");
  }
  ui.alert("Sync Results", msg, ui.ButtonSet.OK);
}

// ─── PROCESS & SEND SHEET TO BACKEND ───
function processAndSendSheet(sheet, month, year) {
  var data = sheet.getDataRange().getValues();
  if (data.length < 2) throw new Error("Sheet is empty");

  var rows = [];

  for (var i = 1; i < data.length; i++) {
    var rowParts = [];
    for (var j = 0; j < data[i].length; j++) {
      rowParts.push(String(data[i][j]).trim());
    }
    var parsedRow = extractRowData(rowParts);
    if (!parsedRow || parsedRow.grossPay <= 0) continue;

    rows.push({
      employeeId: parsedRow.employeeId,
      name: parsedRow.name,
      role: parsedRow.role,
      grossPay: parsedRow.grossPay,
      tds: parsedRow.tds,
      netPay: parsedRow.netPay,
      rowNumber: i + 1
    });
  }

  if (rows.length === 0) throw new Error("No valid payout records found in sheet");

  var config = getBackendConfig();
  var idempotencyKey = "sync_" + month.toLowerCase() + "_" + year + "_" + Date.now();

  var payload = {
    idempotencyKey: idempotencyKey,
    sheetName: sheet.getName(),
    month: month,
    year: year,
    rows: rows
  };

  var options = {
    "method": "post",
    "contentType": "application/json",
    "headers": {
      "X-Sync-Secret": config.secret
    },
    "payload": JSON.stringify(payload),
    "muteHttpExceptions": true
  };

  var response = UrlFetchApp.fetch(config.url, options);
  var statusCode = response.getResponseCode();
  var responseText = response.getContentText();

  if (statusCode >= 400) {
    throw new Error("Backend Error (" + statusCode + "): " + responseText);
  }

  return JSON.parse(responseText);
}

// ─── ROW PARSING HELPER ───
function extractRowData(parts) {
  var first = parts[0] || "";

  if (isRoleField(first)) {
    var role = first.toLowerCase().indexOf("employee") >= 0 ? "Employee" : "Consultant";
    var employeeId, name;
    if (isNumericId(parts[1])) { employeeId = parts[1]; name = parts[2]; }
    else if (isNumericId(parts[2])) { employeeId = parts[2]; name = parts[1]; }
    else { return null; }
    if (!employeeId || !name) return null;
    return {
      employeeId: employeeId, name: name, role: role,
      grossPay: toNum(parts[3]), tds: toNum(parts[4]), netPay: toNum(parts[5])
    };
  }

  var employeeId2, name2;
  if (isNumericId(parts[0])) { employeeId2 = parts[0]; name2 = parts[1]; }
  else if (isNumericId(parts[1])) { employeeId2 = parts[1]; name2 = parts[0]; }
  else { return null; }
  if (!employeeId2 || !name2) return null;
  return {
    employeeId: employeeId2, name: name2, role: "Consultant",
    grossPay: toNum(parts[2]), tds: toNum(parts[3]), netPay: toNum(parts[4])
  };
}

// ─── HELPERS ───
function parseSheetName(name) {
  var parts = name.trim().split(/\s+/);
  if (parts.length !== 2) return null;
  var monthKey = parts[0].toLowerCase();
  var year = parseInt(parts[1], 10);
  if (VALID_MONTHS.indexOf(monthKey) === -1) return null;
  if (isNaN(year) || year < 2020 || year > 2035) return null;
  return { month: MONTH_PROPER[monthKey], year: year };
}

function isNumericId(val) {
  return /^\d{3,5}$/.test(String(val).trim());
}

function isRoleField(val) {
  var v = String(val).toLowerCase().trim();
  return v.indexOf("consultant") === 0 || v.indexOf("employee") === 0 || v.indexOf("consul") === 0;
}

function toNum(val) {
  if (val === undefined || val === null) return 0;
  return parseFloat(String(val).replace(/,/g, "").replace(/[^\d.\-]/g, "")) || 0;
}
