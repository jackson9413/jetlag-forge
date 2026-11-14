'use strict';

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => (
  { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
));

let SAMPLES = [];
let PROFILES = [];
let CURRENT = null;

// ---------------------------------------------------------------- helpers

function clockLabel(h) {
  // Report clocks are plain "HH:MM" strings from the engine.
  return h;
}

function alertColor(v) {
  if (v >= 70) return 'var(--good)';
  if (v >= 55) return 'var(--warn)';
  if (v >= 35) return '#ff8a3d';
  return 'var(--bad)';
}

function axisColor(v) {
  if (v >= 70) return 'var(--good)';
  if (v >= 55) return 'var(--warn)';
  if (v >= 38) return '#ff8a3d';
  return 'var(--bad)';
}

function severityPill(sev) {
  const map = { critical: 'pill-crit', high: 'pill-bad', medium: 'pill-warn', low: 'pill-info', info: 'pill-muted' };
  return '<span class="pill ' + (map[sev] || 'pill-muted') + '">' + esc(sev) + '</span>';
}

function verdictPill(v) {
  const map = { good: 'pill-good', workable: 'pill-warn', risky: 'pill-bad', danger: 'pill-bad', unknown: 'pill-muted' };
  return '<span class="pill ' + (map[v] || 'pill-muted') + '">' + esc(v) + '</span>';
}

function fmtShift(h) {
  if (Math.abs(h) < 0.05) return 'none';
  return (h > 0 ? '+' : '') + h.toFixed(1) + 'h';
}

// ---------------------------------------------------------------- rendering

function renderScore(report) {
  const s = report.score;
  const m = report.meta;
  const bandClass = 'band-' + s.band;
  let html = ''
    + '<div class="score-head">'
    + '  <div class="score-num ' + bandClass + '">' + s.overall.toFixed(1) + '</div>'
    + '  <div class="score-side">'
    + '    <div class="score-title ' + bandClass + '">' + esc(s.band_label) + '</div>'
    + '    <div class="score-sub">' + esc(m.title || 'Untitled trip') + ' &middot; ' + esc(m.profile_label) + '</div>'
    + '    <div class="score-meta" style="margin-top:8px">'
    + '      <span>Home <b>' + esc(m.home_place) + '</b></span>'
    + '      <span>Sleep <b>' + esc(m.home_sleep) + '-' + esc(m.home_wake) + '</b></span>'
    + '      <span>Chronotype <b>' + esc(m.chronotype) + '</b></span>'
    + '      <span>Melatonin <b>' + (m.melatonin_mg ? m.melatonin_mg + ' mg' : 'none') + '</b></span>'
    + '      <span>Max shift <b>' + fmtShift(s.max_shift_h) + '</b></span>'
    + '      <span>Sleep debt <b>' + s.total_sleep_debt_h.toFixed(1) + 'h</b></span>'
    + '    </div>'
    + '  </div>'
    + '</div>';

  html += '<div class="axes">';
  s.axis_order.forEach((axis) => {
    const v = s.axes[axis];
    html += ''
      + '<div class="axis-row">'
      + '  <div class="axis-name">' + esc(m.axis_labels[axis]) + '</div>'
      + '  <div class="axis-track"><div class="axis-fill" style="width:' + v + '%;background:' + axisColor(v) + '"></div></div>'
      + '  <div class="axis-val">' + v.toFixed(1) + '</div>'
      + '</div>';
  });
  html += '</div>';

  Object.keys(s.caps || {}).forEach((axis) => {
    html += '<div class="cap-note"><strong>' + esc(m.axis_labels[axis] || axis) + ' capped:</strong> ' + esc(s.caps[axis]) + '</div>';
  });
  return html;
}

function renderLegs(report) {
  if (!report.legs.length) return '';
  let html = '<div class="section"><div class="section-title">Flights</div><table>'
    + '<thead><tr><th>Route</th><th>Departure</th><th>Arrival</th><th class="mono">Hours</th>'
    + '<th class="mono">Shift</th><th>Direction</th><th>Notes</th></tr></thead><tbody>';
  report.legs.forEach((l) => {
    const notes = [];
    if (l.overnight) notes.push('overnight');
    if (l.red_eye_arrival) notes.push('red-eye arrival');
    if (l.crosses_date_line) notes.push('date line');
    html += '<tr>'
      + '<td><strong>' + esc(l.origin) + ' &rarr; ' + esc(l.dest) + '</strong></td>'
      + '<td class="mono">' + esc(l.dep_local) + '</td>'
      + '<td class="mono">' + esc(l.arr_local) + '</td>'
      + '<td class="mono">' + l.duration_h.toFixed(1) + '</td>'
      + '<td class="mono">' + fmtShift(l.effective_shift_h) + '</td>'
      + '<td>' + esc(l.direction) + '</td>'
      + '<td>' + (notes.length ? esc(notes.join(', ')) : '&mdash;') + '</td>'
      + '</tr>';
  });
  return html + '</tbody></table></div>';
}

