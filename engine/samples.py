"""Built-in sample briefs for jetlag-forge."""

SAMPLES = [
    {
        'id': 'tokyo_sprint',
        'title': 'Tokyo client sprint',
        'summary': 'Chicago to Tokyo. Crosses the date line, so the circadian shift is a '
                   'nine hour delay and you will crash in the early afternoon.',
        'brief': """Trip: Tokyo client sprint
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
""",
    },
    {
        'id': 'london_advance',
        'title': 'London board meeting',
        'summary': 'New York to London. A classic five hour eastward advance with a '
                   'board meeting on day two, which is the worst possible slot.',
        'brief': """Trip: London board meeting
Home: New York
Home wake: 06:00
Home sleep: 23:00
Chronotype: early
Melatonin: 0.5mg
Purpose: quarterly board

Flight: JFK -> LHR | depart 2026-12-02 19:00 | arrive 2026-12-03 07:00
Stay: London | from 2026-12-03 | to 2026-12-07
Event: Board meeting | 2026-12-04 09:30 | London
""",
    },
    {
        'id': 'red_eye_return',
        'title': 'Red-eye return',
        'summary': 'San Francisco to New York on a red-eye. You land at 05:30 with no '
                   'night of recovery and a morning presentation.',
        'brief': """Trip: Red-eye return
Home: San Francisco
Home wake: 06:30
Home sleep: 23:00
Chronotype: intermediate
Melatonin: 1mg
Purpose: client presentation

Flight: SFO -> JFK | depart 2026-12-10 21:15 | arrive 2026-12-11 05:30
Stay: New York | from 2026-12-11 | to 2026-12-13
Event: Client presentation | 2026-12-11 14:00 | New York
""",
    },
    {
        'id': 'no_shift_control',
        'title': 'Same-zone trip (control)',
        'summary': 'A domestic hop inside one time zone. There is no clock shift, so the '
                   'plan is about sleep discipline rather than adaptation.',
        'brief': """Trip: Same-zone client visit
Home: Chicago
Home wake: 06:30
Home sleep: 22:30
Chronotype: intermediate
Melatonin: 0.5mg
Purpose: site visit

Flight: ORD -> MSP | depart 2026-12-01 09:00 | arrive 2026-12-01 11:15
Stay: Minneapolis | from 2026-12-01 | to 2026-12-03
Event: Site review | 2026-12-02 10:00 | Minneapolis
""",
    },
    {
        'id': 'multi_stop_europe',
        'title': 'Three-city European tour',
        'summary': 'New York to Paris to Berlin and back. Three time zones in a week, '
                   'with a direction reversal that costs you a second re-entrainment.',
        'brief': """Trip: Three-city European tour
Home: New York
Home wake: 07:00
Home sleep: 23:30
Chronotype: intermediate
Melatonin: 0.5mg
Purpose: sales tour

Flight: JFK -> CDG | depart 2027-01-11 18:30 | arrive 2027-01-12 08:15
Stay: Paris | from 2027-01-12 | to 2027-01-14
Flight: CDG -> BER | depart 2027-01-14 10:00 | arrive 2027-01-14 11:20
Stay: Berlin | from 2027-01-14 | to 2027-01-16
Flight: BER -> JFK | depart 2027-01-16 13:40 | arrive 2027-01-16 16:20
Event: Paris client dinner | 2027-01-13 19:30 | Paris
Event: Berlin partner review | 2027-01-15 09:00 | Berlin
""",
    },
    {
        'id': 'short_haul_turnaround',
        'title': 'Three-day turnaround',
        'summary': 'New York to London and straight back. There is not enough runway to '
                   'adapt at all, so the plan is about protecting performance, not recovery.',
        'brief': """Trip: Three-day turnaround
Home: New York
Home wake: 06:00
Home sleep: 23:00
Chronotype: intermediate
Purpose: site survey

Flight: JFK -> LHR | depart 2027-02-08 19:00 | arrive 2027-02-09 07:00
Stay: London | from 2027-02-09 | to 2027-02-10
Flight: LHR -> JFK | depart 2027-02-10 17:00 | arrive 2027-02-10 19:00
Event: Site survey | 2027-02-09 13:00 | London
""",
    },
]


def list_samples():
    return [
        {'id': s['id'], 'title': s['title'], 'summary': s['summary']}
        for s in SAMPLES
    ]


def get_sample(sample_id):
    for s in SAMPLES:
        if s['id'] == sample_id:
            return s
    return None
