"""Real gateway preflight and sanitized HTTP failures, with no network calls."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import MagicMock, Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import submission_scheduler as scheduler
import test_submission_scheduler as fixtures


class NotebookAttachmentTests(unittest.TestCase):
    def setUp(self):
        self.sdk = ModuleType('kagglesdk.kernels.types.kernels_api_service')
        for name in ('ApiGetKernelRequest', 'ApiGetKernelSessionStatusRequest',
                     'ApiDownloadKernelOutputRequest'):
            setattr(self.sdk, name, SimpleNamespace)
        requests_stub = ModuleType('requests')
        requests_stub.get = Mock(side_effect=AssertionError('Unexpected network call'))
        self.modules = patch.dict(sys.modules, {self.sdk.__name__: self.sdk,
                                               'requests': requests_stub})
        self.modules.start()
        self.addCleanup(self.modules.stop)
        self.metadata = SimpleNamespace(current_version_number=2, is_private=True,
                                        competition_data_sources=[scheduler.COMPETITION])
        self.api = Mock()
        self.api.get_kernel.return_value = SimpleNamespace(metadata=self.metadata)
        self.api.get_kernel_session_status.return_value = SimpleNamespace(
            status=SimpleNamespace(name='COMPLETE'))
        self.api.download_kernel_output.return_value = SimpleNamespace(url='https://example.test/output')
        self.gateway = scheduler.KaggleGateway()
        self.gateway.client = SimpleNamespace(kernels=SimpleNamespace(kernels_api_client=self.api))
        self.notebook = dict(ref='owner/notebook', version=2, output_file='submission.csv')

    def test_missing_or_near_match_attachment_blocks_before_status_and_download(self):
        with patch('requests.get') as download:
            for sources in (None, [], ['squares-in-squares-other'], 'squares-in-squares',
                            ['https://www.kaggle.com/competitions/squares-in-squares']):
                with self.subTest(sources=sources):
                    self.metadata.competition_data_sources = sources
                    with self.assertRaisesRegex(ValueError, 'attach the exact'):
                        self.gateway.verify_notebook(self.notebook, 'unused')
            self.api.get_kernel_session_status.assert_not_called()
            self.api.download_kernel_output.assert_not_called()
            download.assert_not_called()

    def test_exact_attachment_is_recorded_only_after_complete_output_hash_check(self):
        data = b'exact certified output\r\n'
        response = MagicMock()
        response.__enter__.return_value = response
        response.iter_content.return_value = [data[:5], data[5:]]
        with patch('requests.get', return_value=response):
            proof = self.gateway.verify_notebook(self.notebook, hashlib.sha256(data).hexdigest())
        self.assertEqual(proof['competition_sources'], [scheduler.COMPETITION])
        self.assertEqual(proof['status'], 'complete')
        self.assertEqual(self.api.get_kernel.call_args.args[0].version_label, 'v2')
        self.assertEqual(self.api.download_kernel_output.call_args.args[0].version_number, 2)

    def test_attachment_failure_prevents_submit_and_pending_intent(self):
        fixture = fixtures.SchedulerTests()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        self.metadata.competition_data_sources = []
        fake = fixtures.FakeGateway()
        fake.verify_notebook = self.gateway.verify_notebook
        state = scheduler.new_state()
        saved = []
        with self.assertRaisesRegex(ValueError, 'attach the exact'):
            scheduler.controller([fixture.candidate], state, fake, fixtures.NOW,
                                 execute=True, persist=lambda x: saved.append(deepcopy(x)),
                                 policy=fixtures.POLICY)
        self.assertEqual(fake.submitted, 0)
        self.assertIsNone(state['pending'])
        self.assertEqual(saved, [])


class SafeHttpDiagnosticsTests(unittest.TestCase):
    @staticmethod
    def error(payload, status=400):
        class Response:
            def __bool__(self):
                return self.status_code < 400

            def json(self):
                return json.loads(self._content)

        class HTTPError(Exception):
            def __init__(self, message, response):
                super().__init__(message)
                self.response = response

        response = Response()
        response.status_code = status
        response.url = 'https://example.test/?secret=DO_NOT_RETAIN'
        response._content = json.dumps(payload).encode()
        return HTTPError('secret=DO_NOT_RETAIN', response=response)

    def test_only_integer_codes_survive_falsey_http_error_response(self):
        error = self.error({'code': 409, 'message': 'secret=DO_NOT_RETAIN',
                            'url': 'https://example.test/?secret=DO_NOT_RETAIN'})
        self.assertFalse(error.response)
        self.assertEqual(scheduler.safe_error_diagnostics(error),
                         {'status_code': 400, 'error_code': 409})
        for code in ('DO_NOT_RETAIN', '409', 409.0, True, {'secret': 'DO_NOT_RETAIN'}, 2 ** 40):
            with self.subTest(code=code):
                self.assertEqual(scheduler.safe_error_diagnostics(self.error({'code': code})),
                                 {'status_code': 400})
        self.assertEqual(scheduler.safe_error_diagnostics(TimeoutError('DO_NOT_RETAIN')), {})
        error.response._content = b'<html>DO_NOT_RETAIN</html>'
        self.assertEqual(scheduler.safe_error_diagnostics(error), {'status_code': 400})

    def test_safe_codes_persist_without_retry_or_error_text(self):
        fixture = fixtures.SchedulerTests()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        error = self.error({'code': 422, 'message': 'DO_NOT_RETAIN'})

        class HttpGateway(fixtures.FakeGateway):
            def submit_notebook(inner, notebook, description):
                inner.submitted += 1
                raise error

        gateway = HttpGateway()
        result, state, saved = fixture.run_controller(gateway, execute=True)
        self.assertEqual(result['action'], 'ambiguous')
        for record in (result, state['pending']):
            self.assertEqual(record['status_code'], 400)
            self.assertEqual(record['error_code'], 422)
        self.assertNotIn('DO_NOT_RETAIN', json.dumps([result, state, saved]))
        again, blocked, _ = fixture.run_controller(gateway, state, execute=True)
        self.assertEqual(again['action'], 'blocked')
        self.assertIsNotNone(blocked['pending'])
        self.assertEqual(gateway.submitted, 1)


if __name__ == '__main__':
    unittest.main()