function renderStays(report) {
  if (!report.stays.length) return '';
  let html = '';
  report.stays.forEach((st) => {
    const shiftTxt = Math.abs(st.effective_shift_h) < 0.05
      ? 'no clock shift'
      : fmtShift(st.effective_shift_h) + ' (' + st.direction + ')';
    html += '<div class="section"><div class="section-title">' + esc(st.place) + ' &middot; ' + esc(shiftTxt)
      + ' &middot; ' + st.nights_to_sync + ' nights to sync, ' + st.nights + ' booked</div>';

    st.days.forEach((d) => {
      const light = d.light;
      const bright = clockLabel(light.bright_start) + '-' + clockLabel(light.bright_end);
      const dim = clockLabel(light.dim_start) + '-' + clockLabel(light.dim_end);
      const peak = d.alertness.reduce((a, b) => (b.alertness > a.alertness ? b : a), d.alertness[0]);
      const trough = d.alertness.reduce((a, b) => (b.alertness < a.alertness ? b : a), d.alertness[0]);

      html += ''
        + '<div class="daycard">'
        + '  <div class="daycard-head">'
        + '    <span class="daycard-date">' + esc(d.date) + '</span>'
        + '    <span class="daycard-shift">Day ' + d.day_index + ' &middot; body clock reads ' + esc(d.body_clock_at_noon) + ' at local noon</span>'
        + '    <span class="pill ' + (d.residual_error_h === 0 ? 'pill-good' : 'pill-warn') + '">off by ' + Math.abs(d.residual_error_h).toFixed(1) + 'h</span>'
        + (d.arrival_day ? '    <span class="pill pill-info">arrival day</span>' : '')
        + '  </div>'
        + '  <div class="daycard-grid">'
        + '    <div class="stat"><div class="stat-label">Go to bed</div><div class="stat-value">' + esc(d.recommended_bed_local) + '</div><div class="stat-note">body wants ' + esc(d.body_bed_local) + '</div></div>'
        + '    <div class="stat"><div class="stat-label">Wake</div><div class="stat-value">' + esc(d.recommended_wake_local) + '</div><div class="stat-note">body wants ' + esc(d.body_wake_local) + '</div></div>'
        + '    <div class="stat"><div class="stat-label">Sleep</div><div class="stat-value">' + d.actual_sleep_h.toFixed(1) + 'h</div><div class="stat-note">latency ' + d.sleep_latency_h.toFixed(1) + 'h</div></div>'
        + '    <div class="stat"><div class="stat-label">Bright light</div><div class="stat-value">' + esc(bright) + '</div><div class="stat-note">' + (light.kind === 'advance' ? 'morning advances' : 'evening delays') + '</div></div>'
        + '    <div class="stat"><div class="stat-label">Dim light</div><div class="stat-value">' + esc(dim) + '</div><div class="stat-note">protect sleep</div></div>'
        + '    <div class="stat"><div class="stat-label">Caffeine until</div><div class="stat-value">' + esc(clockLabel(d.caffeine.cutoff)) + '</div><div class="stat-note">6h before bed</div></div>'
        + '    <div class="stat"><div class="stat-label">Peak alert</div><div class="stat-value" style="color:' + alertColor(peak.alertness) + '">' + peak.alertness.toFixed(0) + '</div><div class="stat-note">at ' + String(peak.hour).padStart(2, '0') + ':00 local</div></div>'
        + '    <div class="stat"><div class="stat-label">Trough</div><div class="stat-value" style="color:' + alertColor(trough.alertness) + '">' + trough.alertness.toFixed(0) + '</div><div class="stat-note">at ' + String(trough.hour).padStart(2, '0') + ':00 local</div></div>'
        + '  </div>';

      // Alertness sparkline
      html += '<div class="spark">';
      d.alertness.forEach((c) => {
        const cls = c.alertness >= 70 ? 'hi' : (c.alertness <= 35 ? 'lo' : '');
        html += '<div class="spark-bar ' + cls + '" style="height:' + Math.max(3, c.alertness) + '%;background:' + (c.alertness >= 70 ? 'var(--good)' : (c.alertness <= 35 ? '#6a3a3a' : 'var(--accent-dim)')) + '" title="' + String(c.hour).padStart(2, '0') + ':00 - ' + c.alertness.toFixed(0) + '"></div>';
      });
      html += '</div><div class="spark-axis"><span>00:00</span><span>06:00</span><span>12:00</span><span>18:00</span><span>24:00</span></div>';
      html += '</div>';
    });
    html += '</div>';
  });
  return html;
}

