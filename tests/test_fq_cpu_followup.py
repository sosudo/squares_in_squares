"""The frozen per-lane scheduler must call the controlled actual treatment."""
import hashlib
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'experiments'))
import fq_cpu_followup_search as followup


class FollowupPolicyTests(unittest.TestCase):
    def setUp(self):
        self.original=followup.large.local._ordinary_campaign
        self.trial=followup.remote.fq.trial
        self.release=followup.productive.local.RELEASE_OPTIONS
        self.globals={name:getattr(followup.productive.campaign,name)for name in
            ['MODE_SLOTS','KICK_OPTIONS','FOCUS','configured_trial']}

    def tearDown(self):
        followup.large.local._ordinary_campaign=self.original
        followup.remote.fq.trial=self.trial
        followup.productive.local.RELEASE_OPTIONS=self.release
        for name,value in self.globals.items():setattr(followup.productive.campaign,name,value)

    def configure(self,policy):
        _,source=followup.productive.fixed.build_runtime()
        config=dict(policy=policy,weights={'8_20_12':1,'20_8_12':1},
            generated_runtime_sha256=hashlib.sha256(source.encode()).hexdigest())
        followup.configure_lane(config)
        return followup.large.local._ordinary_campaign.__globals__

    def test_productive_actual_namespace_has_two_modes_strict_hook_and_alm(self):
        namespace=self.configure('productive40_060')
        self.assertIs(namespace['configured_trial'],followup.productive.productive_trial)
        self.assertIs(namespace['fq'].trial,followup.remote.strict_trial)
        self.assertEqual(namespace['MODE_SLOTS'],['productive_circle_060','productive_contact_060'])
        for options in namespace['KICK_OPTIONS'].values():
            self.assertEqual(options[options.index('--soft-a0')+1],'.6')
            self.assertEqual(options[options.index('--soft-steps')+1],'16')
        self.assertEqual(followup.productive.local.RELEASE_OPTIONS,followup.RELEASE)

    def test_large_actual_namespace_has_only_controlled64_and_original_release(self):
        namespace=self.configure('connected64_030')
        self.assertIs(namespace['configured_trial'],followup.large.large_trial)
        self.assertIs(namespace['fq'].trial,followup.remote.strict_trial)
        self.assertEqual(namespace['MODE_SLOTS'],['large_064_soft_030'])
        options=namespace['KICK_OPTIONS']['large_064_soft_030']
        self.assertEqual(options[options.index('--soft-a0')+1],'.3')
        self.assertEqual(options[options.index('--soft-steps')+1],'12')
        self.assertEqual(followup.productive.local.RELEASE_OPTIONS,followup.RELEASE)
        self.assertNotIn('--no-alm',followup.productive.local.RELEASE_OPTIONS)

    def test_uncontrolled_policy_and_changed_runtime_rejected(self):
        with self.assertRaisesRegex(ValueError,'actually controlled'):
            followup.configure_lane({'policy':'connected96_030'})
        with self.assertRaisesRegex(ValueError,'scheduler source changed'):
            followup.configure_lane(dict(policy='connected64_030',weights={},generated_runtime_sha256='0'*64))


if __name__=='__main__':unittest.main()
