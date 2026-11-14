"""Analysis engine for jetlag-forge.

Ties the brief, the circadian model and a rule engine together into one
report: per-day plans, a five-axis scorecard, ranked findings and a
prioritised fix plan.

The body clock is tracked as a continuous phase. body_solar_utc is the UTC
hour at which the traveller's internal clock peaks. It drifts toward the
local solar noon at the adaptation rate and never resets at a time-zone
boundary, so multi-stop trips carry their residual error forward correctly.
"""

import math
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from . import circadian as C
from .parse import Trip, parse_brief


PROFILES = {
    'balanced': {
        'label': 'Balanced',
        'weights': {
            'shift_severity': 0.28,
            'recovery_runway': 0.20,
            'sleep_integrity': 0.18,
            'performance_risk': 0.18,
            'plan_quality': 0.16,
        },
        'blurb': 'Equal weight on clock shift, runway, sleep and events.',
    },
    'conference': {
        'label': 'Conference / business travel',
        'weights': {
            'shift_severity': 0.18,
            'recovery_runway': 0.20,
            'sleep_integrity': 0.14,
            'performance_risk': 0.30,
            'plan_quality': 0.18,
        },
        'blurb': 'Your performance in scheduled meetings dominates the score.',
    },
    'recovery': {
        'label': 'Recovery focus',
        'weights': {
            'shift_severity': 0.20,
            'recovery_runway': 0.18,
            'sleep_integrity': 0.32,
            'performance_risk': 0.10,
            'plan_quality': 0.20,
        },
        'blurb': 'Sleep integrity and runway weigh most; events weigh least.',
    },
    'endurance': {
        'label': 'Endurance / long haul',
        'weights': {
            'shift_severity': 0.34,
            'recovery_runway': 0.24,
            'sleep_integrity': 0.20,
            'performance_risk': 0.12,
            'plan_quality': 0.10,
        },
        'blurb': 'Raw clock displacement dominates the score.',
    },
}

AXIS_LABELS = {
    'shift_severity': 'Shift severity',
    'recovery_runway': 'Recovery runway',
    'sleep_integrity': 'Sleep integrity',
    'performance_risk': 'Performance safety',
    'plan_quality': 'Plan quality',
}

AXIS_ORDER = ['shift_severity', 'recovery_runway', 'sleep_integrity',
              'performance_risk', 'plan_quality']

VERDICT_BANDS = [
    (85, 'smooth_sailing', 'Smooth sailing'),
    (70, 'mild', 'Mild'),
    (55, 'moderate', 'Moderate'),
    (38, 'rough', 'Rough'),
    (0, 'brutal', 'Brutal'),
]

SEVERITY_ORDER = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3, 'info': 4}

AXIS_CAP_LIMIT = {
    'shift_severity': 32,
    'recovery_runway': 40,
    'sleep_integrity': 55,
    'performance_risk': 42,
    'plan_quality': 55,
}


def _solar_utc(offset_hours):
    """UTC hour at which local solar noon happens."""
    return (12.0 - offset_hours) % 24.0