function renderEvents(report) {
  if (!report.events.length) return '';
  let html = '<div class="section"><div class="section-title">Critical events</div>';
  report.events.forEach((e) => {
    html += ''
      + '<div class="event-row">'
      + '  <span class="event-name">' + esc(e.name) + '</span>'
      + '  <span class="event-when">' + esc(e.when_local) + (e.place ? ' &middot; ' + esc(e.place) : '') + '</span>'
      + '  <span class="pill">body clock ' + esc(e.body_clock_time) + '</span>'
      + '  <span class="pill">alertness ' + e.alertness.toFixed(0) + '</span>'
      + '  ' + verdictPill(e.verdict)
      + '  <span class="event-advice">' + esc(e.advice) + '</span>'
      + '</div>';
  });
  return html + '</div>';
}

function renderFindings(report) {
  if (!report.findings.length) return '';
  let html = '<div class="section"><div class="section-title">Findings (' + report.findings.length + ')</div>';
  report.findings.forEach((f) => {
    html += ''
      + '<div class="finding sev-' + esc(f.severity) + '">'
      + '  <div class="finding-head">' + severityPill(f.severity) + '<span class="finding-title">' + esc(f.title) + '</span></div>'
      + '  <div class="finding-line"><b>Evidence</b>' + esc(f.evidence) + '</div>'
      + '  <div class="finding-line"><b>Why</b>' + esc(f.why) + '</div>'
      + '  <div class="finding-line finding-fix"><b>Fix</b>' + esc(f.fix) + '</div>'
      + '</div>';
  });
  return html + '</div>';
}

function renderPlan(report) {
  if (!report.plan.length) return '';
  let html = '<div class="section"><div class="section-title">Fix plan</div>';
  report.plan.forEach((p) => {
    html += ''
      + '<div class="plan-step">'
      + '  <div class="plan-num">' + p.step + '</div>'
      + '  <div>'
      + '    <div class="plan-when">' + esc(p.when) + '</div>'
      + '    <div class="plan-action">' + esc(p.action) + '</div>'
      + '    <div class="plan-why">' + esc(p.why) + '</div>'
      + '  </div>'
      + '</div>';
  });
  return html + '</div>';
}

function renderReport(report) {
  CURRENT = report;
  $('empty-state').hidden = true;
  $('report').hidden = false;
  let html = renderScore(report);
  html += renderLegs(report);
  html += renderStays(report);
  html += renderEvents(report);
  html += renderFindings(report);
  html += renderPlan(report);
  html += '<div class="disclaimer"><strong>Not medical advice.</strong> The circadian model here is a '
    + 'two-process approximation (homeostatic sleep pressure plus circadian alerting) with melatonin '
    + 'gating and published phase-shift rates. It is a planning aid. Talk to a clinician about '
    + 'melatonin, and get medical advice if you have a sleep disorder.</div>';
  $('report').innerHTML = html;
}

// ---------------------------------------------------------------- actions

async function analyze() {
  const brief = $('brief').value;
  const profile = $('profile').value || 'balanced';
  $('error-box').hidden = true;
  $('btn-analyze').disabled = true;
  try {
    const res = await fetch('/api/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ brief, profile }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'analysis failed');
    renderReport(data);
  } catch (err) {
    const box = $('error-box');
    box.textContent = err.message;
    box.hidden = false;
  } finally {
    $('btn-analyze').disabled = false;
  }
}

async function loadSample(id) {
  const res = await fetch('/api/samples/' + encodeURIComponent(id));
  const data = await res.json();
  $('brief').value = data.brief;
  document.querySelectorAll('.chip').forEach((c) => {
    c.classList.toggle('active', c.dataset.id === id);
  });
  analyze();
}

async function download(fmt) {
  const res = await fetch('/api/export', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ brief: $('brief').value, profile: $('profile').value, fmt }),
  });
  if (!res.ok) {
    const box = $('error-box');
    box.textContent = 'Export failed. Is the brief valid?';
    box.hidden = false;
    return;
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'jetlag-plan.' + (fmt === 'json' ? 'json' : 'md');
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

async function saveJourney() {
  const res = await fetch('/api/journeys', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ brief: $('brief').value, profile: $('profile').value }),
  });
  const data = await res.json();
  if (!res.ok) {
    const box = $('error-box');
    box.textContent = data.error || 'Could not save.';
    box.hidden = false;
    return;
  }
  loadHistory();
  $('history-drawer').hidden = false;
}

