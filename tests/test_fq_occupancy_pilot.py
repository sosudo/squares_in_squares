from pathlib import Path
import sys
import unittest
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiments'))
import fq_occupancy_pilot as subject


class OccupancyPilotControls(unittest.TestCase):
    def test_writer_preserves_invalid_coordinates_and_explicit_nominal_box(self):
        p=np.zeros((335,3));p[:,0]=np.arange(335);p[0,1]=-.002;p[1,2]=.2
        encoded,offset=subject.fixed_box_encode(p,18,18)
        lines=encoded.splitlines();rows=np.array([[float(x)for x in line.split()]for line in lines[1:]])
        self.assertEqual(offset,[0,0]);self.assertEqual(float(lines[0].split()[1]),18.803)
        self.assertTrue(np.array_equal(rows[:,:2],p[:,:2]));self.assertEqual(rows[0,1],-.002)
        self.assertAlmostEqual(np.radians(rows[1,2]),.2)

    def test_held_trace_rejects_larger_actual_envelope_box(self):
        logs='\n'.join(f'round r {(.4*(1-k/12)**2):.4f} hold18.803 viol0'for k in range(1,13))
        # Actual native stderr includes the required separating space.
        logs=logs.replace('hold18','hold 18')
        report={'round':{'r0':.4,'s_soft':18.803,'s_hold':18.803}}
        self.assertTrue(subject.held_trace(report,logs)['valid'])
        report['round']['s_hold']=18.8088
        self.assertFalse(subject.held_trace(report,logs)['valid'])


if __name__=='__main__':unittest.main()
