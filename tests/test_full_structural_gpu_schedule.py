"""Finite-prefix and eventual coverage of the immutable-source scheduler."""
import collections
import itertools
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'experiments'))
from full_structural_gpu_schedule import BalancedSeedScheduler


def sources(n,size):
    return [f'n{n}_source_{i:03d}'for i in range(size)]


class BalancedSeedSchedulerTests(unittest.TestCase):
    def test_pool32_batch32_does_not_repeat_the_old24_source_subset(self):
        ids=sources(299,32)
        old={ids[i%32]for i in range(4*32)if i%4}
        self.assertEqual(len(old),24)  # Actual modulo-coupling failure mode.
        schedule=BalancedSeedScheduler({299:ids})
        visits=[schedule.next(299)for _ in range(2*32)]
        alternatives=[r['source_id']for r in visits if not r['is_reference']]
        self.assertEqual(alternatives,ids+ids[:16])
        self.assertEqual(set(alternatives),set(ids))
        self.assertEqual(sum(r['is_reference']for r in visits),16)

    def test_every_budget_prefix_obeys_quarter_reference_and_sequential_alternatives(self):
        ids=sources(299,32);schedule=BalancedSeedScheduler({299:ids})
        seen=[];references=0;per_source=collections.Counter()
        for ordinal in range(173):
            row=schedule.next(299)
            self.assertEqual(row['family_start_ordinal'],ordinal)
            self.assertEqual(row['is_reference'],ordinal%4==0)
            self.assertEqual(row['source_visit'],per_source[row['source_id']])
            per_source[row['source_id']]+=1
            if row['is_reference']:
                references+=1;self.assertIsNone(row['source_index'])
            else:
                self.assertEqual(row['source_index'],len(seen)%32)
                self.assertEqual(row['source_id'],ids[len(seen)%32]);seen.append(row['source_id'])
            self.assertEqual(references,(ordinal+4)//4)
            self.assertEqual(row['alternative_cursor_after'],len(seen))
            self.assertEqual(len(set(seen)),min(32,len(seen)))
        # All32 sources are seen after43 starts, not after an impossible32
        # starts that must reserve eight slots for current-reference controls.
        fresh=BalancedSeedScheduler({299:ids})
        prefix=[fresh.next(299)for _ in range(43)]
        self.assertEqual(len({r['source_id']for r in prefix if not r['is_reference']}),32)

    def test_family_interleavings_do_not_change_per_family_schedule(self):
        pools={299:sources(299,33),335:sources(335,17),147:sources(147,5)}
        mixed=BalancedSeedScheduler(pools);isolated={n:BalancedSeedScheduler({n:v})for n,v in pools.items()}
        pattern=[299,335,299,147,299,299,335,147,335]
        actual=collections.Counter()
        for n in pattern*120:
            self.assertEqual(mixed.next(n),isolated[n].next(n));actual[n]+=1
        state=mixed.snapshot()
        self.assertEqual(state['family_starts'],{str(n):v for n,v in actual.items()})
        for n,ids in pools.items():
            self.assertTrue(all(state['source_visits'][str(n)][name]>0 for name in ids))

    def test_each_source_and_reference_reaches_every_operator_amplitude_depth_slack_tuple(self):
        ids=sources(299,33);schedule=BalancedSeedScheduler({299:ids})
        names=[f'current_299',*ids];seen={name:set()for name in names}
        expected=set(itertools.product(schedule.MODES,schedule.AMPLITUDES,
                                       schedule.TARGET_DEPTHS,schedule.LOOSE_SLACK))
        self.assertEqual(len(expected),240)
        # 240 visits/source is the complete joint period; the separate
        # alternative cursor prevents batch-size or quarter-policy aliasing.
        for _ in range(4*((len(ids)*240+2)//3)+4):
            row=schedule.next(299)
            seen[row['source_id']].add((row['mode'],row['amplitude'],row['target_depth'],row['loose_slack']))
        for name in names:self.assertEqual(seen[name],expected,name)

    def test_paired_instances_and_batch_boundaries_are_identical(self):
        pools={299:sources(299,32),335:sources(335,33)}
        a=BalancedSeedScheduler(pools);b=BalancedSeedScheduler(pools)
        families=([299]*32+[335]*32+[299]*17+[335]*11)*4
        first=[a.next(n)for n in families];second=[]
        for start in range(0,len(families),7):
            second.extend(b.next(n)for n in families[start:start+7])
        self.assertEqual(first,second);self.assertEqual(a.snapshot(),b.snapshot())

    def test_frozen_order_is_used_verbatim(self):
        ids=['z_lowest_side','b_alternative','a_alternative','y_other']
        schedule=BalancedSeedScheduler({299:ids})
        rows=[schedule.next(299)for _ in range(6)]
        self.assertEqual([r['source_id']for r in rows if not r['is_reference']],ids)

    def test_invalid_inventories_and_unknown_family_fail(self):
        for source_ids in ({},{299:[]},{299:['']},{299:['same','same']},{299:['current_299']},{299:[1]}):
            with self.assertRaises(ValueError):BalancedSeedScheduler(source_ids)
        schedule=BalancedSeedScheduler({299:sources(299,1)})
        with self.assertRaises(ValueError):schedule.next(335)


if __name__=='__main__':unittest.main()
