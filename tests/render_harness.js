/* Executes the real frontend render functions against live API data
   and asserts the produced HTML is correct.

   Usage: node render_harness.js <project-root> <port>

   This catches the class of bug where a renderer silently returns early
   and drops half of the report. */
'use strict';
const fs = require('fs');
const vm = require('vm');

const root = process.argv[2];
const port = process.argv[3] || '5000';

const source = fs.readFileSync(root + '/static/app.js', 'utf8')
  .replace(/\ninit\(\);\s*$/, '\n');

function makeEl() {
  return {
    innerHTML: '', textContent: '', value: '', hidden: false, disabled: false,
    classList: { add() {}, remove() {}, toggle() {}, contains() { return false; } },
    addEventListener() {}, dataset: {}, querySelector: () => makeEl(),
    querySelectorAll: () => [], appendChild() {}, remove() {},
  };
}

const els = {};
const sandbox = {
  document: {
    getElementById: (id) => { const e = els[id] = els[id] || makeEl(); return e; },
    querySelectorAll: () => [], createElement: () => makeEl(), body: makeEl(),
  },
  fetch: async () => ({ ok: true, json: async () => ({}), blob: async () => ({}) }),
  URL: { createObjectURL: () => '', revokeObjectURL() {} },
  console,
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
vm.createContext(sandbox);
vm.runInContext(source, sandbox);

const get = (p, opts) => fetch('http://127.0.0.1:' + port + p, opts);

(async () => {
  const samples = await (await get('/api/samples')).json();
  let failures = 0;

  for (const s of samples) {
    const detail = await (await get('/api/samples/' + s.id)).json();
    const analyzeRes = await get('/api/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ brief: detail.brief, profile: 'balanced' }),
    });
    if (!analyzeRes.ok) {
      failures++;
      console.log('FAIL ' + s.id + ': analyze returned ' + analyzeRes.status);
      continue;
    }
    const report = await analyzeRes.json();

    els['report'] = makeEl();
    sandbox.renderReport(report);
    const html = els['report'].innerHTML;
    const dayCount = report.stays.reduce((n, st) => n + st.days.length, 0);

    const checks = [
      ['html not empty', html.length > 2000],
      ['score rendered', html.includes('score-num')],
      ['5 axis rows', (html.match(/axis-row/g) || []).length === 5],
      ['all axis labels', report.score.axis_order.every((a) => html.includes(report.meta.axis_labels[a]))],
      ['one finding block each', (html.match(/finding sev-/g) || []).length === report.findings.length],
      ['one plan step each', (html.match(/class="plan-step"/g) || []).length === report.plan.length],
      ['one day card each', (html.match(/daycard-date/g) || []).length === dayCount],
      ['sparkline per hour per day', (html.match(/spark-bar/g) || []).length === dayCount * 24],
      ['events rendered', report.events.length === 0 || (html.match(/event-row/g) || []).length === report.events.length],
      ['flights rendered', report.legs.length === 0 || (html.match(/<tr>/g) || []).length >= report.legs.length],
      ['disclaimer present', html.includes('Not medical advice')],
      ['no undefined', !html.includes('undefined')],
      ['no NaN', !html.includes('NaN')],
      ['no [object Object]', !html.includes('[object Object]')],
      ['no raw null', !html.includes('>null<')],
    ];

    const bad = checks.filter((c) => !c[1]).map((c) => c[0]);
    if (bad.length) {
      failures++;
      console.log('FAIL ' + s.id + ': ' + bad.join('; '));
    } else {
      console.log('PASS ' + s.id.padEnd(22) + html.length + ' bytes');
    }
  }

  console.log(failures === 0 ? '\nALL RENDER CHECKS PASSED' : '\n' + failures + ' RENDER CHECKS FAILED');
  process.exit(failures === 0 ? 0 : 1);
})().catch((e) => {
  console.error('harness error: ' + (e && e.message));
  process.exit(1);
});
