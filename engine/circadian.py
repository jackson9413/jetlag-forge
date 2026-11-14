"""Circadian phase and alertness modelling for jetlag-forge.

Three layers.

1. PHASE ERROR (the core number). Your body clock keeps running on its old
   schedule after you fly. The phase error is how many hours the destination
   clock leads your body clock:

       h = (destination UTC offset - home UTC offset) folded into (-12, +12]

   Folding matters. Chicago to Tokyo is +15 hours of clock, which is really
   a 9 hour DELAY, because a day only holds 24 hours. That fold is why
   Tokyo from the US West Coast behaves like a westward trip, and why the
   light advice flips.

   h > 0  destination clock leads. Your body wants to sleep later than local
          life does, you wake at 03:00, and you need a phase ADVANCE:
          morning light, earlier bedtime, evening dimness.
   h < 0  destination clock lags. You collapse at 15:00, your body runs ahead
          of local life, and you need a phase DELAY: evening light, later
          bedtime, morning dimness.

2. ADAPTATION. Your internal clock re-entrains at roughly one hour per night.
   Advances are slower than delays, and chronotype modulates both: early
   birds adapt faster to advances, night owls faster to delays. The residual
   error falls linearly to zero over the nights needed.

3. ALERTNESS (two-process model, Borbely). Sleep propensity comes from
   Process S (homeostatic pressure, builds while awake, decays during sleep)
   and Process C (circadian, driven by your body clock). Alertness is a blend
   of the two. Melatonin onset gates sleep onset, and a melatonin surge
   inside your sleep window produces the classic 03:00 awakening.

All local times are continuous hours that may run past 24, so 25:30 means
01:30 the next morning. Standard library only: no network, no API keys.
"""

import math
from zoneinfo import ZoneInfo

# --- tunables -------------------------------------------------------------

HOMEPRESSURE_RISE_TAU_H = 18.0      # process S time constant while awake
HOMEPRESSURE_FALL_TAU_H = 4.5       # process S time constant while asleep
CIRC_PERIOD_H = 24.0                # free-running circadian period
CIRC_NADIR_BODY_HOUR = 5.0          # body clock hour of the alertness trough
CIRC_WEIGHT = 0.45                  # weight of the circadian term
BASELINE_SLEEP_NEED_H = 8.0
SLEEP_LATENCY_PER_HOUR_MISMATCH = 0.45
SLEEP_LATENCY_MAX_H = 3.5
SLEEP_LATENCY_FLOOR_H = 0.25
CIRCADIAN_CAFFEINE_HALFLIFE_H = 5.0
DLMO_OFFSET_BEFORE_BED_H = 2.0      # melatonin onset before your habitual bedtime
DLMO_GATE_LEAD_H = 1.0              # you get sleepy this long before melatonin peaks

SCHEDULE_STEP_H = 1.0               # one hour of schedule shift per night
EARLIEST_BED_H = 20.0               # 20:00 local floor for an adopted bedtime
LATEST_BED_H = 26.0                 # 02:00 local ceiling
EARLIEST_WAKE_H = 5.0
LATEST_WAKE_H = 10.0

# Adaptation efficiency by direction and chronotype.
ADAPT_EFFICIENCY = {
    'advance': {'early': 1.15, 'intermediate': 1.00, 'late': 0.85},
    'delay': {'early': 0.90, 'intermediate': 1.20, 'late': 1.35},
}


def utc_offset_hours(tz_name, instant_utc):
    """UTC offset (hours) of a zone at a given UTC instant."""
    return instant_utc.astimezone(ZoneInfo(tz_name)).utcoffset().total_seconds() / 3600.0


def normalise_shift(raw_hours):
    """Fold a raw offset change into (-12, 12] and flag date-line crossings."""
    if raw_hours > 12:
        return raw_hours - 24.0, True
    if raw_hours < -12:
        return raw_hours + 24.0, True
    return raw_hours, False


def fold(value):
    """Fold an hour difference into (-12, 12]."""
    v = value % 24.0
    if v > 12.0:
        v -= 24.0
    if v <= -12.0:
        v += 24.0
    return v


def format_hours(value, signed=False):
    """Format a fractional hour offset as a compact clock offset."""
    sign = '+' if value >= 0 else '-'
    if signed:
        return '%s%.1fh' % (sign, abs(value))
    return '%.1fh' % abs(value)


