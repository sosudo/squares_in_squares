"""Immutable inputs stay eligible after arbitrarily many better outputs."""
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'experiments'))
import fq_fixed_pool_campaign as fixed


def entry(pose, name):
    return {'pose': pose, 'geometry_sha256': fixed.geometry_sha(pose),
            'source_archive': 'original_frozen_input', 'source_name': name,
            'bucket': name, 'excess': .936648}


class FixedPoolTests(unittest.TestCase):
    def test_old_sources_are_sampled_and_bound_after_many_better_arrivals(self):
        key = '7_21_15'
        originals = [np.array([[float(i), .5, 0.]]) for i in range(5)]
        pools = {key: {str(i): entry(p, str(i)) for i, p in enumerate(originals)}}
        immutable = fixed.freeze_original_pools(pools, [key])
        expected = [item['geometry_sha256'] for item in immutable[key]]
        best = {key: np.array([[100., .5, 0.]])}
        seen, count = [], 0
        for visit in range(80):
            # Thousands of newly arriving, numerically better pool entries
            # cannot alter the frozen geometry-hash cycle.
            for index in range(50):
                pose = np.array([[1000.+visit*50+index, .5, 0.]])
                value = entry(pose, f'new-{visit}-{index}'); value['excess'] = .932818
                pools[key][value['bucket']] = value
            pose, parent = fixed.choose_start(key, visit, best, immutable)
            self.assertEqual(fixed.geometry_sha(pose), parent['geometry_sha256'])
            if parent['selection'] == 'immutable_input':
                count += 1; seen.append(parent['geometry_sha256'])
                self.assertEqual(parent['source_archive'], 'original_frozen_input')
                self.assertEqual(parent['source_name'], immutable[key][parent['source_pool_index']]['source_name'])
        self.assertEqual(count, 20)
        self.assertEqual(seen, expected*4)
        originals[0][:] = -999
        returned, _ = fixed.choose_start(key, 3, best, immutable)
        returned[:] = 999
        self.assertEqual([fixed.geometry_sha(x['pose']) for x in immutable[key]], expected)

    def test_empty_or_misidentified_sources_fail_closed(self):
        with self.assertRaisesRegex(ValueError, 'No immutable'):
            fixed.freeze_original_pools({'x': {}}, ['x'])
        value = entry(np.array([[.5, .5, 0.]]), 'one')
        value['geometry_sha256'] = 'wrong'
        with self.assertRaisesRegex(ValueError, 'identity'):
            fixed.freeze_original_pools({'x': {'one': value}}, ['x'])


if __name__ == '__main__':
    unittest.main()
