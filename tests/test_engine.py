"""Smoke tests for jetlag-forge.

Run with:  python3 -m unittest discover -s tests -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import analyze, circadian as C
from engine.export import to_markdown, to_json
from engine.parse import BriefError, parse_brief
from engine.samples import SAMPLES, get_sample, list_samples


class TestParsing(unittest.TestCase):
    def test_basic_brief(self):
        trip = parse_brief(
            "Trip: Test\nHome: Chicago\nHome wake: 06:30\nHome sleep: 22:30\n"
            "Flight: ORD -> HND | depart 2026-11-03 11:00 | arrive 2026-11-04 14:30\n"
            "Stay: Tokyo | from 2026-11-04 | to 2026-11-09\n"
        )
        self.assertEqual(len(trip.flights), 1)
        self.assertEqual(len(trip.stays), 1)
        self.assertEqual(trip.home_tz, 'America/Chicago')
        self.assertEqual(trip.home_wake, 6.5)
        self.assertEqual(trip.home_sleep, 22.5)

    def test_empty_brief_raises(self):
        with self.assertRaises(BriefError):
            parse_brief("   ")

    def test_brief_without_trip_raises(self):
        with self.assertRaises(BriefError):
            parse_brief("Hello there\nNothing to see")

    def test_event_parsing(self):
        trip = parse_brief(
            "Home: Chicago\n"
            "Flight: ORD -> HND | depart 2026-11-03 11:00 | arrive 2026-11-04 14:30\n"
            "Event: Client review | 2026-11-05 10:00 | Tokyo\n"
        )
        self.assertEqual(len(trip.events), 1)
        self.assertEqual(trip.events[0].name, 'Client review')
        self.assertEqual(trip.events[0].place, 'Tokyo')

    def test_chronotype_aliases(self):
        for word, expected in [('early', 'early'), ('lark', 'early'),
                               ('late', 'late'), ('night owl', 'late'),
                               ('intermediate', 'intermediate')]:
            trip = parse_brief("Home: Chicago\nChronotype: %s\nFlight: ORD -> HND | depart 2026-11-03 11:00 | arrive 2026-11-04 14:30\n" % word)
            self.assertEqual(trip.chronotype, expected, word)

    def test_melatonin_dose_parsed(self):
        trip = parse_brief("Home: Chicago\nMelatonin: 0.5mg\nFlight: ORD -> HND | depart 2026-11-03 11:00 | arrive 2026-11-04 14:30\n")
        self.assertAlmostEqual(trip.melatonin_mg, 0.5)

    def test_unknown_place_reports_which_place_failed(self):
        with self.assertRaises(BriefError) as ctx:
            parse_brief("Home: Chicago\nFlight: XXX -> YYY | depart 2026-11-03 11:00 | arrive 2026-11-04 14:30\n")
        self.assertIn('XXX', str(ctx.exception))

    def test_explicit_zone_override_rescues_unknown_code(self):
        trip = parse_brief(
            "Home: Chicago\n"
            "Flight: XXX(Asia/Tokyo) -> YYY(America/New_York) | depart 2026-11-03 11:00 | arrive 2026-11-03 23:00\n")
        self.assertEqual(len(trip.flights), 1)


class TestTimezoneMap(unittest.TestCase):
    def test_airport_codes(self):
        from engine import tzmap
        self.assertEqual(tzmap.resolve('NRT')[0], 'Asia/Tokyo')
        self.assertEqual(tzmap.resolve('JFK')[0], 'America/New_York')
        self.assertEqual(tzmap.resolve('LHR')[0], 'Europe/London')

    def test_city_names(self):
        from engine import tzmap
        self.assertEqual(tzmap.resolve('Tokyo')[0], 'Asia/Tokyo')
        self.assertEqual(tzmap.resolve('Chicago')[0], 'America/Chicago')

    def test_iana_passthrough(self):
        from engine import tzmap
        self.assertEqual(tzmap.resolve('Asia/Kolkata')[0], 'Asia/Kolkata')

    def test_explicit_override(self):
        from engine import tzmap
        self.assertEqual(tzmap.resolve('XXX(Asia/Tokyo)')[0], 'Asia/Tokyo')

    def test_unknown(self):
        from engine import tzmap
        self.assertIsNone(tzmap.resolve('Zzzz')[0])


class TestFold(unittest.TestCase):
    def test_fold_within_range(self):
        self.assertAlmostEqual(C.fold(5.0), 5.0)
        self.assertAlmostEqual(C.fold(-6.0), -6.0)

    def test_date_line_folds(self):
        # Chicago to Tokyo is +15 raw, which is a 9 hour delay.
        self.assertAlmostEqual(C.fold(15.0), -9.0)
        self.assertAlmostEqual(C.fold(-15.0), 9.0)

    def test_normalise_flags_date_line(self):
        value, crossed = C.normalise_shift(15.0)
        self.assertTrue(crossed)
        self.assertAlmostEqual(value, -9.0)
        value, crossed = C.normalise_shift(3.0)
        self.assertFalse(crossed)


class TestCircadian(unittest.TestCase):
    def test_format_clock_wraps(self):
        self.assertEqual(C.format_clock(25.5)[0], '01:30')
        self.assertEqual(C.format_clock(24.0)[0], '00:00')
        self.assertEqual(C.format_clock(7.25)[0], '07:15')

    def test_body_reading(self):
        # At a 6 hour advance, local noon reads 06:00 on the body clock.
        self.assertAlmostEqual(C.body_reading(12.0, 6.0), 6.0)

    def test_adaptation_rate_direction(self):
        advance = C.adaptation_rate(6.0, 'intermediate')
        delay = C.adaptation_rate(-6.0, 'intermediate')
        self.assertGreater(delay, advance)

    def test_chronotype_modulates_rate(self):
        # Morning people adapt faster to an advance, night people to a delay.
        self.assertGreater(C.adaptation_rate(6.0, 'early'), C.adaptation_rate(6.0, 'late'))
        self.assertGreater(C.adaptation_rate(-6.0, 'late'), C.adaptation_rate(-6.0, 'early'))

    def test_residual_converges_to_zero(self):
        residual = C.residual_after_nights(9.0, 0, 'intermediate')
        self.assertAlmostEqual(residual, 9.0)
        residual = C.residual_after_nights(9.0, 30, 'intermediate')
        self.assertAlmostEqual(residual, 0.0)

    def test_alertness_low_in_the_small_hours(self):
        night = C.alertness(0.8, 3.0)
        day = C.alertness(0.3, 11.0)
        self.assertLess(night, day)

    def test_circadian_trough_at_0500(self):
        self.assertLess(C.circ_term(5.0), C.circ_term(15.0))

    def test_sleep_pressure_rises_then_decays(self):
        rested = C.pressure_after_sleep(0.95, 8.0)
        tired = C.pressure_after_sleep(0.95, 2.0)
        self.assertLess(rested, tired)

    def test_zero_shift_night_is_normal(self):
        day = C.simulate_day(0.0, 1, 22.5, 6.5, 0.95, 'intermediate')
        self.assertGreater(day['actual_sleep_h'], 6.5)
        self.assertLess(day['sleep_latency_h'], 1.0)

    def test_eastward_shift_costs_more_sleep(self):
        east = C.simulate_day(6.0, 1, 22.5, 6.5, 0.95, 'intermediate')
        west = C.simulate_day(-6.0, 1, 22.5, 6.5, 0.95, 'intermediate')
        self.assertLess(east['actual_sleep_h'], west['actual_sleep_h'])

    def test_adaptation_improves_over_nights(self):
        first = C.simulate_day(9.0, 1, 22.5, 6.5, 0.95, 'intermediate')
        later = C.simulate_day(9.0, 6, 22.5, 6.5, 0.95, 'intermediate')
        self.assertLess(abs(later['residual_error_h']), abs(first['residual_error_h']))
        self.assertGreater(later['actual_sleep_h'], first['actual_sleep_h'])

    def test_light_prescription_flips_by_direction(self):
        east = C.light_prescription(6.0, 22.5, 30.5, 6.0)
        west = C.light_prescription(-6.0, 22.5, 30.5, -6.0)
        self.assertEqual(east['kind'], 'advance')
        self.assertEqual(west['kind'], 'delay')

    def test_morning_light_is_early_for_advance(self):
        east = C.light_prescription(6.0, 22.5, 30.5, 6.0)
        self.assertLess(east['bright_start'], 12.0)

    def test_caffeine_cutoff_is_before_bed(self):
        plan = C.caffeine_plan(22.5, 'intermediate')
        self.assertLess(plan['cutoff'], 22.5)

    def test_days_to_sync_scales_with_shift(self):
        self.assertGreater(C.days_to_sync(9.0, 'intermediate'),
                           C.days_to_sync(3.0, 'intermediate'))

    def test_format_hours(self):
        self.assertEqual(C.format_hours(5.0), '5.0h')
        self.assertEqual(C.format_hours(-5.0, True), '-5.0h')


class TestAnalyzer(unittest.TestCase):
    def test_every_sample_analyses(self):
        for sample in SAMPLES:
            report = analyze(sample['brief'])
            self.assertIn('score', report, sample['id'])
            self.assertGreater(len(report['findings']), 0, sample['id'])
            self.assertGreater(len(report['plan']), 0, sample['id'])
            self.assertGreater(report['score']['overall'], 0, sample['id'])

    def test_score_in_range(self):
        for sample in SAMPLES:
            report = analyze(sample['brief'])
            self.assertGreaterEqual(report['score']['overall'], 0.0)
            self.assertLessEqual(report['score']['overall'], 100.0)
            for axis, value in report['score']['axes'].items():
                self.assertGreaterEqual(value, 0.0, axis)
                self.assertLessEqual(value, 100.0, axis)

    def test_no_shift_scores_better_than_big_shift(self):
        control = analyze(get_sample('no_shift_control')['brief'])
        tokyo = analyze(get_sample('tokyo_sprint')['brief'])
        self.assertGreater(control['score']['overall'], tokyo['score']['overall'])

    def test_long_runway_scores_better_than_short(self):
        long_run = analyze(get_sample('tokyo_sprint')['brief'])
        short = analyze(get_sample('short_haul_turnaround')['brief'])
        self.assertGreater(long_run['score']['axes']['recovery_runway'],
                           short['score']['axes']['recovery_runway'])

    def test_eastward_is_harder_than_westward_same_magnitude(self):
        east = analyze(
            "Home: Chicago\nHome sleep: 22:30\nHome wake: 06:30\n"
            "Flight: ORD -> LHR | depart 2026-11-03 11:00 | arrive 2026-11-03 23:00\n"
            "Stay: London | from 2026-11-03 | to 2026-11-12\n")
        west = analyze(
            "Home: Chicago\nHome sleep: 22:30\nHome wake: 06:30\n"
            "Flight: ORD -> HNL | depart 2026-11-03 11:00 | arrive 2026-11-03 15:00\n"
            "Stay: Honolulu | from 2026-11-03 | to 2026-11-12\n")
        self.assertGreater(west['score']['axes']['shift_severity'],
                           east['score']['axes']['shift_severity'])

    def test_date_line_crossing_is_detected(self):
        report = analyze(get_sample('tokyo_sprint')['brief'])
        self.assertTrue(report['legs'][0]['crosses_date_line'])

    def test_tokyo_from_chicago_is_a_delay(self):
        report = analyze(get_sample('tokyo_sprint')['brief'])
        self.assertLess(report['legs'][0]['effective_shift_h'], 0.0)
        self.assertEqual(report['legs'][0]['direction'], 'delay')

    def test_multi_stop_has_multiple_stays(self):
        report = analyze(get_sample('multi_stop_europe')['brief'])
        self.assertGreaterEqual(len(report['stays']), 3)

    def test_red_eye_flagged(self):
        report = analyze(get_sample('red_eye_return')['brief'])
        rules = [f['rule'] for f in report['findings']]
        self.assertIn('red_eye_arrival', rules)

    def test_event_assessed(self):
        report = analyze(get_sample('tokyo_sprint')['brief'])
        self.assertEqual(len(report['events']), 2)
        for ev in report['events']:
            self.assertIn(ev['verdict'], ('good', 'workable', 'risky', 'danger', 'unknown'))
            self.assertTrue(ev['advice'])

    def test_missing_events_produce_finding(self):
        report = analyze(
            "Home: Chicago\n"
            "Flight: ORD -> LHR | depart 2026-11-03 11:00 | arrive 2026-11-03 23:00\n"
            "Stay: London | from 2026-11-03 | to 2026-11-08\n")
        rules = [f['rule'] for f in report['findings']]
        self.assertIn('no_critical_events', rules)

    def test_findings_sorted_by_severity(self):
        order = ['critical', 'high', 'medium', 'low', 'info']
        report = analyze(get_sample('multi_stop_europe')['brief'])
        severities = [f['severity'] for f in report['findings']]
        ranks = [order.index(s) for s in severities]
        self.assertEqual(ranks, sorted(ranks))

    def test_plan_steps_are_numbered(self):
        report = analyze(get_sample('tokyo_sprint')['brief'])
        for i, step in enumerate(report['plan'], 1):
            self.assertEqual(step['step'], i)

    def test_profile_changes_weights(self):
        balanced = analyze(get_sample('tokyo_sprint')['brief'], 'balanced')
        conference = analyze(get_sample('tokyo_sprint')['brief'], 'conference')
        self.assertNotEqual(balanced['score']['weights'],
                            conference['score']['weights'])

    def test_invalid_brief_raises(self):
        with self.assertRaises(BriefError):
            analyze("nothing useful here")

    def test_days_have_alertness_curves(self):
        report = analyze(get_sample('tokyo_sprint')['brief'])
        for stay in report['stays']:
            for day in stay['days']:
                self.assertEqual(len(day['alertness']), 24)

    def test_adapted_percentage_increases(self):
        report = analyze(get_sample('tokyo_sprint')['brief'])
        days = report['stays'][0]['days']
        self.assertGreater(days[-1]['adapted_pct'], days[0]['adapted_pct'])


class TestExport(unittest.TestCase):
    def test_markdown_export(self):
        report = analyze(get_sample('tokyo_sprint')['brief'])
        md = to_markdown(report)
        self.assertIn('# ', md)
        self.assertIn('Scorecard', md)
        self.assertIn('Fix plan', md)
        self.assertIn('|', md)

    def test_json_export_parses(self):
        import json
        report = analyze(get_sample('tokyo_sprint')['brief'])
        parsed = json.loads(to_json(report))
        self.assertEqual(parsed['meta']['title'], report['meta']['title'])


class TestSamples(unittest.TestCase):
    def test_list_samples(self):
        listed = list_samples()
        self.assertEqual(len(listed), len(SAMPLES))
        for item in listed:
            self.assertIn('id', item)
            self.assertIn('summary', item)

    def test_get_sample(self):
        self.assertIsNotNone(get_sample('tokyo_sprint'))
        self.assertIsNone(get_sample('nope'))


class TestApi(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = tempfile.mkdtemp()
        import app as app_module
        self.app_module = app_module
        app_module.DB_PATH = os.path.join(self.tmp, 'test.db')
        app_module.init_db()
        self.client = app_module.app.test_client()

    def test_health(self):
        res = self.client.get('/api/health')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()['status'], 'ok')

    def test_analyze_endpoint(self):
        res = self.client.post('/api/analyze', json={
            'brief': get_sample('tokyo_sprint')['brief'], 'profile': 'balanced'})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn('score', data)
        self.assertIn('findings', data)

    def test_analyze_bad_brief(self):
        res = self.client.post('/api/analyze', json={'brief': 'nope'})
        self.assertEqual(res.status_code, 400)
        self.assertIn('error', res.get_json())

    def test_samples_endpoint(self):
        res = self.client.get('/api/samples')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.get_json()), len(SAMPLES))

    def test_profiles_endpoint(self):
        res = self.client.get('/api/profiles')
        self.assertEqual(res.status_code, 200)
        self.assertGreater(len(res.get_json()), 1)

    def test_journey_lifecycle(self):
        res = self.client.post('/api/journeys', json={
            'brief': get_sample('tokyo_sprint')['brief'], 'profile': 'balanced'})
        self.assertEqual(res.status_code, 201)
        journey_id = res.get_json()['id']

        res = self.client.get('/api/journeys')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.get_json()), 1)

        res = self.client.get('/api/journeys/%d' % journey_id)
        self.assertEqual(res.status_code, 200)
        self.assertIn('report', res.get_json())

        res = self.client.patch('/api/journeys/%d' % journey_id,
                                json={'rating': 4, 'notes': 'slept badly'})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()['rating'], 4)

        res = self.client.get('/api/journeys/%d' % journey_id)
        self.assertEqual(res.get_json()['notes'], 'slept badly')

    def test_missing_journey_404(self):
        res = self.client.get('/api/journeys/9999')
        self.assertEqual(res.status_code, 404)

    def test_export_endpoint(self):
        res = self.client.post('/api/export', json={
            'brief': get_sample('tokyo_sprint')['brief'], 'fmt': 'md'})
        self.assertEqual(res.status_code, 200)
        self.assertIn('Scorecard', res.get_data(as_text=True))

    def test_frontend_field_contract(self):
        """Every field the frontend reads must exist in the API payload."""
        res = self.client.post('/api/analyze', json={
            'brief': get_sample('tokyo_sprint')['brief'], 'profile': 'balanced'})
        data = res.get_json()
        for key in ('meta', 'score', 'legs', 'stays', 'events', 'findings', 'plan'):
            self.assertIn(key, data)
        for key in ('axes', 'axis_order', 'weights', 'overall', 'band', 'band_label', 'caps'):
            self.assertIn(key, data['score'])
        for key in ('title', 'home_place', 'home_tz', 'home_wake', 'home_sleep',
                    'chronotype', 'melatonin_mg', 'profile_label', 'axis_labels'):
            self.assertIn(key, data['meta'])
        for key in ('origin', 'dest', 'dep_local', 'arr_local', 'duration_h',
                    'effective_shift_h', 'direction', 'crosses_date_line',
                    'overnight', 'red_eye_arrival'):
            self.assertIn(key, data['legs'][0])
        for key in ('place', 'start', 'end', 'nights', 'effective_shift_h',
                    'direction', 'nights_to_sync', 'days'):
            self.assertIn(key, data['stays'][0])
        for key in ('date', 'day_index', 'body_clock_at_noon', 'body_bed_local',
                    'body_wake_local', 'recommended_bed_local', 'recommended_wake_local',
                    'actual_sleep_h', 'sleep_latency_h', 'alertness', 'light',
                    'caffeine', 'residual_error_h', 'adapted_pct', 'arrival_day'):
            self.assertIn(key, data['stays'][0]['days'][0])
        for key in ('kind', 'bright_start', 'bright_end', 'dim_start', 'dim_end'):
            self.assertIn(key, data['stays'][0]['days'][0]['light'])
        for key in ('cutoff', 'note'):
            self.assertIn(key, data['stays'][0]['days'][0]['caffeine'])
        for key in ('name', 'when_local', 'place', 'body_clock_time', 'alertness',
                    'verdict', 'advice'):
            self.assertIn(key, data['events'][0])
        for key in ('rule', 'severity', 'title', 'evidence', 'why', 'fix'):
            self.assertIn(key, data['findings'][0])
        for key in ('step', 'when', 'action', 'why'):
            self.assertIn(key, data['plan'][0])


if __name__ == '__main__':
    unittest.main()