def format_clock(hours):
    """Format fractional hours-from-midnight as HH:MM, allowing hours past 24."""
    total = int(round(hours * 60.0))
    day_shift = total // (24 * 60)
    total = total % (24 * 60)
    return '%02d:%02d' % (total // 60, total % 60), day_shift


def clock_text(hours):
    """Format as HH:MM with a next-day marker when it rolls past midnight."""
    text, day_shift = format_clock(hours)
    if day_shift >= 1:
        return '%s (+1)' % text
    return text


def body_reading(local_hour, effective_shift):
    """What your body clock reads when the local clock shows local_hour."""
    return (local_hour - effective_shift) % 24.0


def adaptation_rate(effective_shift, chronotype):
    """Hours of phase correction absorbed per night at the destination."""
    direction = 'advance' if effective_shift >= 0 else 'delay'
    efficiency = ADAPT_EFFICIENCY[direction].get(chronotype, 1.0)
    return SCHEDULE_STEP_H * efficiency


def nights_to_sync(effective_shift, chronotype):
    """Nights needed to fully re-entrain to the destination."""
    if abs(effective_shift) < 0.05:
        return 0
    rate = adaptation_rate(effective_shift, chronotype)
    return max(1, int(math.ceil(abs(effective_shift) / rate)))


def residual_after_nights(effective_shift, nights, chronotype):
    """Phase error remaining after N nights at the destination.

    The error falls linearly to zero over the nights needed, which keeps the
    schedule and the residual in agreement instead of drifting apart.
    """
    if abs(effective_shift) < 0.05:
        return 0.0
    total = nights_to_sync(effective_shift, chronotype)
    fraction = min(1.0, float(nights) / float(total))
    return effective_shift * (1.0 - fraction)


def homeostatic_sleep_pressure(sleep_hours_awake):
    """Process S after being awake for N hours (0 = fully rested)."""
    return 1.0 - math.exp(-sleep_hours_awake / HOMEPRESSURE_RISE_TAU_H)


def pressure_after_sleep(pressure_at_sleep, slept_hours):
    """Process S after sleeping."""
    return max(0.0, pressure_at_sleep * math.exp(-slept_hours / HOMEPRESSURE_FALL_TAU_H))


def alertness(pressure, body_hour):
    """Blend the two processes into a 0-100 alertness reading."""
    homeostatic = max(0.0, 1.0 - pressure)
    circadian = circ_term(body_hour)
    raw = (1.0 - CIRC_WEIGHT) * homeostatic + CIRC_WEIGHT * circadian
    return max(0.0, min(1.0, raw)) * 100.0


def circ_term(body_hour):
    """Process C as a 0-1 circadian alertness wave, trough at body 05:00."""
    phase = ((body_hour - CIRC_NADIR_BODY_HOUR) % CIRC_PERIOD_H) / CIRC_PERIOD_H
    wave = -math.cos(2 * math.pi * phase)
    return (wave + 1.0) / 2.0


def sleep_duration(home_sleep, home_wake):
    """Your habitual sleep length in hours."""
    d = home_wake - home_sleep
    if d <= 0:
        d += 24.0
    return d


def wanted_bedtime_local(home_sleep, residual):
    """Local clock time at which your body wants to fall asleep."""
    return home_sleep + residual


def recommended_schedule(effective_shift, day_index, residual, home_sleep, home_wake,
                         chronotype='intermediate'):
    """The sleep window to actually adopt on a given night at the destination.

    The adopted schedule tracks your local social bedtime and is pulled by
    up to three hours in the direction of the shift, in proportion to how
    much of the shift you have already adapted. Pulling earlier is what a
    phase advance needs; pushing later is what a phase delay needs.

    The physiology is handled separately: melatonin onset gates when you
    can actually drop off, so an adopted 22:30 on a big eastward trip
    still means you lie awake until your body lets you sleep.
    """
    duration = sleep_duration(home_sleep, home_wake)
    adapted = abs(effective_shift) - abs(residual)
    pull = min(3.0, max(0.0, adapted))
    if effective_shift >= 0:
        bed = home_sleep - pull
    else:
        bed = home_sleep + pull
    bed = max(EARLIEST_BED_H, min(LATEST_BED_H, bed))
    wake = bed + duration
    if wake <= bed:
        wake = bed + duration
    return bed, wake


def sleep_onset_latency(residual, effective_shift):
    """How long you lie awake, from the gap between wanted and adopted bedtime."""
    mismatch = abs(residual)
    if effective_shift >= 0:
        latency = SLEEP_LATENCY_FLOOR_H + SLEEP_LATENCY_PER_HOUR_MISMATCH * mismatch
    else:
        latency = SLEEP_LATENCY_FLOOR_H + SLEEP_LATENCY_PER_HOUR_MISMATCH * 0.35 * mismatch
    return max(SLEEP_LATENCY_FLOOR_H, min(SLEEP_LATENCY_MAX_H, latency))


def light_prescription(effective_shift, bed_h, wake_h, residual):
    """Light and darkness windows in local clock time."""
    if effective_shift >= 0:
        kind = 'advance'
        bright_start = (wake_h + 0.2) % 24.0
        bright_end = (wake_h + 1.8) % 24.0
        dim_start = (bed_h - 3.0) % 24.0
        dim_end = bed_h % 24.0
        advice = (
            'Bright outdoor light within an hour of waking advances your clock. '
            'Keep the three hours before bed dim so melatonin still fires on time.'
        )
    else:
        kind = 'delay'
        bright_start = (bed_h - 3.0) % 24.0
        bright_end = (bed_h - 1.0) % 24.0
        dim_start = (wake_h - 1.0) % 24.0
        dim_end = (wake_h + 0.8) % 24.0
        advice = (
            'Bright light in the late evening pushes your clock later. '
            'Keep the first hour after waking dim so you stay sleepy until bed.'
        )
    return {
        'kind': kind,
        'bright_start': bright_start,
        'bright_end': bright_end,
        'dim_start': dim_start,
        'dim_end': dim_end,
        'advice': advice,
        'residual_error_h': residual,
    }


def caffeine_plan(bed_h, chronotype):
    """Caffeine cutoff and a same-day strategy for the destination."""
    cutoff = (bed_h - 6.0) % 24.0
    if chronotype == 'late':
        note = (
            'Keep caffeine before 14:00 local. Its half-life is about five hours, '
            'so a late cup is still working when you want to sleep.'
        )
    elif chronotype == 'early':
        note = (
            'Cap caffeine at two cups and stop by 12:00 local. You wake early on a '
            'new schedule, so the coffee needs to clear before that.'
        )
    else:
        note = 'Stop caffeine six hours before bed. A cup at 16:00 is still half-active at 21:00.'
    return {'cutoff': cutoff, 'note': note}


def meal_plan(effective_shift, bed_h):
    """Meal timing anchors that keep the body clock tied to local time."""
    if effective_shift >= 0:
        breakfast = 8.0
        dinner = max(18.0, bed_h - 4.0)
        note = (
            'Eat breakfast near your usual time even if you have no appetite. '
            'It is the strongest non-light anchor you have.'
        )
    else:
        breakfast = 9.5
        dinner = min(21.0, bed_h - 2.5)
        note = (
            'Do not force an early breakfast. Skipping it until 09:30-10:00 keeps '
            'your clock from reading the local morning as lunchtime.'
        )
    return {'breakfast': breakfast, 'dinner': dinner, 'note': note}


def days_to_sync(effective_shift, chronotype):
    """Nights needed to fully re-entrain to the destination."""
    if abs(effective_shift) < 0.05:
        return 0
    rate = adaptation_rate(effective_shift, chronotype)
    return max(1, int(math.ceil(abs(effective_shift) / rate)))


def simulate_day(effective_shift, day_index, home_sleep, home_wake,
                 sleep_pressure_start, chronotype='intermediate', melatonin_mg=0.0,
                 arrival_hour=None, arrival_pressure=None):
    """Simulate one destination night and return the alertness curve and advice.

    effective_shift: hours the destination clock leads your body clock at
                     arrival (positive = phase advance needed).
    day_index:      1 for the first day at the destination.
    sleep_pressure_start: process S at the moment you woke that morning.
    melatonin_mg:   dose the traveller is taking, if any.

    The night is built from four physiological anchors, all in unwrapped
    local time carried past midnight:

      body bed    the local time at which your internal clock says to sleep.
      DLMO        melatonin onset, about two hours before that. It gates
                  sleep onset, which is why a big eastward shift means
                  lying awake for hours.
      SMZ         the sleep maintenance zone, about two hours before DLMO.
                  This is the brief awakening that ruins the first nights
                  of an eastward trip.
      body wake   the local time at which your internal clock expects you
                  to be up. If it lands in the early local morning you
                  wake before you are ready, which is the westward trap.
    """
    residual = residual_after_nights(effective_shift, day_index - 1, chronotype)

    duration = sleep_duration(home_sleep, home_wake)

    # The adopted schedule: one hour per night in the direction of travel,
    # capped so it stays humane.
    remaining = int(math.ceil(abs(residual)))
    steps = min(max(day_index - 1, 0), 3, remaining)
    if effective_shift >= 0:
        bed = home_sleep - steps
    else:
        bed = home_sleep + min(steps, 2)
    bed = max(EARLIEST_BED_H, min(LATEST_BED_H, bed))
    wake = bed + duration

    # What the internal clock wants, expressed in local time.
    body_bed = home_sleep + residual
    body_wake = home_wake + residual

    # Melatonin onset, plus the phase effect of the dose itself.
    dlmo = body_bed - DLMO_OFFSET_BEFORE_BED_H
    if melatonin_mg > 0:
        effect = min(1.5, 0.6 + 0.45 * melatonin_mg)
        if effective_shift >= 0:
            dlmo -= effect
        else:
            dlmo += effect

    # Sleep onset. If your body wants to sleep EARLIER than the adopted
    # bedtime you drop off quickly. If it wants to sleep LATER you are
    # awake for hours, and that is the eastward experience.
    if body_bed <= bed:
        latency = SLEEP_LATENCY_FLOOR_H
    else:
        gap = body_bed - bed
        latency = SLEEP_LATENCY_FLOOR_H + SLEEP_LATENCY_PER_HOUR_MISMATCH * gap
    latency = max(SLEEP_LATENCY_FLOOR_H, min(SLEEP_LATENCY_MAX_H, latency))
    onset = max(bed + latency, dlmo - DLMO_GATE_LEAD_H)

    # The sleep maintenance zone: a brief arousal inside the sleep window.
    smz = dlmo - 2.0
    mid_night_wake = None
    if onset + 0.3 < smz < wake - 0.3:
        mid_night_wake = smz

    # Homeostatic pressure: it rises while you are awake and decays while
    # you sleep, and it is what actually stops you sleeping.
    #
    # On the arrival day the reference point is the moment you stepped off
    # the plane, not the adopted wake time. You are already running on
    # whatever sleep you managed in the air, and the hours before arrival
    # were spent in a seat, not in a bed.
    if arrival_hour is not None:
        wake_mod = arrival_hour % 24.0
        start_pressure = arrival_pressure
    else:
        wake_mod = wake % 24.0
        start_pressure = sleep_pressure_start
    hours_awake = (bed - wake_mod) % 24.0
    if hours_awake < 0.5:
        hours_awake = 24.0
    pressure_at_bed = 1.0 - (1.0 - start_pressure) * math.exp(
        -hours_awake / HOMEPRESSURE_RISE_TAU_H)
    max_sleep = HOMEPRESSURE_FALL_TAU_H * math.log(max(pressure_at_bed, 0.011) / 0.10)
    max_sleep = min(max(max_sleep, 1.0), 11.0)

    # Your internal wake signal, softened because the body does not drag
    # you out of sleep on the dot.
    body_wake_signal = body_wake
    while body_wake_signal <= onset:
        body_wake_signal += 24.0
    body_wake_signal += 1.5

    # Your internal wake signal passing through the sleep window fragments
    # the night rather than ending it: you surface, lie there for a while,
    # and usually get back down because you are still deeply sleep-deprived.
    fragmentation = 0.0
    if onset + 0.5 < body_wake_signal < wake:
        fragmentation = 1.5

    awake_at = min(wake, onset + max_sleep)
    effective_sleep = max(1.5, awake_at - onset - fragmentation)
    if mid_night_wake is not None:
        effective_sleep -= 0.75

    pressure_at_wake = pressure_at_bed * math.exp(-effective_sleep / HOMEPRESSURE_FALL_TAU_H)

    curve = []
    for hour in range(24):
        awake_hours = (hour - wake_mod) % 24.0
        if arrival_hour is not None:
            # Before arrival you were in a seat, not lying down, so cap the
            # accumulated wake time rather than letting it run away.
            awake_hours = min(awake_hours, 12.0)
        p = homeostatic_sleep_pressure(awake_hours)
        b_hour = (hour - residual) % 24.0
        curve.append({'hour': hour, 'alertness': round(alertness(p, b_hour), 1)})

    focus = [c['hour'] for c in curve if c['alertness'] >= 70]
    worst = [c['hour'] for c in curve if c['alertness'] <= 35]

    debt = max(0.0, BASELINE_SLEEP_NEED_H - effective_sleep)

    key_hours = {}
    for h in (7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 20, 22):
        key_hours['%02d:00' % h] = curve[h]['alertness']

    noon_body = body_reading(12.0, residual)
    light = light_prescription(effective_shift, bed, wake, residual)
    caffeine = caffeine_plan(bed, chronotype)
    meals = meal_plan(effective_shift, bed)

    return {
        'day_index': day_index,
        'residual_error_h': round(residual, 2),
        'adapted_pct': round(
            100.0 * (1.0 - abs(residual) / max(abs(effective_shift), 1e-6)), 1
        ) if abs(effective_shift) > 0.05 else 100.0,
        'body_clock_at_noon': format_clock(noon_body)[0],
        'body_bed_local': format_clock(body_bed % 24.0)[0],
        'body_wake_local': format_clock(body_wake % 24.0)[0],
        'wanted_bed_local': format_clock(body_bed % 24.0)[0],
        'recommended_bed_local': format_clock(bed)[0],
        'recommended_bed_local_text': clock_text(bed),
        'recommended_wake_local': format_clock(wake)[0],
        'recommended_wake_local_text': clock_text(wake),
        'sleep_latency_h': round(onset - bed, 2),
        'melatonin_onset_local': format_clock(dlmo % 24.0)[0],
        'early_wake_local': (format_clock(mid_night_wake % 24.0)[0] if mid_night_wake else None),
        'sleep_window_h': round(wake - bed, 2),
        'actual_sleep_h': round(effective_sleep, 2),
        'sleep_debt_h': round(debt, 2),
        'alertness': curve,
        'focus_hours': focus,
        'worst_hours': worst,
        'key_alertness': key_hours,
        'light': light,
        'caffeine': caffeine,
        'meals': meals,
        'next_pressure': pressure_at_wake,
        'arrival_day': arrival_hour is not None,
    }


def flight_alertness(flight, chronotype='intermediate'):
    """Rough alertness profile for a day spent in the air."""
    dep_h = flight.dep_local_hour
    arr_h = flight.arr_local_hour
    overnight = dep_h >= 21.0 or dep_h < 5.0 or arr_h <= 6.0 or arr_h >= 22.0
    red_eye = arr_h <= 6.0 or arr_h >= 23.0
    duration = flight.duration_h
    if overnight:
        sleep_in_air = max(0.0, min(duration * 0.55, duration - 1.0))
        quality = 0.65 if duration < 10 else 0.5
        effective = sleep_in_air * quality
        mood = 'tired'
    else:
        sleep_in_air = 0.0
        effective = 0.0
        mood = 'flat'
    return {
        'overnight': overnight,
        'red_eye': red_eye,
        'sleep_in_air_h': round(sleep_in_air, 1),
        'effective_sleep_h': round(effective, 1),
        'mood': mood,
        'notes': [
            'Cabin light and low humidity cost you more than the clock does.',
            'Set your watch to destination time the moment you board.',
        ],
    }


def event_assessment(event, day_model):
    """Assess a critical event against the traveller's body clock."""
    local_hour = event.when_local.hour + event.when_local.minute / 60.0
    residual = day_model['residual_error_h']
    body_hour = (local_hour - residual) % 24.0
    body_str = format_clock(body_hour)[0]
    nearest = min(day_model['alertness'], key=lambda c: abs(c['hour'] - local_hour))
    value = nearest['alertness']
    if value >= 75:
        verdict = 'good'
        advice = 'Your clock is close enough that this should land well.'
    elif value >= 55:
        verdict = 'workable'
        advice = 'Usable, but do not schedule the hardest part of the day here.'
    elif value >= 35:
        verdict = 'risky'
        advice = 'You will be running on fumes. Push it later, or make it async.'
    else:
        verdict = 'danger'
        advice = (
            'Your body clock says it is the middle of the night. Do not put a '
            'decisive meeting here.'
        )
    return {
        'name': event.name,
        'when_local': event.when_local.strftime('%Y-%m-%d %H:%M'),
        'place': event.place or '',
        'local_hour': local_hour,
        'body_clock_time': body_str,
        'alertness': value,
        'verdict': verdict,
        'advice': advice,
    }
