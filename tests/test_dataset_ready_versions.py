from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from check_dataset_ready_versions import ready_versions


class DatasetReadyVersionTests(unittest.TestCase):
    def test_new_ready_versions_override_stale_current_field(self):
        result=ready_versions({'currentVersionNumber':26,'versions':[
            {'versionNumber':28,'status':'Ready'},{'versionNumber':27,'status':'Ready'},
            {'versionNumber':26,'status':'Ready'}]},26)
        self.assertEqual(result['latest_ready_version'],28)
        self.assertEqual(result['status'],'newer_ready_version_available')
        self.assertTrue(result['current_field_lags_ready_versions'])

    def test_pending_version_is_not_treated_as_published(self):
        result=ready_versions({'currentVersionNumber':28,'versions':[
            {'versionNumber':30,'status':'Processing'},{'versionNumber':28,'status':'Ready'}]},28)
        self.assertEqual(result['latest_ready_version'],28)
        self.assertEqual(result['status'],'no_new_ready_version')

    def test_missing_versions_cannot_support_an_unchanged_claim(self):
        result=ready_versions({'currentVersionNumber':26},26)
        self.assertFalse(result['discovery_complete'])
        self.assertEqual(result['status'],'metadata_incomplete')

    def test_nullable_status_and_current_ahead_are_handled_explicitly(self):
        result=ready_versions({'currentVersionNumber':30,'versions':[
            {'versionNumber':28,'status':None,'statusNullable':'Ready'}]},28)
        self.assertEqual(result['latest_ready_version'],28)
        self.assertFalse(result['discovery_complete'])
        self.assertEqual(result['status'],'metadata_incomplete')


if __name__=='__main__':unittest.main()
