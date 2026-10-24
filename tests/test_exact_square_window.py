"""Independent brute-force and official positive controls for window sweep."""
import math
from pathlib import Path
import sys
import tempfile
import time
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'experiments'))
from exact_square_window import WindowSolver, boxes, certify, compile_solver, coordinate_text, metric_module


def brute_force(q,length):
    b = boxes(q)
    rectangles = [(x1-length,x0,y1-length,y0) for x0,y0,x1,y1 in b
        if x1-length<=x0 and y1-length<=y0]
    if not rectangles:return 0
    xs = {v for r in rectangles for v in r[:2]}
    ys = {v for r in rectangles for v in r[2:]}
    return max(sum(x0<=x<=x1 and y0<=y<=y1 for x0,x1,y0,y1 in rectangles) for x in xs for y in ys)


class ExactWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.binary = Path(cls.directory.name)/'window'
        compile_solver(cls.binary)

    @classmethod
    def tearDownClass(cls):cls.directory.cleanup()

    def test_closed_grid_boundaries_and_official_subset(self):
        q = np.array([[x+.5,y+.5,0.] for y in range(3) for x in range(3)])
        with WindowSolver(self.binary) as solver:
            solver.load(q)
            for length,expected in [(1.,1),(2.,4),(3.,9),(2.-1e-10,1)]:
                result = solver.query(length)
                self.assertEqual(result['count'],expected)
            result = solver.query(2.)
        selected = q[result['ids']]
        certificate = certify(selected,metric_module())
        self.assertIsNotNone(certificate)
        self.assertTrue(certificate['interval']['valid'])
        self.assertEqual(certificate['raw'][3],'ok')
        self.assertEqual(certificate['roundtrip'][3],'ok')
        self.assertEqual(certificate['default_roundtrip'][3],'ok')
        self.assertTrue(certificate['default_interval']['valid'])
        self.assertEqual(float(certificate['raw'][2]),2.)

    def test_export_preserves_certified_decimal_text(self):
        q = np.array([[.1,.2,0.]])
        text = coordinate_text(q)
        self.assertEqual(text,[['0.10000000000000001','0.20000000000000001','0']])
        certificate = certify(q,metric_module())
        self.assertIsNotNone(certificate)
        self.assertEqual(certificate['default_roundtrip'][3],'ok')

    def test_small_random_against_every_endpoint_pair(self):
        rng = np.random.default_rng(432917)
        with WindowSolver(self.binary) as solver:
            for _ in range(180):
                n = int(rng.integers(1,9))
                q = np.column_stack((rng.uniform(-3.,3.,(n,2)),rng.uniform(-math.pi/4,math.pi/4,n)))
                length = float(rng.uniform(.4,7.))
                solver.load(q);result = solver.query(length)
                self.assertEqual(result['count'],brute_force(q,length))
                self.assertEqual(len(result['ids']),result['count'])
                if result['count']:
                    b = boxes(q[result['ids']]);a = np.array([result['x'],result['y']])
                    self.assertTrue(np.all(b[:,:2]>=a-2e-12))
                    self.assertTrue(np.all(b[:,2:]<=a+length+2e-12))

    def test_query_timeout_stops_owned_worker(self):
        sleeper = Path(self.directory.name)/'sleeper'
        sleeper.write_text('#!'+sys.executable+'\nimport time\ntime.sleep(10)\n')
        sleeper.chmod(0o700)
        started = time.monotonic()
        solver = WindowSolver(sleeper,timeout=.04)
        with self.assertRaises(TimeoutError):solver.load(np.array([[.5,.5,0.]]))
        self.assertIsNotNone(solver.process.poll())
        self.assertLess(time.monotonic()-started,1.)


if __name__=='__main__':unittest.main()
