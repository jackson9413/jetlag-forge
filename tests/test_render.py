"""Frontend render verification.

Executes the real static/app.js render functions against live API data
and asserts the produced HTML is correct. This catches the class of bug
where a renderer silently returns early and drops half of the report.

Run with:  python3 -m unittest discover -s tests -v
"""

import os
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HARNESS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'render_harness.js')


class TestFrontendRender(unittest.TestCase):
    """Runs the frontend against a live server and checks the HTML."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.port = 5099
        cls.proc = subprocess.Popen(
            [sys.executable, os.path.join(ROOT, 'app.py')],
            cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            env=dict(os.environ, PORT=str(cls.port)),
        )
        deadline = time.time() + 20
        while time.time() < deadline:
            try:
                urllib.request.urlopen(
                    'http://127.0.0.1:%d/api/health' % cls.port, timeout=1).read()
                break
            except Exception:
                time.sleep(0.3)
        else:
            raise RuntimeError('server did not start on port %d' % cls.port)

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        try:
            cls.proc.wait(timeout=5)
        except Exception:
            cls.proc.kill()

    def test_render_harness_passes(self):
        result = subprocess.run(
            ['node', HARNESS, ROOT, str(self.port)],
            capture_output=True, text=True, timeout=120,
        )
        self.assertEqual(
            result.returncode, 0,
            'frontend render checks failed:\n%s\n%s' % (result.stdout, result.stderr),
        )
        self.assertIn('ALL RENDER CHECKS PASSED', result.stdout)


if __name__ == '__main__':
    unittest.main()
