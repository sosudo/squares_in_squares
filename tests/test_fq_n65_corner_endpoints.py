from fractions import Fraction as F
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiments'))
from fq_n65_corner_endpoints import collision_interval,first_block,move,separation


def square(x,y):
    return [(F(x),F(y)),(F(x+1),F(y)),(F(x+1),F(y+1)),(F(x),F(y+1))]


class ExactCornerControls(unittest.TestCase):
    def test_first_contact_is_exact_and_beyond_it_overlaps(self):
        source=[square(0,0),square(2,0)]
        interval=collision_interval(source[0],source[1],(F(1),F(0)))
        self.assertEqual(interval,(F(1),F(3)))
        end,blockers=first_block(source,F(5),0,(F(1),F(0)))
        self.assertEqual(end,F(1));self.assertIn(('square',1),blockers)
        at=move(source,{0:((F(1),F(0)),end)})
        after=move(source,{0:((F(1),F(0)),end+F(1,100))})
        self.assertEqual(separation(at[0],at[1]),0)
        self.assertIsNone(separation(after[0],after[1]))

    def test_tangential_contact_does_not_limit_a_feasible_slide(self):
        source=[square(0,0),square(0,1)]
        self.assertIsNone(collision_interval(source[0],source[1],(F(1),F(0))))
        end,blockers=first_block(source,F(4),0,(F(1),F(0)))
        self.assertEqual(end,F(3));self.assertEqual(blockers,[('wall',0,1)])

    def test_immediate_blocker_is_not_mistaken_for_a_positive_interval(self):
        source=[square(0,0),square(1,0)]
        end,_=first_block(source,F(4),0,(F(1),F(0)))
        self.assertEqual(end,F(0))