class Analyzer(object):
    def __init__(self, trip, profile='balanced'):
        self.trip = trip
        self.profile = profile if profile in PROFILES else 'balanced'
        self.findings = []
        self.event_assessments = []

    def _add(self, rule, severity, title, evidence, why, fix, axis=None):
        self.findings.append({
            'rule': rule,
            'severity': severity,
            'title': title,
            'evidence': evidence,
            'why': why,
            'fix': fix,
            'axis': axis,
        })

    # ----------------------------------------------------------------- model

    def build_timeline(self):
        """Walk legs and stays in true chronological order.

        The body clock is a continuous phase: body_solar_utc is the UTC hour
        at which the traveller's internal clock peaks. It drifts toward local
        solar noon at the adaptation rate and carries residual error across
        every time-zone boundary, which is what makes multi-stop trips
        behave the way they actually do.
        """
        trip = self.trip
        first_instant = trip.flights[0].dep_utc if trip.flights else datetime.now()
        home_offset = C.utc_offset_hours(trip.home_tz, first_instant)
        body_solar = _solar_utc(home_offset)

        legs = []
        stays = []
        arrivals = {}
        pressure = 0.95

        # Merge legs and stays into one chronological stream.
        stream = []
        for fl in trip.flights:
            stream.append(('leg', fl.dep_utc, fl))
        for st in trip.stays:
            anchor = None
            for fl in trip.flights:
                if fl.dest_tz == st.tz and fl.arr_local.date() == st.start:
                    anchor = fl.arr_utc
                    break
            if anchor is not None:
                stream.append(('stay', anchor, st))
        stream.sort(key=lambda item: (item[1], 0 if item[0] == 'leg' else 1))

        for kind, _when, obj in stream:
            if kind == 'leg':
                fl = obj
                dep_offset = C.utc_offset_hours(fl.origin_tz, fl.dep_utc)
                arr_offset = C.utc_offset_hours(fl.dest_tz, fl.arr_utc)
                dest_solar = _solar_utc(arr_offset)
                raw_shift = arr_offset - dep_offset
                effective = C.fold(body_solar - dest_solar)
                crossed = abs(raw_shift) > 12.0

                info = C.flight_alertness(fl, trip.chronotype)
                legs.append({
                    'origin': fl.origin,
                    'origin_tz': fl.origin_tz,
                    'dest': fl.dest,
                    'dest_tz': fl.dest_tz,
                    'dep_local': fl.dep_local.strftime('%Y-%m-%d %H:%M'),
                    'arr_local': fl.arr_local.strftime('%Y-%m-%d %H:%M'),
                    'dep_utc': fl.dep_utc.strftime('%Y-%m-%d %H:%M UTC'),
                    'arr_utc': fl.arr_utc.strftime('%Y-%m-%d %H:%M UTC'),
                    'duration_h': round(fl.duration_h, 2),
                    'raw_shift_h': round(raw_shift, 2),
                    'effective_shift_h': round(effective, 2),
                    'direction': ('advance' if effective > 0 else ('delay' if effective < 0 else 'none')),
                    'direction_label': (
                        'phase advance: the destination clock runs ahead of your body'
                        if effective > 0 else
                        ('phase delay: the destination clock runs behind your body'
                         if effective < 0 else 'no clock shift')
                    ),
                    'crosses_date_line': crossed,
                    'overnight': info['overnight'],
                    'red_eye_arrival': info['red_eye'],
                    'effective_sleep_in_air_h': info['effective_sleep_h'],
                    'in_flight_notes': info['notes'],
                })
                arrivals[(fl.dest_tz, fl.arr_local.date())] = {
                    'hour': fl.arr_local_hour,
                    'overnight': info['overnight'],
                    'sleep_in_air_h': info['effective_sleep_h'],
                }
                # The body clock does not move during the flight.
                continue

            st = obj
            offset = C.utc_offset_hours(st.tz, _utc_at(st.start, st.tz))
            dest_solar = _solar_utc(offset)
            effective = C.fold(body_solar - dest_solar)
            rate = C.adaptation_rate(effective, trip.chronotype)
            nights = max(0, (st.end - st.start).days)

            arrival = arrivals.get((st.tz, st.start))
            days = []
            for d in range(max(1, nights + 1)):
                arrival_hour = None
                arrival_pressure = None
                if d == 0 and arrival is not None:
                    if arrival['overnight']:
                        # You land on whatever sleep you managed in a seat.
                        deficit = max(0.0, C.BASELINE_SLEEP_NEED_H - arrival['sleep_in_air_h'])
                        arrival_hour = arrival['hour']
                        arrival_pressure = 1.0 - 0.84 * math.exp(-deficit / C.HOMEPRESSURE_FALL_TAU_H)
                    else:
                        # A daytime flight: you slept at home and woke to your
                        # normal alarm, so the day starts rested.
                        arrival_hour = trip.home_wake
                        arrival_pressure = 0.16
                sim = C.simulate_day(effective, d + 1, trip.home_sleep, trip.home_wake,
                                     pressure, trip.chronotype, trip.melatonin_mg,
                                     arrival_hour, arrival_pressure)
                sim['date'] = (st.start + timedelta(days=d)).strftime('%Y-%m-%d')
                sim['place'] = st.place
                sim['tz'] = st.tz
                days.append(sim)
                pressure = sim['next_pressure']
                # The body clock drifts toward local solar noon.
                drift = -rate if effective > 0 else rate
                body_solar = (body_solar + drift) % 24.0

            place_label = st.place
            if st.tz == trip.home_tz and st.place != trip.home_place:
                place_label = 'Home (%s)' % st.place
            stays.append({
                'place': place_label,
                'tz': st.tz,
                'start': st.start.strftime('%Y-%m-%d'),
                'end': st.end.strftime('%Y-%m-%d'),
                'nights': nights,
                'effective_shift_h': round(effective, 2),
                'direction': ('advance' if effective > 0 else ('delay' if effective < 0 else 'none')),
                'nights_to_sync': C.nights_to_sync(effective, trip.chronotype),
                'days': days,
            })

        self.legs = legs
        self.stays = stays
        self.body_solar = body_solar
        return legs, stays

    # --------------------------------------------------------------- scoring

    def score_axes(self):
        trip = self.trip
        legs = self.legs
        stays = self.stays
        caps = {}

        # --- shift severity ---------------------------------------------
        shifts = [abs(l['effective_shift_h']) for l in legs] or [0.0]
        max_shift = max(shifts)
        eastward = any(l['effective_shift_h'] > 0 for l in legs)
        westward = any(l['effective_shift_h'] < 0 for l in legs)
        shift_severity = 100.0 - max_shift * 7.5
        if eastward and westward:
            shift_severity -= 4.0
        elif eastward:
            shift_severity -= 3.0
        shift_severity = max(0.0, min(100.0, shift_severity))
        if max_shift >= 11:
            shift_severity = min(shift_severity, 32)
            caps['shift_severity'] = 'A clock shift of 11 hours or more cannot be absorbed quickly, whatever the plan.'
        elif max_shift >= 9:
            shift_severity = min(shift_severity, 45)
            caps['shift_severity'] = 'A 9-11 hour shift needs roughly nine nights to fully re-entrain.'
        elif max_shift >= 6:
            shift_severity = min(shift_severity, 62)
            caps['shift_severity'] = 'A 6-8 hour shift needs about a week of runway.'

        # --- recovery runway --------------------------------------------
        if stays:
            worst_ratio = 0.0
            for st in stays:
                need = max(1, st['nights_to_sync'])
                have = max(1, st['nights'])
                worst_ratio = max(worst_ratio, float(need) / float(have))
            runway = 100.0 - (worst_ratio - 1.0) * 42.0
        else:
            runway = 45.0
        runway = max(0.0, min(100.0, runway))
        if stays and max(st['nights'] for st in stays) < 2 and max_shift >= 5:
            runway = min(runway, 40)
            caps['recovery_runway'] = 'No stop is long enough to re-enter the local clock.'
        if max_shift >= 8 and stays and max(st['nights'] for st in stays) < max_shift:
            runway = min(runway, 48)
            caps['recovery_runway'] = 'You leave before your body clock has finished shifting.'

        # --- sleep integrity --------------------------------------------
        debt = sum(d['sleep_debt_h'] for st in stays for d in st['days'])
        red_eyes = sum(1 for l in legs if l['red_eye_arrival'])
        overnights = sum(1 for l in legs if l['overnight'])
        long_flights = sum(1 for l in legs if l['duration_h'] >= 9)
        sleep_integrity = 100.0 - debt * 5.5 - red_eyes * 14 - overnights * 6 - long_flights * 5
        sleep_integrity = max(0.0, min(100.0, sleep_integrity))
        if red_eyes:
            sleep_integrity = min(sleep_integrity, 66)
            caps['sleep_integrity'] = 'A red-eye arrival costs you a full night of the recovery budget.'
        if debt > 6:
            sleep_integrity = min(sleep_integrity, 55)
            caps['sleep_integrity'] = 'Projected sleep debt exceeds six hours across the trip.'

        # --- performance safety -----------------------------------------
        if self.event_assessments:
            avg = sum(a['alertness'] for a in self.event_assessments) / len(self.event_assessments)
            worst = min(self.event_assessments, key=lambda a: a['alertness'])
            performance = avg
            if worst['verdict'] == 'danger':
                performance = min(performance, 42)
                caps['performance_safety'] = 'A critical event falls inside your body clock night.'
            elif worst['verdict'] == 'risky':
                performance = min(performance, 62)
                caps['performance_safety'] = 'A critical event lands in your body clock low-alertness trough.'
        else:
            performance = 58.0
            caps['performance_safety'] = 'No critical events were given, so performance risk is judged on the shift alone.'
        performance = max(0.0, min(100.0, performance))

        # --- plan quality -----------------------------------------------
        quality = 100.0
        if not trip.flights:
            quality -= 40
        if not getattr(trip, 'explicit_sleep', False):
            quality -= 14
            caps['plan_quality'] = 'Your home sleep times were not supplied, so the plan assumes 23:00-07:00.'
        if trip.chronotype == 'intermediate':
            quality -= 8
        if trip.melatonin_mg <= 0:
            quality -= 10
        if not trip.events:
            quality -= 6
        if len(stays) > 1:
            quality += 3
        if trip.purpose:
            quality += 3
        plan_quality = max(0.0, min(100.0, quality))
        if plan_quality < 55:
            caps.setdefault('plan_quality', 'Key planning inputs are missing from the brief.')

        axes = {
            'shift_severity': round(shift_severity, 1),
            'recovery_runway': round(runway, 1),
            'sleep_integrity': round(sleep_integrity, 1),
            'performance_risk': round(performance, 1),
            'plan_quality': round(plan_quality, 1),
        }
        weights = PROFILES[self.profile]['weights']
        overall = sum(axes[k] * weights[k] for k in axes)
        for axis, limit in AXIS_CAP_LIMIT.items():
            if axis in caps and axes[axis] >= limit:
                overall = min(overall, limit + 12)
        overall = round(overall, 1)

        band_key, band_label = 'brutal', 'Brutal'
        for threshold, key, label in VERDICT_BANDS:
            if overall >= threshold:
                band_key, band_label = key, label
                break

        return {
            'axes': axes,
            'axis_order': AXIS_ORDER,
            'weights': weights,
            'overall': overall,
            'band': band_key,
            'band_label': band_label,
            'caps': caps,
            'max_shift_h': round(max_shift, 2),
            'total_sleep_debt_h': round(debt, 2),
            'red_eyes': red_eyes,
            'overnight_flights': overnights,
        }

    def _day_for_event(self, ev):
        for st in self.stays:
            for d in st['days']:
                if d['date'] == ev.when_local.strftime('%Y-%m-%d'):
                    return d
        return None

    # ----------------------------------------------------------------- rules

    def run_rules(self):
        trip = self.trip
        legs = self.legs
        stays = self.stays
        add = self._add

        if not trip.events:
            add('no_critical_events', 'medium',
                'No critical events in the brief',
                'The brief lists flights and stays but no meetings, interviews or deadlines.',
                'Performance risk can only be judged against the raw clock shift without knowing when you actually have to perform.',
                "Add a line like 'Event: Client review | 2026-11-05 10:00 | Tokyo' so the plan can protect the hours that matter.",
                axis='plan_quality')

        if trip.melatonin_mg <= 0:
            sev = 'high' if max(abs(l['effective_shift_h']) for l in legs) >= 6 else 'medium'
            add('no_melatonin', sev,
                'Melatonin is not in the plan',
                'The brief does not mention a melatonin dose.',
                'For a shift of six hours or more, timed low-dose melatonin is the strongest non-light lever for resetting the body clock, especially eastward.',
                'Consider 0.5-1mg taken three to four hours before your target bedtime in the destination, starting the night you land. Check with a clinician first.',
                axis='plan_quality')

        if trip.chronotype == 'intermediate':
            add('chronotype_default', 'low',
                'Chronotype not specified',
                'The brief does not state whether you are a morning or an evening person.',
                'Chronotype changes the adaptation rate by roughly fifteen percent and shifts your natural sleep window, which changes every bedtime recommendation downstream.',
                "Add 'Chronotype: early' or 'Chronotype: late' to sharpen the schedule.",
                axis='plan_quality')

        if not getattr(trip, 'explicit_sleep', False):
            add('no_home_sleep', 'medium',
                'Home sleep times not supplied',
                'The brief does not give your normal bedtime and wake time.',
                'Your home sleep window sets the entire schedule: the recommended bedtime, the light windows and the predicted alertness all derive from it.',
                "Add 'Home sleep: 22:30' and 'Home wake: 06:30'.",
                axis='plan_quality')

        for l in legs:
            shift = l['effective_shift_h']
            direction = 'ahead of' if shift > 0 else 'behind'
            if abs(shift) >= 9:
                add('extreme_shift', 'critical',
                    'Extreme clock shift on %s to %s' % (l['origin'], l['dest']),
                    'The destination clock runs %s hours %s your body clock on arrival.' % (
                        C.format_hours(shift), direction),
                    'At this magnitude your circadian system needs roughly %d nights to re-enter, and the first two or three nights will be genuinely broken.' % max(1, int(abs(shift))),
                    'Shift the arrival by a day if you can, take melatonin before the flight lands, and protect the first morning light.',
                    axis='shift_severity')
            elif abs(shift) >= 6:
                add('large_shift', 'high',
                    'Large clock shift on %s to %s' % (l['origin'], l['dest']),
                    'The destination clock runs %s %s your body clock.' % (
                        C.format_hours(shift), direction),
                    'Expect roughly %d nights before you are fully in sync, and put your highest-demand work after that.' % max(1, int(abs(shift))),
                    'Anchor the first meal and first outdoor light exposure to local time, then hold that rhythm.',
                    axis='shift_severity')

            if l['crosses_date_line']:
                add('date_line', 'medium',
                    'Date-line crossing on the %s to %s leg' % (l['origin'], l['dest']),
                    'The raw UTC offset change is %s hours, so the calendar date and the weekday both move.' % l['raw_shift_h'],
                    'Calendar-day confusion is the most common practical mistake on these legs, and it quietly corrupts every meeting you schedule.',
                    'Re-anchor on the destination date and weekday before you confirm anything, and keep a paper backup of the itinerary.',
                    axis='plan_quality')

            if l['red_eye_arrival']:
                add('red_eye_arrival', 'high',
                    'Red-eye arrival into %s' % l['dest'],
                    'You land at %s local after %s hours in the air.' % (
                        l['arr_local'][-5:], l['duration_h']),
                    'A night flight that lands in the small hours removes a full night of recovery at exactly the moment you need it most.',
                    'Use an eye mask, take melatonin before boarding, and treat the morning after as a light-only day with no decisions.',
                    axis='sleep_integrity')

            if l['overnight'] and l['duration_h'] >= 8:
                add('overnight_long_haul', 'medium',
                    'Overnight long-haul on the %s leg' % l['origin'],
                    'You are airborne for %s hours across your normal sleep window.' % l['duration_h'],
                    'Cabin service, low humidity and a reclined seat cut sleep efficiency well below what a bed would give you, so the deficit is larger than the hours suggest.',
                    'Book a window seat if you can, keep the eye mask on, set your watch to destination time at boarding and avoid screens.',
                    axis='sleep_integrity')

            if l['duration_h'] >= 11:
                add('very_long_flight', 'medium',
                    'Very long flight: %s hours' % l['duration_h'],
                    'The %s leg runs %s hours.' % (l['origin'], l['duration_h']),
                    'Flights beyond eleven hours exceed the longest natural sleep bout, so you will almost certainly get a broken night in the air.',
                    'Break the flight with a walk and water, and plan the next day as a short day rather than a full one.',
                    axis='sleep_integrity')

        for st in stays:
            shift = st['effective_shift_h']
            if st['nights_to_sync'] > st['nights'] + 1:
                add('runway_short', 'high',
                    'Not enough runway at %s' % st['place'],
                    '%s needs about %d nights to re-enter the local clock, and you are there for %d.' % (
                        st['place'], st['nights_to_sync'], st['nights']),
                    'You will be leaving while still out of sync, and the fatigue carries into the flight home and the days after it.',
                    'Push the heaviest work to the end of the stay, or add a day at the end of the trip to absorb the residual shift.',
                    axis='recovery_runway')

            first = st['days'][0]
            if first['sleep_latency_h'] >= 1.5:
                if shift >= 0:
                    why = ('You cannot fall asleep before your melatonin fires, which lands at '
                           '%s local. That is why eastward arrivals feel like insomnia.' % first['melatonin_onset_local'])
                    fix = ('Do not fight it in bed. Stay in dim light, keep the room dark, and go to '
                           'bed at %s anyway so your light exposure and melatonin timing stay anchored.' % first['recommended_bed_local'])
                else:
                    why = ('Your body wants to sleep at %s local, well before your adopted bedtime, so you '
                           'will get a heavy wave of sleepiness in the afternoon.' % first['wanted_bed_local'])
                    fix = ('Hold the adopted bedtime of %s. A short nap before 15:00 local is fine; a long '
                           'one is not.' % first['recommended_bed_local'])
                add('sleep_onset_delay', 'high',
                    'Your sleep will not settle easily at %s' % st['place'],
                    'Your body wants to sleep at %s local but the plan puts you in bed at %s, about %s hours of lag.' % (
                        first['wanted_bed_local'], first['recommended_bed_local'], first['sleep_latency_h']),
                    why,
                    fix,
                    axis='sleep_integrity')

            if first['early_wake_local']:
                add('midnight_wake', 'high',
                    'A 03:00-style wake-up is likely at %s' % st['place'],
                    'Your melatonin onset lands around %s local on the first night.' % first['melatonin_onset_local'],
                    'That early awakening is the signature of an eastward shift and it is what makes people conclude they cannot sleep in hotels.',
                    'Expect one or two such nights. Do not chase sleep after waking; get outside within thirty minutes and let bright morning light do the resetting.',
                    axis='sleep_integrity')

            for d in st['days']:
                if d['sleep_debt_h'] >= 3.0:
                    add('sleep_debt_day', 'medium',
                        'Sleep debt builds on day %d at %s' % (d['day_index'], st['place']),
                        'Projected sleep that night is %s hours against a %s hour need.' % (
                            d['actual_sleep_h'], C.BASELINE_SLEEP_NEED_H),
                        'Cumulative debt, not one bad night, is what produces the flat, foggy feeling people call jet lag.',
                        'Keep the caffeine cutoff, keep naps under twenty minutes and before 15:00, and treat the following morning as the recovery priority.',
                        axis='sleep_integrity')

        if len(legs) >= 3:
            signs = [l['direction'] for l in legs if l['direction'] != 'none']
            reversals = sum(1 for a, b in zip(signs, signs[1:]) if a != b)
            if reversals >= 1:
                add('direction_reversal', 'medium',
                    'Your itinerary reverses direction',
                    'You change between advancing and delaying legs %d time(s).' % reversals,
                    'Every reversal means a second re-entrainment, and the recovery runway you budgeted for the first shift does not carry over.',
                    'Where the order is flexible, travel in one direction and come back through your home zone rather than zig-zagging.',
                    axis='recovery_runway')

        if len(legs) == 1 and not stays:
            add('no_stays', 'medium',
                'No destination stay was found',
                'The brief has a flight but no stay information.',
                'A flight on its own is not a trip plan, and without the stay length the runway calculation cannot be trusted.',
                "Add a line like 'Stay: Tokyo | from 2026-11-04 | to 2026-11-09'.",
                axis='plan_quality')

        if len(stays) >= 2:
            worst = max(stays, key=lambda s: abs(s['effective_shift_h']))
            add('multi_stop_compare', 'info',
                'Hardest stop: %s' % worst['place'],
                'Shift sizes across stops: ' + ', '.join(
                    '%s %s' % (s['place'], C.format_hours(s['effective_shift_h'])) for s in stays),
                'Multi-stop trips punish you twice, once per stop, and the second shift lands on an already-degraded system.',
                'If you can choose, give the largest shift the longest stay and put your best hours at the stop with the smallest shift.',
                axis='recovery_runway')

        if any(l['effective_shift_h'] == 0 for l in legs):
            add('no_shift_leg', 'info',
                'At least one leg does not move your clock',
                'One of your flights crosses no or minimal time zones.',
                'Legs inside one or two zones are free, so use them to place your hardest work.',
                'Schedule demanding output around those legs.',
                axis='shift_severity')

        return self.findings

    # ----------------------------------------------------------------- plan

    def build_plan(self):
        """Prioritised, ordered actions derived from the findings and the model."""
        steps = []
        trip = self.trip

        for st in self.stays:
            shift = st['effective_shift_h']
            if shift == 0:
                continue
            first = st['days'][0]
            if shift > 0:
                steps.append({
                    'when': 'Day 1 morning at %s' % st['place'],
                    'action': 'Get 30-60 minutes of bright outdoor light within an hour of waking',
                    'why': 'Morning light advances the clock; %s runs %s ahead of your body.' % (
                        st['place'], C.format_hours(shift)),
                    'priority': 1,
                })
                steps.append({
                    'when': 'Day 1 at %s' % st['place'],
                    'action': 'Go to bed at %s local even though you will not sleep for hours' % first['recommended_bed_local'],
                    'why': 'Your melatonin fires around %s local. Fighting it in bed teaches your body that the bed is not for sleep.' % first['melatonin_onset_local'],
                    'priority': 1,
                })
                steps.append({
                    'when': 'Evenings at %s' % st['place'],
                    'action': 'Keep the room dim from %s local and screens off the last hour' % C.format_clock(first['light']['dim_start'])[0],
                    'why': 'Evening light pushes the clock the wrong way and is the fastest way to wreck progress.',
                    'priority': 2,
                })
            else:
                steps.append({
                    'when': 'Day 1 evening at %s' % st['place'],
                    'action': 'Get bright light in the evening, around %s local' % C.format_clock(first['light']['bright_start'])[0],
                    'why': 'Evening light delays the clock; %s runs %s behind your body.' % (
                        st['place'], C.format_hours(shift)),
                    'priority': 1,
                })
                steps.append({
                    'when': 'Mornings at %s' % st['place'],
                    'action': 'Stay dim or wear sunglasses for the first hour after waking',
                    'why': 'Morning light advances a clock that needs to delay, which is why westward travel feels fine right up until it does not.',
                    'priority': 2,
                })
                steps.append({
                    'when': 'Day 1 at %s' % st['place'],
                    'action': 'Hold bedtime at %s local and let your sleep run long' % first['recommended_bed_local'],
                    'why': 'Sleeping past your normal wake is the fastest way to delay the clock on a westward trip.',
                    'priority': 1,
                })

        for ev in self.event_assessments:
            if ev['verdict'] in ('danger', 'risky'):
                steps.append({
                    'when': '%s (%s)' % (ev['when_local'], ev['name']),
                    'action': 'Move this out of the %s local slot' % C.format_clock(ev['local_hour'])[0],
                    'why': 'Your body clock reads %s at that moment, so predicted alertness is %s out of 100.' % (
                        ev['body_clock_time'], ev['alertness']),
                    'priority': 1,
                })

        if trip.melatonin_mg <= 0:
            steps.append({
                'when': 'Before departure',
                'action': 'Take 0.5-1mg of melatonin three to four hours before your target bedtime for the first two or three nights',
                'why': 'Timed melatonin is the strongest non-light lever for an eastward reset. Confirm the dose with a clinician.',
                'priority': 1,
            })

        steps.append({
            'when': 'Every destination morning',
            'action': 'Eat breakfast near your normal time and get outside within an hour',
            'why': 'Meal timing and light together are what actually move the clock; caffeine only hides the symptom.',
            'priority': 2,
        })
        steps.append({
            'when': 'Before every flight',
            'action': 'Set your watch to destination time at boarding and live in it',
            'why': 'Your body clock adopts the schedule you expose it to, so the first thing it needs is a consistent one.',
            'priority': 2,
        })
        steps.append({
            'when': 'Nap, if you must',
            'action': 'Keep naps under 20 minutes and before 15:00 local',
            'why': 'A long or late nap gives away the sleep pressure you need to fall asleep at night.',
            'priority': 3,
        })

        steps.sort(key=lambda s: (s['priority'], s['when']))
        for i, s in enumerate(steps, 1):
            s['step'] = i
        return steps

    # --------------------------------------------------------------- report

    def run(self):
        self.build_timeline()

        assessments = []
        for ev in self.trip.events:
            day = self._day_for_event(ev)
            if day is None:
                assessments.append({
                    'name': ev.name,
                    'when_local': ev.when_local.strftime('%Y-%m-%d %H:%M'),
                    'place': ev.place or '',
                    'local_hour': ev.when_local.hour + ev.when_local.minute / 60.0,
                    'body_clock_time': '--:--',
                    'alertness': 0.0,
                    'verdict': 'unknown',
                    'advice': 'This date does not fall inside a destination stay, so no local plan applies to it.',
                })
                continue
            assessments.append(C.event_assessment(ev, day))
        self.event_assessments = assessments

        score = self.score_axes()
        self.run_rules()
        plan = self.build_plan()

        findings = sorted(self.findings, key=lambda f: (SEVERITY_ORDER.get(f['severity'], 9), f['rule']))
        counts = {}
        for f in findings:
            counts[f['severity']] = counts.get(f['severity'], 0) + 1

        return {
            'meta': {
                'title': self.trip.title,
                'home_place': self.trip.home_place or self.trip.home_tz,
                'home_tz': self.trip.home_tz,
                'home_wake': C.format_clock(self.trip.home_wake)[0],
                'home_sleep': C.format_clock(self.trip.home_sleep)[0],
                'chronotype': self.trip.chronotype,
                'melatonin_mg': self.trip.melatonin_mg,
                'purpose': self.trip.purpose,
                'profile': self.profile,
                'profile_label': PROFILES[self.profile]['label'],
                'profile_blurb': PROFILES[self.profile]['blurb'],
                'axis_labels': AXIS_LABELS,
                'warnings': self.trip.warnings,
            },
            'score': score,
            'legs': self.legs,
            'stays': self.stays,
            'events': assessments,
            'findings': findings,
            'finding_counts': counts,
            'plan': plan,
        }


def _utc_at(day, tz_name):
    """Midnight on a given local date, as a UTC instant."""
    return datetime(day.year, day.month, day.day, 12, 0, tzinfo=ZoneInfo(tz_name)).astimezone(ZoneInfo('UTC'))


def analyze(text, profile='balanced'):
    """Parse and analyse a brief. Returns the report dict."""
    trip = parse_brief(text)
    return Analyzer(trip, profile).run()