async function loadHistory() {
  const res = await fetch('/api/journeys');
  const rows = await res.json();
  const list = $('history-list');
  if (!rows.length) {
    list.innerHTML = '<p style="color:var(--fg-3);font-size:13px">No saved trips yet.</p>';
    return;
  }
  list.innerHTML = rows.map((r) => {
    let stars = '';
    for (let i = 1; i <= 5; i++) {
      stars += '<span class="star' + (i <= (r.rating || 0) ? ' on' : '') + '" data-id="' + r.id + '" data-v="' + i + '">&#9733;</span>';
    }
    return ''
      + '<div class="hist-item" data-id="' + r.id + '">'
      + '  <div class="hist-head">'
      + '    <div><div class="hist-title">' + esc(r.title) + '</div>'
      + '    <div class="hist-meta">' + esc(r.profile) + ' &middot; score ' + r.score + ' &middot; ' + esc(r.created_at || '') + '</div></div>'
      + '    <div class="stars">' + stars + '</div>'
      + '  </div>'
      + '  <textarea class="hist-notes" data-id="' + r.id + '" placeholder="How did the trip actually go?">' + esc(r.notes || '') + '</textarea>'
      + '  <div class="hist-actions">'
      + '    <button class="btn btn-ghost btn-sm" data-load="' + r.id + '">Open</button>'
      + '    <button class="btn btn-ghost btn-sm" data-save-notes="' + r.id + '">Save notes</button>'
      + '  </div>'
      + '</div>';
  }).join('');

  list.querySelectorAll('.star').forEach((star) => {
    star.addEventListener('click', async () => {
      const id = star.dataset.id;
      const value = parseInt(star.dataset.v, 10);
      const item = star.closest('.hist-item');
      const notes = item.querySelector('.hist-notes').value;
      await fetch('/api/journeys/' + id, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rating: value, notes }),
      });
      loadHistory();
    });
  });

  list.querySelectorAll('[data-load]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const res = await fetch('/api/journeys/' + btn.dataset.load);
      const data = await res.json();
      $('brief').value = data.brief;
      $('profile').value = data.profile || 'balanced';
      $('history-drawer').hidden = true;
      analyze();
    });
  });

  list.querySelectorAll('[data-save-notes]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const id = btn.dataset.saveNotes;
      const item = btn.closest('.hist-item');
      const notes = item.querySelector('.hist-notes').value;
      const rating = item.querySelectorAll('.star.on').length;
      await fetch('/api/journeys/' + id, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rating, notes }),
      });
      loadHistory();
    });
  });
}

// ---------------------------------------------------------------- bootstrap

async function init() {
  const [sRes, pRes] = await Promise.all([fetch('/api/samples'), fetch('/api/profiles')]);
  SAMPLES = await sRes.json();
  PROFILES = await pRes.json();

  const row = $('sample-row');
  row.innerHTML = SAMPLES.map((s) => '<button class="chip" data-id="' + esc(s.id) + '" title="' + esc(s.summary) + '">' + esc(s.title) + '</button>').join('');
  row.querySelectorAll('.chip').forEach((chip) => {
    chip.addEventListener('click', () => loadSample(chip.dataset.id));
  });

  $('profile').innerHTML = PROFILES.map((p) => '<option value="' + esc(p.id) + '">' + esc(p.label) + '</option>').join('');
  $('profile').addEventListener('change', () => {
    const p = PROFILES.find((x) => x.id === $('profile').value);
    $('profile-blurb').textContent = p ? p.blurb : '';
  });
  $('profile-blurb').textContent = PROFILES[0] ? PROFILES[0].blurb : '';

  $('btn-analyze').addEventListener('click', analyze);
  $('btn-export-md').addEventListener('click', () => download('md'));
  $('btn-export-json').addEventListener('click', () => download('json'));
  $('btn-save').addEventListener('click', saveJourney);
  $('btn-clear').addEventListener('click', () => {
    $('brief').value = '';
    $('report').hidden = true;
    $('empty-state').hidden = false;
    document.querySelectorAll('.chip').forEach((c) => c.classList.remove('active'));
  });
  $('btn-history').addEventListener('click', () => {
    $('history-drawer').hidden = false;
    loadHistory();
  });
  $('btn-close-history').addEventListener('click', () => { $('history-drawer').hidden = true; });

  $('brief').value = SAMPLES.length ? '' : '';
  if (SAMPLES.length) {
    await loadSample(SAMPLES[0].id);
  }
}

init();
