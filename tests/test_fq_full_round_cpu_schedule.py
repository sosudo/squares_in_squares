"""Pure controls for full-case restart exposure; no native solver is run."""
from collections import Counter, defaultdict
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'experiments'))
import fq_full_round_cpu_search as search
from fq_variant_campaign import geometry_sha


KEYS = ('12_12_3', '17_17_10', '18_18_11')
WEIGHTS = dict(zip(KEYS, (1, 1, 2)))


def fixtures():
    reference, pools, expected, donors = {}, {}, {}, {}
    for key in KEYS:
        w, h, d = map(int, key.split('_'))
        n = w*h+d
        p = np.zeros((n, 3))
        p[:, 0] = np.arange(n) % (w+1)
        p[:, 1] = np.arange(n) // (w+1)
        reference[key] = p
        pools[key] = {}
        expected[key] = []
        for index in range(2 if n == 335 else 1):
            q = p.copy()
            # The second n335 input is wider than the old .005 cutoff.
            q[q[:, 0].argmax(), 0] += .00627 if index else .00001
            sha = geometry_sha(q)
            name = key + '__control_' + str(index)
            donors[name] = q
            pools[key][sha] = dict(pose=q, excess=search.remote.fq.bloat(q,w,h),
                geometry_sha256=sha, source_archive='donor_0', source_name=name, bucket=sha)
            expected[key].append(sha)
    return reference, pools, expected, donors


class FullRoundedScheduleTests(unittest.TestCase):
    def test_weighted_case_prefixes_preserve_restart_fractions_and_all_source_modes(self):
        reference, pools, expected, _ = fixtures()
        frozen = search.freeze_start_sources(reference, pools, expected)
        modes = list(search.MODE_OPTIONS)
        visits = Counter({key: 0 for key in KEYS})
        roles = defaultdict(Counter)
        source_modes = defaultdict(set)
        observed_alternates = defaultdict(list)
        offsets = dict(zip(KEYS, range(len(KEYS))))
        for _ in range(128):
            key = min(KEYS, key=lambda k: (visits[k]/WEIGHTS[k], k))
            visit = visits[key]
            q, parent = search.choose_start(key, visit, reference, frozen)
            mode = search.select_mode(key, visit, offsets[key], frozen, modes)
            visits[key] += 1
            role = parent['selection']
            roles[key][role] += 1
            identity = parent['geometry_sha256'] if role == 'immutable_control' else role
            source_modes[key, identity].add(mode)
            self.assertEqual(geometry_sha(q), parent['geometry_sha256'])
            self.assertEqual(role, ('incumbent', 'immutable_control', 'incumbent', 'original_current')[visit % 4])
            self.assertEqual(roles[key]['original_current'], visits[key] // 4)
            self.assertEqual(roles[key]['immutable_control'], (visits[key]+2) // 4)
            if role == 'original_current':
                np.testing.assert_array_equal(q, reference[key])
            elif role == 'immutable_control':
                observed_alternates[key].append(identity)
        self.assertEqual(dict(visits), dict(zip(KEYS, (32, 32, 64))))
        for key in KEYS:
            self.assertEqual(roles[key], Counter(incumbent=visits[key]//2,
                immutable_control=visits[key]//4, original_current=visits[key]//4))
            for identity in ('incumbent', 'original_current', *expected[key]):
                self.assertEqual(source_modes[key, identity], set(modes), (key, identity))
            ids = sorted(expected[key])
            self.assertEqual(observed_alternates[key],
                [ids[i % len(ids)] for i in range(visits[key]//4)])

    def test_frozen_sources_survive_incumbent_and_returned_array_mutation(self):
        reference, pools, expected, _ = fixtures()
        frozen = search.freeze_start_sources(reference, pools, expected)
        key = KEYS[-1]
        original = reference[key].copy()
        alternate, parent = search.choose_start(key, 1, reference, frozen)
        expected_alternate_sha = parent['geometry_sha256']
        alternate[:] = -7
        reference[key][:] = 55
        for entry in pools[key].values():
            entry['pose'][:] = 99
        q, _ = search.choose_start(key, 3, reference, frozen)
        np.testing.assert_array_equal(q, original)
        q, parent = search.choose_start(key, 1, reference, frozen)
        self.assertEqual(geometry_sha(q), expected_alternate_sha)
        self.assertEqual(parent['geometry_sha256'], expected_alternate_sha)

    def test_actual_generated_loader_preserves_all_seven_inputs_and_wider335(self):
        reference, _, expected, donors = fixtures()
        config = dict(weights=WEIGHTS, alternative_geometry_hashes=expected)
        runtime, _, _ = search.build_runtime(config)

        class StopBeforeNativeWork(Exception):
            pass

        def stop_before_executor(**kwargs):
            self.assertEqual(kwargs['max_workers'], 4)
            raise StopBeforeNativeWork

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            np.savez(root/'reference.npz', **reference)
            np.savez(root/'donors.npz', **donors)
            (root/'priorities.json').write_text(json.dumps({key: 1 for key in KEYS}))
            (root/'unused_binary').write_text('No solver is executed by this control.\n')
            args = SimpleNamespace(reference=[root/'reference.npz'], donors=[root/'donors.npz'],
                priorities=root/'priorities.json', binary=root/'unused_binary', out=root/'campaign',
                seconds=1200., trial_seconds=60., workers=4, seed=7, max_trials=0)
            with patch.object(runtime.__globals__['os'], 'setsid'), patch.dict(
                    runtime.__globals__, ProcessPoolExecutor=stop_before_executor):
                with self.assertRaises(StopBeforeNativeWork):
                    runtime(args)
            manifest = json.loads((args.out/'manifest.json').read_text())
            sources = manifest['restart_policy']['sources']
            self.assertEqual(sum(1+len(row['alternatives']) for row in sources.values()), 7)
            for key in KEYS:
                self.assertEqual(sources[key]['original_geometry_sha256'], geometry_sha(reference[key]))
                self.assertEqual({row['geometry_sha256'] for row in sources[key]['alternatives']}, set(expected[key]))
            wide = max(row['excess'] for row in sources[KEYS[-1]]['alternatives'])
            self.assertGreater(wide, manifest['reference_excess_by_key'][KEYS[-1]]+.005)
            self.assertEqual(manifest['restart_policy']['input_side_cutoff'], None)


if __name__ == '__main__':
    unittest.main()
