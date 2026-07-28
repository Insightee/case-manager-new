
// fetch is built-in in Node 24


const SHEET_ID = '11ABJe6Hvno0AjOxXgOxmlg-waCkpTixzSH8qUdsCOPo';
const months = [
  'April 2025', 'May 2025', 'June 2025', 'July 2025', 'August 2025',
  'September 2025', 'October 2025', 'November 2025', 'December 2025',
  'January 2026', 'February 2026', 'March 2026', 'April 2026'
];

async function checkSheets() {
  for (const sheet of months) {
    const url = `https://docs.google.com/spreadsheets/d/${SHEET_ID}/gviz/tq?tqx=out:csv&sheet=${encodeURIComponent(sheet)}`;
    const res = await fetch(url);
    if (!res.ok) {
      console.log(`${sheet}: Failed to fetch`);
      continue;
    }
    const text = await res.text();
    if (text.includes('1642')) {
      console.log(`${sheet}: Found 1642!`);
      const lines = text.split('\n');
      const matching = lines.filter(l => l.includes('1642'));
      matching.forEach(l => console.log(`  ${l}`));
    } else {
      console.log(`${sheet}: Not found`);
    }
  }
}

checkSheets();
