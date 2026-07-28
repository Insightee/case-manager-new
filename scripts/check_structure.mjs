
async function checkStructure() {
  const months = ['October 2025', 'January 2026', 'April 2026'];
  const SHEET_ID = '11ABJe6Hvno0AjOxXgOxmlg-waCkpTixzSH8qUdsCOPo';
  for (const sheet of months) {
    const url = `https://docs.google.com/spreadsheets/d/${SHEET_ID}/gviz/tq?tqx=out:csv&sheet=${encodeURIComponent(sheet)}`;
    const res = await fetch(url);
    const text = await res.text();
    console.log(`--- ${sheet} ---`);
    console.log(text.split('\n').slice(0, 5).join('\n'));
  }
}
checkStructure();
