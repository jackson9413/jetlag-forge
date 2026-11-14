"""Brief parsing for jetlag-forge.

Turns a plain-text travel brief into a structured Trip object.
Format (keys are case-insensitive, order-free):

    Trip: Tokyo Sprint
    Home: Chicago
    Home wake: 06:30
    Home sleep: 23:00
    Chronotype: late
    Melatonin: 0.5mg
    Purpose: client work

    Flight: ORD -> HND | depart 2026-11-03 11:00 | arrive 2026-11-04 14:30
    Stay: Tokyo | from 2026-11-04 | to 2026-11-09
    Event: Board review | 2026-11-05 10:00 | Tokyo

Flight times are LOCAL to their airport. "->" may also be written "to".
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

from . import tzmap


class BriefError(Exception):
    """Raised when a brief cannot be understood at all."""


@dataclass
class Flight:
    origin: str
    origin_tz: str
    dest: str
    dest_tz: str
    dep_local: datetime
    arr_local: datetime
    dep_utc: datetime
    arr_utc: datetime
    unresolved: list = field(default_factory=list)

    @property
    def duration_h(self):
        return (self.arr_utc - self.dep_utc).total_seconds() / 3600.0

    @property
    def dep_local_hour(self):
        return self.dep_local.hour + self.dep_local.minute / 60.0

    @property
    def arr_local_hour(self):
        return self.arr_local.hour + self.arr_local.minute / 60.0

    @property
    def offset_change_h(self):
        a = self.dep_utc.astimezone(ZoneInfo(self.origin_tz)).utcoffset()
        b = self.arr_utc.astimezone(ZoneInfo(self.dest_tz)).utcoffset()
        return (b - a).total_seconds() / 3600.0


@dataclass
class Stay:
    place: str
    tz: str
    start: date
    end: date
    derived: bool = False


@dataclass
class Event:
    name: str
    when_local: datetime
    tz: str
    place: str

    def local_hour(self):
        return self.when_local.hour + self.when_local.minute / 60.0


@dataclass
class Trip:
    title: str = "Untitled trip"
    home_place: str = ""
    home_tz: str = "UTC"
    home_wake: float = 7.0
    home_sleep: float = 23.0
    chronotype: str = "intermediate"
    melatonin_mg: float = 0.0
    purpose: str = ""
    flights: list = field(default_factory=list)
    stays: list = field(default_factory=list)
    events: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    explicit_sleep: bool = False
    explicit_wake: bool = False

    @property
    def sleep_duration_h(self):
        d = self.home_wake - self.home_sleep
        if d <= 0:
            d += 24.0
        return d


_DT_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{1,2}):(\d{2}))?")
_TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})$")


def _parse_datetime(text):
    m = _DT_RE.search(text or "")
    if not m:
        return None
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    hh = int(m.group(4)) if m.group(4) else 0
    mm = int(m.group(5)) if m.group(5) else 0
    try:
        return datetime(y, mo, d, hh, mm)
    except ValueError:
        return None


def _parse_date(text):
    dt = _parse_datetime(text)
    return dt.date() if dt else None


def _parse_clock(text):
    m = _TIME_RE.match((text or "").strip())
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2))
    if h > 24 or mi > 59:
        return None
    return h + mi / 60.0


def _split_parts(rest):
    rest = (rest or "").strip()
    if not rest:
        return []
    if "|" in rest:
        return [p.strip() for p in rest.split("|") if p.strip()]
    parts = [p.strip() for p in rest.split(",") if p.strip()]
    return parts


def _route_from(text):
    m = re.search(r"([A-Za-z0-9_./()\- ]+?)\s*(?:->|=>|→|\bto\b)\s*([A-Za-z0-9_./()\- ]+)", text)
    if not m:
        return None
    return m.group(1).strip(), m.group(2).strip()


def parse_brief(text):
    """Parse a plain-text brief into a Trip. Raises BriefError if no trip found."""
    if not text or not text.strip():
        raise BriefError("The brief is empty. Paste a travel brief with at least one flight.")

    trip = Trip()
    unresolved_zones = []
    raw_stays = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, rest = line.partition(":")
        key_l = key.strip().lower()
        rest = rest.strip()

        if key_l in ("trip", "title"):
            trip.title = rest or trip.title
        elif key_l in ("home", "home city", "from", "origin", "home timezone", "home tz"):
            if key_l in ("home timezone", "home tz"):
                tz, _, label = tzmap.resolve(rest)
                trip.home_tz = tz or trip.home_tz
                trip.home_place = label
            else:
                tz, kind, label = tzmap.resolve(rest)
                if tz:
                    trip.home_tz = tz
                    trip.home_place = label
                else:
                    unresolved_zones.append(rest)
                    trip.home_place = rest
        elif key_l in ("home wake", "wake", "wake time", "rise"):
            v = _parse_clock(rest)
            if v is not None:
                trip.home_wake = v
                trip.explicit_wake = True
        elif key_l in ("home sleep", "sleep", "bed", "bedtime", "sleep time"):
            v = _parse_clock(rest)
            if v is not None:
                trip.home_sleep = v
                trip.explicit_sleep = True
        elif key_l in ("chronotype", "type", "body type"):
            word = rest.strip().lower()
            if word in ("early", "lark", "morning", "early bird"):
                trip.chronotype = "early"
            elif word in ("late", "owl", "night owl", "evening"):
                trip.chronotype = "late"
            else:
                trip.chronotype = "intermediate"
        elif key_l in ("melatonin", "melatonin dose"):
            m = re.search(r"([0-9]*\.?[0-9]+)", rest)
            if m:
                trip.melatonin_mg = float(m.group(1))
            elif rest.strip().lower() in ("yes", "true"):
                trip.melatonin_mg = 0.5
        elif key_l in ("purpose", "reason", "notes"):
            trip.purpose = rest
        elif key_l in ("flight", "leg", "segment"):
            fl = _parse_flight(rest, unresolved_zones)
            if fl:
                trip.flights.append(fl)
        elif key_l in ("stay", "destination stop", "stop"):
            st = _parse_stay(rest)
            if st:
                raw_stays.append(st)
        elif key_l in ("event", "meeting", "critical event", "appointment"):
            ev = _parse_event(rest)
            if ev:
                trip.events.append(ev)

    if not trip.flights and not raw_stays:
        if unresolved_zones:
            raise BriefError(
                "Could not work out the timezone for: %s. Use an airport code, a city "
                "name or an IANA zone such as Asia/Tokyo, or write it as "
                "NRT(Asia/Tokyo)." % ', '.join(sorted(set(unresolved_zones)))
            )
        raise BriefError(
            "No flight or stay lines found. Add a line like "
            "'Flight: ORD -> HND | depart 2026-11-03 11:00 | arrive 2026-11-04 14:30'."
        )

    trip.flights.sort(key=lambda f: f.dep_utc)
    trip.stays = _merge_stays(trip, raw_stays)
    trip.warnings = ["Could not resolve timezone for: " + ", ".join(sorted(set(unresolved_zones)))] if unresolved_zones else []
    return trip


def _resolve_place(token, unresolved):
    tz, kind, label = tzmap.resolve(token)
    if tz is None:
        unresolved.append(token)
        return None, token
    return tz, label


def _parse_flight(rest, unresolved):
    parts = _split_parts(rest)
    if not parts:
        return None
    route = None
    dep = arr = None
    for part in parts:
        low = part.lower()
        if "->" in part or "=>" in part or "\u2192" in part or re.search(r"\bto\b", low):
            if route is None:
                route = _route_from(part)
            continue
        dt = _parse_datetime(part)
        if dt is None:
            continue
        if low.startswith("dep") or "depart" in low or low.startswith("out"):
            dep = dt
        elif low.startswith("arr") or "arrive" in low or low.startswith("land"):
            arr = dt
        else:
            if dep is None:
                dep = dt
            elif arr is None:
                arr = dt
    if route is None:
        return None
    origin_tok, dest_tok = route
    if dep is None:
        return None
    if arr is None:
        arr = dep
    o_tz, o_label = _resolve_place(origin_tok, unresolved)
    d_tz, d_label = _resolve_place(dest_tok, unresolved)
    if o_tz is None or d_tz is None:
        return None
    dep_local = dep.replace(tzinfo=ZoneInfo(o_tz))
    arr_local = arr.replace(tzinfo=ZoneInfo(d_tz))
    dep_utc = dep_local.astimezone(ZoneInfo("UTC"))
    arr_utc = arr_local.astimezone(ZoneInfo("UTC"))
    if arr_utc <= dep_utc:
        arr_utc += timedelta(days=1)
        arr_local = arr_utc.astimezone(ZoneInfo(d_tz)).replace(tzinfo=None)
    return Flight(o_label, o_tz, d_label, d_tz, dep_local, arr_local, dep_utc, arr_utc)


def _parse_stay(rest):
    parts = _split_parts(rest)
    if not parts:
        return None
    place = parts[0]
    start = end = None
    for part in parts[1:]:
        d = _parse_date(part)
        if d is None:
            continue
        if start is None:
            start = d
        elif end is None:
            end = d
    if start is None:
        return None
    return (place, start, end or start)


def _parse_event(rest):
    parts = _split_parts(rest)
    if not parts:
        return None
    name = parts[0]
    when = None
    place = None
    for part in parts[1:]:
        dt = _parse_datetime(part)
        if dt is not None and when is None:
            when = dt
        elif dt is None and place is None:
            place = part
    if when is None:
        return None
    tz, _kind, label = tzmap.resolve(place) if place else (None, "unknown", "")
    if place and tz is None:
        label = place
    return Event(name, when, tz, label or "")


def _merge_stays(trip, raw_stays):
    """Combine explicit stays with stays implied by the flight sequence."""
    stays = []
    for place, start, end in raw_stays:
        tz, kind, label = tzmap.resolve(place)
        if tz is None:
            continue
        stays.append(Stay(label, tz, start, end, derived=False))

    flights = trip.flights
    for i, fl in enumerate(flights):
        start_date = fl.arr_local.date()
        if i + 1 < len(flights):
            nxt = flights[i + 1]
            if nxt.origin_tz == fl.dest_tz:
                end_date = nxt.dep_local.date()
            else:
                end_date = start_date
        else:
            end_date = start_date
        if end_date < start_date:
            end_date = start_date
        explicit = None
        for st in stays:
            if st.tz == fl.dest_tz and st.start == start_date:
                explicit = st
                break
        if explicit is None:
            stays.append(Stay(fl.dest, fl.dest_tz, start_date, end_date, derived=True))
    stays.sort(key=lambda s: s.start)
    return stays
