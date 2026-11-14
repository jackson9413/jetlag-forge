# jetlag-forge

**A circadian jet-lag and body-clock planner for people who fly.**

Paste a trip brief. Get a night-by-night body-clock plan, a five-axis scorecard,
ranked findings with concrete fixes, and a prioritised action list.

Local-first: it runs entirely on your machine. No API keys, no network calls,
no LLM, no account. Your briefs never leave the box.

---

## What it actually does

Most jet-lag advice is a list of tips. jetlag-forge computes.

It models your body clock as a **continuous phase** and asks one question of
every leg: *how many hours does the destination clock lead your internal
clock right now?* Everything else falls out of that number.

**The phase error.** Your body clock keeps running on its old schedule after
you fly. The shift is computed from real UTC offsets (DST-aware) and then
folded into (-12, +12]. That fold matters more than it sounds:

> Chicago to Tokyo is **+15 hours** of clock, which is really a **9 hour
> delay**. A day only holds 24 hours. Because of that fold, flying *east*
> across the Pacific behaves like a *westward* trip for your body clock, and
> the advice flips with it. People get this backwards constantly.

**Direction decides everything.** An eastward (advance) trip and a westward
(delay) trip need opposite corrections, so they get opposite advice:

| | Eastward (advance) | Westward (delay) |
|---|---|---|
| What you feel | awake at midnight, exhausted at 9am | sleepy at 4pm, awake at midnight |
| Light | **morning** bright light | **evening** bright light |
| Darkness | dim the 3h before bed | dim the first hour after waking |
| Bedtime | earlier, in local terms | later, in local terms |
| Melatonin | timed low dose before local bed | generally not helpful |
| Adaptation | slower (~1h/night) | faster (~1.2h/night) |

**Adaptation is modelled, not asserted.** Your internal clock drifts toward
local solar noon at roughly an hour per night, and the drift carries across
time-zone boundaries, so a multi-stop trip accumulates error the way it
actually does. Chronotype modulates the rate: morning people adapt faster to
an advance, night people faster to a delay.

**Sleep is simulated.** A two-process model (Borbely): homeostatic sleep
pressure builds while you are awake and decays while you sleep, and
circadian alerting rides on top of it, driven by your body clock. On top of
that sit three real physiological constraints:

- **Melatonin gates sleep onset.** You cannot drop off before it fires, which
  is why a big eastward shift means lying awake for hours rather than
  sleeping badly.
- **The sleep maintenance zone** produces the classic 03:00 awakening when it
  lands inside your sleep window.
- **Your internal wake signal** can surface you before the alarm, which is
  the westward trap of waking at 4am and not being tired again.

**Your meetings are scored.** Every critical event is assessed against your
body clock, so a 10:00 local meeting that lands at 03:00 on your internal
clock gets flagged as dangerous rather than optimistically called fine.

---

## Quick start

```bash
cd jetlag-forge
python3 -m pip install -r requirements.txt   # just Flask
python3 app.py
```

Open <http://127.0.0.1:5000>. Six sample briefs are built in, so you can see
the whole thing working before you type anything.

Run the tests:

```bash
python3 -m unittest discover -s tests -v
```

---

## The brief format

Plain text, one directive per line. Keys are case-insensitive and order-free.

```
Trip: Tokyo client sprint
Home: Chicago
Home wake: 06:30
Home sleep: 22:30
Chronotype: late
Melatonin: 0.5mg
Purpose: client work

Flight: ORD -> HND | depart 2026-11-16 11:00 | arrive 2026-11-17 14:30
Stay: Tokyo | from 2026-11-17 | to 2026-11-22
Event: Client review | 2026-11-18 10:00 | Tokyo
Event: Contract signing | 2026-11-20 14:00 | Tokyo
```

**Flight times are local to each airport.** So the departure is Chicago time
and the arrival is Tokyo time, and the tool works out the rest.

**Places** accept an airport code (`NRT`), a city name (`Tokyo`), an IANA
zone (`Asia/Tokyo`), or an explicit override (`XXX(Asia/Tokyo)`).

**Chronotype** is `early`, `intermediate` or `late` (aliases: lark, morning,
owl, night owl).

**Every field improves the plan.** Home sleep times set your whole schedule,
chronotype changes the adaptation rate, and events are what let the tool
protect the hours that actually matter.

---

## What you get

- **Scorecard** across five axes: shift severity, recovery runway, sleep
  integrity, performance safety, plan quality. Four profiles re-weight them
  (balanced, conference, recovery, endurance).
- **Structural caps.** A document cannot score well by skipping the hard
  part. No runway, no critical events, no home sleep times, a red-eye
  arrival or an 11-hour shift each cap a specific axis and drag the overall
  score down with them.
- **Per-day plan** for every night at every stop: what time your body wants
  to sleep, what time you should actually get into bed, when melatonin fires,
  when the circadian trough lands, the bright-light and dim-light windows,
  the caffeine cutoff, meal anchors, projected sleep and the hour-by-hour
  alertness curve.
- **Ranked findings**, each with the evidence that triggered it, why it
  matters and a concrete fix.
- **A prioritised action list** you can actually follow.
- **Markdown and JSON export**, plus a local SQLite history with 1-5 star
  ratings and notes so you can compare what the plan said against what
  actually happened.

---

## How the numbers are put together

| Layer | Model |
|---|---|
| Phase error | Real UTC offsets, DST-aware, folded into (-12, +12] |
| Adaptation | ~1h/night toward local solar noon, carried across legs, chronotype-modulated |
| Alertness | Two-process model: homeostatic pressure (tau 18h awake, 4.5h asleep) plus circadian alerting on a 24.2h period |
| Sleep onset | Psychological latency, gated by melatonin onset |
| Fragmentation | Sleep maintenance zone arousal and the internal wake signal |

The parameters are calibrated to published phase-shift and adaptation rates.
It is a planning aid, not a clinical instrument.

---

## Project layout

```
app.py                 Flask API and static server
engine/
  tzmap.py             Airport codes and city names to IANA zones
  parse.py             Brief parsing into a structured trip
  circadian.py         The phase, adaptation and alertness model
  analyzer.py          Timeline walk, scorecard, rules, fix plan
  export.py            Markdown and JSON export
  samples.py           Six built-in sample briefs
static/                Dark vanilla-JS UI (no build step, no framework)
tests/                 63 tests, including a live frontend render check
```

## API

```
GET  /api/health
GET  /api/profiles
GET  /api/samples
GET  /api/samples/<id>
POST /api/analyze          {brief, profile} -> full report
POST /api/export           {brief, profile, fmt: md|json}
GET  /api/journeys
POST /api/journeys         {brief, profile}
GET  /api/journeys/<id>
PATCH /api/journeys/<id>  {rating, notes}
```

---

## Not medical advice

This is a planning tool. It is not a diagnostic, and it does not replace a
clinician. Talk to a doctor about melatonin or any sleep disorder, and seek
medical advice if jet lag is significantly disrupting your life.

## Licence

MIT.
