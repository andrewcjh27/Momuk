#!/usr/bin/env node
// Round-trip the dish dataset between momuk-data.js and momuk-data.csv.
//
//   node tools/sync-data.js to-csv    momuk-data.js  -> momuk-data.csv
//   node tools/sync-data.js to-js     momuk-data.csv -> momuk-data.js
//
// Edit the CSV in a spreadsheet, run to-js, commit both.

const fs = require('fs');
const path = require('path');
const ROOT = path.join(__dirname, '..');
const JS = path.join(ROOT, 'momuk-data.js');
const CSV = path.join(ROOT, 'momuk-data.csv');
const COLS = ['id','ko','en','cuisine','temp','soup','spice','heavy','price','speed','solo','share','ubiq','tags'];
const NUM = new Set(['soup','spice','heavy','price','solo','share','ubiq']);

function load() {
  global.window = global;
  require(JS);
  return global.MOMUK_DATA;
}

function toCsv() {
  const rows = load().map(d =>
    COLS.map(c => (c === 'tags' ? d.tags.join('|') : String(d[c]))).join(','));
  fs.writeFileSync(CSV, COLS.join(',') + '\n' + rows.join('\n') + '\n');
  console.log('wrote ' + CSV + ' (' + rows.length + ' dishes)');
}

function toJs() {
  const lines = fs.readFileSync(CSV, 'utf8').trim().split('\n');
  const head = lines[0].split(',');
  if (head.join(',') !== COLS.join(',')) {
    console.error('Header mismatch.\n  expected: ' + COLS.join(',') + '\n  found:    ' + head.join(','));
    process.exit(1);
  }

  const dishes = [], seen = new Set(), problems = [];
  lines.slice(1).forEach((line, i) => {
    if (!line.trim()) return;
    const cells = line.split(',');
    const at = 'row ' + (i + 2);
    if (cells.length !== COLS.length) {
      problems.push(at + ': expected ' + COLS.length + ' columns, found ' + cells.length +
                    ' (commas inside a field? use | to separate tags)');
      return;
    }
    const d = {};
    COLS.forEach((c, j) => {
      const raw = cells[j].trim();
      if (c === 'tags') d.tags = raw ? raw.split('|').map(s => s.trim()).filter(Boolean) : [];
      else if (NUM.has(c)) {
        const n = Number(raw);
        if (!Number.isFinite(n)) problems.push(at + ' (' + d.ko + '): ' + c + ' is not a number: "' + raw + '"');
        d[c] = n;
      } else d[c] = raw;
    });

    if (!d.id) problems.push(at + ': missing id');
    if (seen.has(d.id)) problems.push(at + ': duplicate id "' + d.id + '"');
    seen.add(d.id);
    if (!['hot','cold','room'].includes(d.temp)) problems.push(at + ' (' + d.ko + '): temp must be hot|cold|room, found "' + d.temp + '"');
    if (!['fast','sit'].includes(d.speed)) problems.push(at + ' (' + d.ko + '): speed must be fast|sit, found "' + d.speed + '"');
    [['soup',0,3],['spice',0,3],['heavy',0,3],['price',1,3],['ubiq',1,3],['solo',0,1],['share',0,1]]
      .forEach(([c, lo, hi]) => {
        if (d[c] < lo || d[c] > hi) problems.push(at + ' (' + d.ko + '): ' + c + ' must be ' + lo + '-' + hi + ', found ' + d[c]);
      });
    dishes.push(d);
  });

  if (problems.length) {
    console.error('Not written — ' + problems.length + ' problem(s):');
    problems.forEach(p => console.error('  ' + p));
    process.exit(1);
  }

  const pad = (s, n) => s + ' '.repeat(Math.max(0, n - [...s].reduce((w, ch) => w + (ch.charCodeAt(0) > 0x2e80 ? 2 : 1), 0)));
  // Keep the generated file browsable: group by cuisine, in first-seen order.
  const order = [];
  dishes.forEach(d => { if (!order.includes(d.cuisine)) order.push(d.cuisine); });
  const grouped = [];
  order.forEach(c => {
    grouped.push({ comment: c });
    dishes.filter(d => d.cuisine === c).forEach(d => grouped.push(d));
  });

  const line = d =>
    "{ id:'" + d.id + "'," + ' '.repeat(Math.max(1, 24 - d.id.length)) +
    "ko:'" + d.ko + "', " + pad('', 0) +
    "en:'" + d.en + "', cuisine:'" + d.cuisine + "', temp:'" + d.temp + "', soup:" + d.soup +
    ", spice:" + d.spice + ", heavy:" + d.heavy + ", price:" + d.price + ", speed:'" + d.speed +
    "', solo:" + d.solo + ", share:" + d.share + ", ubiq:" + d.ubiq +
    ", tags:[" + d.tags.map(t => "'" + t + "'").join(',') + "] }";

  const body = grouped.map((d, i) => {
    if (d.comment) return (i ? '\n' : '') + '// \u2500\u2500 ' + d.comment + ' \u2500\u2500';
    const isLast = i === grouped.length - 1;
    return line(d) + (isLast ? '' : ',');
  }).join('\n');

  const header = fs.readFileSync(JS, 'utf8').split('window.MOMUK_DATA')[0];
  fs.writeFileSync(JS, header + 'window.MOMUK_DATA = [\n' + body.replace(/,(\s*)$/, '$1') + '\n];\n');
  console.log('wrote ' + JS + ' (' + dishes.length + ' dishes, all valid)');
}

const mode = process.argv[2];
if (mode === 'to-csv') toCsv();
else if (mode === 'to-js') toJs();
else { console.error('usage: node tools/sync-data.js to-csv|to-js'); process.exit(1); }
