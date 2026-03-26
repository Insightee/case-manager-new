/**
 * ═══════════════════════════════════════════════════════
 * INSIGHTE PAYOUT PORTAL — Google Sheets → Supabase Sync
 * ═══════════════════════════════════════════════════════
 * 
 * INSTALLATION:
 * 1. Open your Google Spreadsheet
 * 2. Go to Extensions → Apps Script
 * 3. Delete any existing code in the editor
 * 4. Paste this entire file
 * 5. Click Save
 * 6. Reload the spreadsheet — a new "Insighte" menu will appear
 */

var SUPABASE_URL = "https://dhlxkzvgdkytcyguxvxr.supabase.co";
var SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRobHhrenZnZGt5dGN5Z3V4dnhyIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzM1ODM0NzYsImV4cCI6MjA4OTE1OTQ3Nn0.GQybPpaAFMiePAneZhoVejM0SLVEPYW7W5gLeOiUY1A";

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
    "All existing data for " + parsed.month + " " + parsed.year + " will be replaced.\n\nContinue?",
    ui.ButtonSet.YES_NO);

  if (confirm !== ui.Button.YES) return;

  try {
    var result = processSheet(sheet, parsed.month, parsed.year, false);
    ui.alert("Sync Complete",
      sheetName + " synced successfully!\n\n" +
      result.employees + " employees updated\n" +
      result.payouts + " payout records inserted",
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
    names.join(", ") + "\n\nALL existing payout data will be replaced.\n\nContinue?",
    ui.ButtonSet.YES_NO);

  if (confirm !== ui.Button.YES) return;

  // Clear all existing data
  supabaseDelete("payouts", "id", "neq", "00000000-0000-0000-0000-000000000000");
  supabaseDelete("employees", "employee_id", "neq", "0000");

  var totalPay = 0;
  var allEmployees = {};
  var errors = [];

  for (var i = 0; i < monthSheets.length; i++) {
    var parsed = parseSheetName(monthSheets[i].getName());
    try {
      var result = processSheet(monthSheets[i], parsed.month, parsed.year, true, allEmployees);
      totalPay += result.payouts;
      SpreadsheetApp.getActiveSpreadsheet().toast(
        monthSheets[i].getName() + ": " + result.payouts + " records", "Syncing...", 3);
    } catch (e) {
      errors.push(monthSheets[i].getName() + ": " + e.message);
    }
  }

  // Batch upsert all employees
  var empArray = objectValues(allEmployees);
  for (var i = 0; i < empArray.length; i += 50) {
    supabaseUpsert("employees", empArray.slice(i, i + 50));
  }

  var msg = "Sync complete!\n\n" +
    empArray.length + " employees\n" +
    totalPay + " payout records\n" +
    monthSheets.length + " months synced";
  if (errors.length > 0) {
    msg += "\n\nErrors:\n" + errors.join("\n");
  }
  ui.alert("Sync Results", msg, ui.ButtonSet.OK);
}

// ─── PROCESS ONE SHEET ───
function processSheet(sheet, month, year, skipEmployeeUpsert, sharedEmployeeMap) {
  var data = sheet.getDataRange().getValues();
  if (data.length < 2) throw new Error("Sheet is empty");

  var rows = [];
  var employees = sharedEmployeeMap || {};

  for (var i = 1; i < data.length; i++) {
    var row = [];
    for (var j = 0; j < data[i].length; j++) {
      row.push(String(data[i][j]).trim());
    }
    var parsed = extractRowData(row);
    if (!parsed || parsed.grossPay <= 0) continue;

    rows.push({
      employee_id: parsed.employeeId,
      name: parsed.name,
      month: month,
      year: year,
      gross_pay: parsed.grossPay,
      tds: parsed.tds,
      net_pay: parsed.netPay,
      status: "paid"
    });

    if (!employees[parsed.employeeId]) {
      employees[parsed.employeeId] = {
        employee_id: parsed.employeeId,
        name: parsed.name,
        email: parsed.name.toLowerCase().replace(/[^a-z0-9]/g, ".") + "@insighte.in",
        role: parsed.role
      };
    }
  }

  if (rows.length === 0) throw new Error("No valid payout records found");

  // Delete existing payouts for this month (single-sheet mode only)
  if (!skipEmployeeUpsert) {
    supabaseDeleteMonth(month, year);
  }

  // Insert payouts in batches
  for (var i = 0; i < rows.length; i += 100) {
    supabaseInsert("payouts", rows.slice(i, i + 100));
  }

  // Upsert employees (single-sheet mode only)
  if (!skipEmployeeUpsert) {
    var empArr = objectValues(employees);
    for (var i = 0; i < empArr.length; i += 50) {
      supabaseUpsert("employees", empArr.slice(i, i + 50));
    }
  }

  return { employees: objectKeys(employees).length, payouts: rows.length };
}

// ─── ROW PARSING ───
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

  // No role column
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

function objectValues(obj) {
  var result = [];
  var keys = Object.keys(obj);
  for (var i = 0; i < keys.length; i++) {
    result.push(obj[keys[i]]);
  }
  return result;
}

function objectKeys(obj) {
  return Object.keys(obj);
}

// ─── SUPABASE REST API ───
function supabaseRequest(method, path, body, prefer) {
  var headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": "Bearer " + SUPABASE_KEY,
    "Content-Type": "application/json"
  };
  if (prefer) {
    headers["Prefer"] = prefer;
  }

  var options = {
    "method": method,
    "headers": headers,
    "muteHttpExceptions": true
  };

  if (body) {
    options["payload"] = JSON.stringify(body);
  }

  var url = SUPABASE_URL + "/rest/v1/" + path;
  var response = UrlFetchApp.fetch(url, options);
  var code = response.getResponseCode();

  if (code >= 400) {
    throw new Error("Supabase " + method + " " + path + ": HTTP " + code + " - " + response.getContentText());
  }
  return response;
}

function supabaseInsert(table, rows) {
  supabaseRequest("POST", table, rows, "return=minimal");
}

function supabaseUpsert(table, rows) {
  supabaseRequest("POST", table + "?on_conflict=employee_id", rows, "return=minimal,resolution=merge-duplicates");
}

function supabaseDelete(table, column, operator, value) {
  supabaseRequest("DELETE", table + "?" + column + "=" + operator + "." + value);
}

function supabaseDeleteMonth(month, year) {
  supabaseRequest("DELETE", "payouts?month=eq." + encodeURIComponent(month) + "&year=eq." + year);
}
