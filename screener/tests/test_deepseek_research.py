from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import requests

from screener import deepseek_research as model
from screener import factor_research as research
from screener import research_signals as signals
from screener.tracking import write_json


def response(body=None, status=200):
    result = Mock(status_code=status)
    result.__enter__ = Mock(return_value=result)
    result.__exit__ = Mock(return_value=False)
    result.json.return_value = body
    result.iter_content.return_value = [json.dumps(body).encode()]
    return result


class DeepSeekTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.now = datetime(2026, 10, 19, tzinfo=timezone.utc)
        self.parent = {**deepcopy(signals.SEEDS[0]), 'id': 'factor_test', 'market': 'US',
                       'definition_hash': 'definition', 'engine_version': research.engine_version(),
                       'status': 'testing', 'generation': 1}
        self.state = {'programs': [self.parent]}
        self.proposal = {k: deepcopy(self.parent[k]) for k in model.BASE_FIELDS}
        self.proposal['research_card'] = {'version': 1, 'evidence': 'Supplied completed observations only',
            'failure_condition': 'Reject at the original fixed gate if no net improvement', 'data_risks': 'No news or fundamental data'}
        self.proposal.update(name='New gap test', expression=signals.feature('gap'), filters=[])
        self.value = {'proposals': [self.proposal]}

    def mature(self):
        for i in range(20):
            research.sealed(self.directory / 'research/settled' / f'factor_test_{i}.json', {
                'definition_hash': 'definition', 'due': True, 'entry_date': 20260901 + i,
                'exit_date': 20260907 + i, 'benchmark_pct': 0,
                **{k: {'complete': True, 'return_pct': 1} for k in ('branch', 'parent', 'pool')}})

    def body(self):
        return {'status': 'completed', 'output': [
            {'type': 'reasoning', 'content': [{'type': 'reasoning_text', 'text': 'PRIVATE_REASONING'}]},
            {'type': 'message', 'role': 'assistant', 'content': [{'type': 'output_text', 'text': json.dumps(self.value)}]}],
            'usage': {'input_tokens': 10, 'output_tokens': 20, 'total_tokens': 30}}

    def test_missing_key_never_contacts_provider(self):
        with patch.object(model.requests, 'get') as get:
            self.assertEqual(model.connection(''), 'missing_key')
            get.assert_not_called()

    def test_connection_checks_model_and_never_follows_redirect(self):
        with patch.object(model.requests, 'get', return_value=response({'data': [{'id': model.MODEL}]})) as get:
            self.assertEqual(model.connection('secret'), 'verified')
            self.assertFalse(get.call_args.kwargs['allow_redirects'])
        with patch.object(model.requests, 'get', return_value=response({}, 401)):
            self.assertEqual(model.connection('secret'), 'authentication_failed')
        with patch.object(model.requests, 'get', return_value=response({'data': []})):
            self.assertEqual(model.connection('secret'), 'model_unavailable')

    def test_request_is_bounded_no_tools_and_reasoning_is_not_persisted(self):
        with patch.object(model.requests, 'post', return_value=response(self.body())) as post:
            result = model.infer('SECRET', {'safe': 'summary'})
            request = post.call_args.kwargs
            self.assertEqual(post.call_args.args[0], 'https://api.deepseek.com/responses')
            self.assertEqual(request['json']['model'], 'deepseek-flash')
            self.assertEqual(request['json']['reasoning'], {'effort': 'high'})
            self.assertEqual(request['json']['max_output_tokens'], 4096)
            self.assertNotIn('tools', request['json'])
            self.assertFalse(request['allow_redirects'])
            self.assertNotIn('SECRET', json.dumps(request['json']))
            self.assertNotIn('PRIVATE_REASONING', json.dumps(result))
            self.assertEqual(result['value'], self.value)

    def test_retry_is_limited_and_auth_errors_do_not_retry(self):
        with patch.object(model.time, 'sleep'), patch.object(model.requests, 'post', side_effect=[response({}, 429), response(self.body())]) as post:
            self.assertEqual(model.infer('secret', {})['attempts'], 2)
            self.assertEqual(post.call_count, 2)
        for code in [401, 402, 403, 302]:
            with patch.object(model.requests, 'post', return_value=response({'secret': 'do not log'}, code)) as post:
                result = model.infer('secret', {})
                self.assertEqual(post.call_count, 1)
                self.assertNotIn('do not log', json.dumps(result))
        with patch.object(model.time, 'sleep'), patch.object(model.requests, 'post', side_effect=requests.Timeout('secret')) as post:
            self.assertEqual(model.infer('secret', {})['status'], 'network_error')
            self.assertEqual(post.call_count, 2)

    def test_truncated_malformed_and_oversized_responses_fail_closed(self):
        for body, expected in [({'status': 'incomplete'}, 'incomplete'), ([], 'invalid_response'),
                               ({'status': 'completed', 'output': []}, 'invalid_response')]:
            with patch.object(model.requests, 'post', return_value=response(body)):
                self.assertEqual(model.infer('secret', {})['status'], expected)
        huge = response({})
        huge.iter_content.return_value = [b'x' * 262145]
        with patch.object(model.requests, 'post', return_value=huge):
            self.assertEqual(model.infer('secret', {})['status'], 'response_limit')
        with patch.object(model.requests, 'post') as post:
            self.assertEqual(model.infer('secret', {'text': 'x' * 24001})['status'], 'input_too_large')
            post.assert_not_called()

    def test_proposals_are_bound_to_parent_and_reject_injection_and_duplicates(self):
        valid, rejected = model.validate_proposals(self.value, self.parent, self.state)
        self.assertFalse(rejected)
        self.assertEqual(valid[0]['parent_id'], self.parent['id'])
        self.assertEqual(valid[0]['market'], 'US')
        self.assertFalse(model.validate_proposals(self.value, self.parent, self.state, valid)[0])
        for invalid in [{**self.proposal, 'market': 'HK'}, {**self.proposal, 'name': ' '},
                        {**self.proposal, 'expression': {'op': 'eval', 'code': 'shell'}},
                        {**self.proposal, 'expression': signals.feature('unavailable_news')},
                        {**self.proposal, 'filters': [{'feature': 'gap', 'gte': float('nan')}]},
                        {k: self.parent[k] for k in model.BASE_FIELDS},
                        {**self.proposal, 'research_card': {'version': 1}},
                        {**self.proposal, 'research_card': {**self.proposal['research_card'], 'failure_condition': ' '}}]:
            accepted, rejected = model.validate_proposals({'proposals': [invalid]}, self.parent, self.state)
            self.assertFalse(accepted)
            self.assertEqual(len(rejected), 1)
        with self.assertRaises(ValueError):
            model.validate_proposals({'proposals': [self.proposal] * 4}, self.parent, self.state)

    def test_no_inference_before_twenty_complete_cohorts(self):
        with patch.object(model, 'infer') as infer:
            model.generate(self.directory, self.state, self.now, 'secret')
            infer.assert_not_called()
            self.assertFalse(model.records(self.directory))

    def test_completed_call_is_immutable_and_never_starts_a_strategy(self):
        self.mature()
        before = deepcopy(self.state)
        with patch.object(research, 'assess', return_value=({'paired': 20}, {})), patch.object(model, 'infer', return_value={'status': 'completed', 'value': self.value}) as infer:
            model.generate(self.directory, self.state, self.now, 'secret')
            model.generate(self.directory, self.state, self.now + timedelta(days=8), 'secret')
            self.assertEqual(infer.call_count, 1)
        self.assertEqual(self.state, before)
        self.assertEqual(len(model.records(self.directory)), 1)
        stored = list((self.directory / 'research/ai_requests').glob('*.result.json'))
        self.assertEqual(len(research.read_sealed(stored[0])['proposals']), 1)

    def test_interruption_reserves_budget_and_restart_does_not_repeat_charge(self):
        self.mature()
        with patch.object(research, 'assess', return_value=({}, {})), patch.object(model, 'infer', side_effect=RuntimeError('interrupted')):
            with self.assertRaises(RuntimeError):
                model.generate(self.directory, self.state, self.now, 'secret')
        with patch.object(model, 'infer') as infer:
            model.generate(self.directory, self.state, self.now + timedelta(days=8), 'secret')
            infer.assert_not_called()
        self.assertEqual(len(model.records(self.directory)), 1)

    def test_lifetime_limit_applies_before_requests(self):
        self.mature()
        for i in range(6):
            research.sealed(self.directory / 'research/ai_requests' / f'{i}.request.json',
                            {'at': (self.now - timedelta(days=20 + i)).isoformat(), 'parent_id': str(i)})
        with patch.object(model, 'infer') as infer:
            model.generate(self.directory, self.state, self.now, 'secret')
            infer.assert_not_called()

    def test_global_cooldown_applies_to_other_parents(self):
        self.mature()
        research.sealed(self.directory / 'research/ai_requests/previous.request.json',
                        {'at': self.now.isoformat(), 'parent_id': 'another-parent'})
        with patch.object(model, 'infer') as infer:
            model.generate(self.directory, self.state, self.now + timedelta(days=6), 'secret')
            infer.assert_not_called()

    def test_report_only_never_generates_and_exposes_no_credentials(self):
        output = self.directory / 'report.json'
        write_json(output, {'model_connected': False, 'programs': [self.parent]})
        with patch.dict(os.environ, {'DEEPSEEK_API_KEY': 'SECRET'}), patch.object(model, 'connection', return_value='verified'), patch.object(research, 'load_state', return_value=self.state), patch.object(model, 'generate') as generate:
            result = model.run(self.directory, output, now=self.now)
            generate.assert_not_called()
            self.assertTrue(result['model_connected'])
            self.assertNotIn('SECRET', json.dumps(result))
            self.assertEqual(result['model_research']['mode'], 'owner_review')


if __name__ == '__main__':
    unittest.main()
