"""Enrollment and readiness checks use temporary files and a fake transport only."""
from contextlib import redirect_stdout
import getpass
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import yaml
from app.core.contracts import EngineError
from app.channels.telegram import TelegramError
from app.config.schema import (ConfigurationFileError, load_config, load_enrollment_config,
                               load_enrollment_secrets, read_yaml, validate_telegram_token,
                               TelegramSecretsError)
from scripts.check_telegram_i2 import check
from scripts.setup_telegram_i2 import discover, enroll, prepare, read_token, main

ROOT = Path(__file__).resolve().parents[1]
FAKE_TOKEN = '9009:' + 'X'*30


class TelegramSetupTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='vert2go-setup-test-')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        shutil.copyfile(ROOT/'config.telegram.example.yaml', self.root/'config.telegram.example.yaml')
        self.stream = io.StringIO()
        blocker = patch('socket.create_connection', side_effect=AssertionError('No network in setup tests'))
        blocker.start()
        self.addCleanup(blocker.stop)

    def configured(self):
        shutil.copyfile(ROOT/'config.telegram.example.yaml', self.root/'config.yaml')
        (self.root/'secrets.yaml').write_text(yaml.safe_dump({
            'telegram_bot_token': FAKE_TOKEN, 'openai_api_key': None, 'google_oauth': None}), encoding='utf-8')

    def snapshots(self):
        return [(self.root/name).read_bytes() for name in ('config.yaml', 'secrets.yaml')]

    def test_prepare_uses_nulls_and_preserves_existing_files_byte_for_byte(self):
        prepare(self.root)
        raw = yaml.safe_load((self.root/'config.yaml').read_text(encoding='utf-8'))
        self.assertIsNone(raw['channels']['telegram']['bot_id'])
        self.assertEqual([u['chat_ids'] for u in raw['users']], [[None], [None]])
        before = self.snapshots()
        prepare(self.root)
        self.assertEqual(before, self.snapshots())
        self.assertEqual(check(self.root)['local_configuration'], 'blocked')

    def test_windows_existing_protected_files_are_not_opened_for_creation(self):
        prepare(self.root)
        before = self.snapshots()
        original_open = Path.open
        def protected_open(path, mode='r', *args, **kwargs):
            if path.name in ('config.yaml', 'secrets.yaml') and mode == 'x':
                raise PermissionError('FAKE_PRIVATE_ACCESS_DETAIL')
            return original_open(path, mode, *args, **kwargs)
        with patch.object(Path, 'open', protected_open):
            prepare(self.root)
        self.assertEqual(before, self.snapshots())

    def test_permission_denial_is_not_reported_as_yaml_syntax_error(self):
        for name in ('config.yaml', 'secrets.yaml'):
            with patch.object(Path, 'open', side_effect=PermissionError('FAKE_SECRET')):
                with self.assertRaises(ConfigurationFileError) as error:
                    read_yaml(self.root/name)
            self.assertEqual(error.exception.code, 'configuration_read_denied')
            self.assertEqual(error.exception.diagnostic, {'file': name})
            self.assertNotIn('FAKE_SECRET', str(error.exception))

    def test_missing_file_and_syntax_error_have_distinct_redacted_diagnostics(self):
        with self.assertRaises(ConfigurationFileError) as missing:
            read_yaml(self.root/'secrets.yaml')
        self.assertEqual(missing.exception.code, 'configuration_file_missing')
        (self.root/'secrets.yaml').write_text('telegram_bot_token: [FAKE_SECRET\n', encoding='utf-8')
        with self.assertRaises(ConfigurationFileError) as syntax:
            read_yaml(self.root/'secrets.yaml')
        self.assertEqual(syntax.exception.code, 'invalid_yaml')
        self.assertEqual(syntax.exception.diagnostic['file'], 'secrets.yaml')
        self.assertIn('line', syntax.exception.diagnostic)
        self.assertNotIn('FAKE_SECRET', json.dumps(syntax.exception.diagnostic))

    def test_drafts_pass_enrollment_schema_but_never_runtime_validation(self):
        prepare(self.root)
        self.assertIsNone(load_enrollment_config(self.root/'config.yaml')['channels']['telegram']['bot_id'])
        self.assertIsNone(load_enrollment_secrets(self.root/'secrets.yaml')['telegram_bot_token'])
        with self.assertRaises(EngineError):
            load_config(self.root/'config.yaml')
        report = check(self.root, allow_live=True)
        self.assertEqual(report['config_yaml'], 'passed')
        self.assertEqual(report['secrets_yaml'], 'passed')
        self.assertEqual(report['enrollment_structure'], 'passed')
        self.assertEqual(report['reason'], 'telegram_enrollment_incomplete')
        self.assertEqual(set(report['missing_fields']), {'channels.telegram.bot_id',
            'users.resident.channel_user_id', 'users.manager.channel_user_id', 'telegram_bot_token'})
        self.assertFalse(report['external_api_attempted'])

    def test_valid_draft_reaches_secure_prompt_before_any_external_call(self):
        prepare(self.root)
        before = self.snapshots()
        class PromptReached(Exception):
            pass
        with patch('sys.stdin.isatty', return_value=True), \
                patch('getpass.getpass', side_effect=PromptReached), \
                patch('scripts.setup_telegram_i2.TelegramAPI', side_effect=AssertionError('No API')):
            with self.assertRaises(PromptReached):
                enroll(self.root, discovery=True, allow_live=True)
        self.assertEqual(before, self.snapshots())

    def test_invalid_nonidentity_parameter_is_rejected_before_prompt_or_api(self):
        prepare(self.root)
        config = read_yaml(self.root/'config.yaml')
        config['channels']['telegram']['request_seconds'] = 1
        (self.root/'config.yaml').write_text(yaml.safe_dump(config), encoding='utf-8')
        before = self.snapshots()
        with patch('getpass.getpass', side_effect=AssertionError('No prompt')), \
                patch('scripts.setup_telegram_i2.TelegramAPI', side_effect=AssertionError('No API')):
            with self.assertRaisesRegex(EngineError, 'unsafe_configuration'):
                enroll(self.root, discovery=True, allow_live=True)
        self.assertEqual(before, self.snapshots())

    def test_partial_enrollment_preserves_existing_token_bytes(self):
        prepare(self.root)
        (self.root/'secrets.yaml').write_text('# PRESERVE COMMENT\n'+yaml.safe_dump({
            'telegram_bot_token': FAKE_TOKEN, 'openai_api_key': None, 'google_oauth': None}), encoding='utf-8')
        before = (self.root/'secrets.yaml').read_bytes()
        with patch('getpass.getpass', side_effect=AssertionError('No token prompt')), \
                patch('builtins.input', side_effect=['10101', '20202']), redirect_stdout(self.stream):
            enroll(self.root)
        self.assertEqual(before, (self.root/'secrets.yaml').read_bytes())
        self.assertEqual(load_config(self.root/'config.yaml').telegram['bot_id'], 9009)

    def test_checker_identifies_inaccessible_file_without_leaking_exception(self):
        self.configured()
        real_open = Path.open
        def denied_read(path, mode='r', *args, **kwargs):
            if path == self.root/'secrets.yaml' and mode == 'rb':
                raise PermissionError('FAKE_SECRET')
            return real_open(path, mode, *args, **kwargs)
        with patch.object(Path, 'open', denied_read):
            report = check(self.root, allow_live=True)
        self.assertEqual(report['reason'], 'configuration_read_denied')
        self.assertEqual(report['diagnostic'], {'file': 'secrets.yaml'})
        self.assertEqual(report['config_yaml'], 'passed')
        self.assertFalse(report['external_api_attempted'])
        self.assertNotIn('FAKE_SECRET', json.dumps(report))

    def test_draft_cannot_relax_permissions_channel_or_other_null_fields(self):
        prepare(self.root)
        original = read_yaml(self.root/'config.yaml')
        from copy import deepcopy
        for mutate in (
            lambda raw: raw['permissions']['resident'].append('guidance.create'),
            lambda raw: raw['channels']['telegram'].__setitem__('poll_seconds', None),
            lambda raw: raw['users'][0].__setitem__('enabled', False),
            lambda raw: raw['users'][0].__setitem__('chat_ids', [None, 1001]),
        ):
            raw = deepcopy(original)
            mutate(raw)
            (self.root/'config.yaml').write_text(yaml.safe_dump(raw), encoding='utf-8')
            with self.assertRaises(EngineError):
                load_enrollment_config(self.root/'config.yaml')

    def test_complete_existing_setup_is_unchanged_and_never_prompts(self):
        self.configured()
        before = self.snapshots()
        with patch('builtins.input', side_effect=AssertionError('No prompts')), redirect_stdout(self.stream):
            enroll(self.root)
        self.assertEqual(before, self.snapshots())
        self.assertNotIn(FAKE_TOKEN, self.stream.getvalue())

    def test_new_setup_gets_hidden_token_and_explicit_role_ids(self):
        prepare(self.root)
        with patch('sys.stdin.isatty', return_value=True), patch('getpass.getpass', return_value=FAKE_TOKEN), \
                patch('builtins.input', side_effect=['10101', '20202']), redirect_stdout(self.stream):
            enroll(self.root)
        config = yaml.safe_load((self.root/'config.yaml').read_text(encoding='utf-8'))
        self.assertEqual([(u['role'], u['channel_user_id'], u['chat_ids']) for u in config['users']],
                         [('resident', 10101, [10101]), ('manager', 20202, [20202])])
        self.assertEqual(check(self.root)['local_token'], 'passed')
        self.assertNotIn(FAKE_TOKEN, self.stream.getvalue())

    def test_duplicate_participant_ids_are_not_saved_after_valid_token_stage(self):
        prepare(self.root)
        before = self.snapshots()
        with patch('sys.stdin.isatty', return_value=True), patch('getpass.getpass', return_value=FAKE_TOKEN), \
                patch('builtins.input', side_effect=['10101', '10101']), redirect_stdout(self.stream):
            with self.assertRaises(EngineError):
                enroll(self.root)
        config = read_yaml(self.root/'config.yaml')
        self.assertEqual(config['channels']['telegram']['bot_id'], 9009)
        self.assertTrue(all(user['channel_user_id'] is None for user in config['users']))
        self.assertEqual(load_enrollment_secrets(self.root/'secrets.yaml')['telegram_bot_token'], FAKE_TOKEN)

    def test_noninteractive_token_and_echo_fallback_are_refused(self):
        prepare(self.root)
        before = self.snapshots()
        with patch('sys.stdin.isatty', return_value=False):
            with self.assertRaisesRegex(EngineError, 'interactive_terminal_required'):
                enroll(self.root)
        with patch('sys.stdin.isatty', return_value=True), \
                patch('getpass.getpass', side_effect=getpass.GetPassWarning('sensitive')):
            with self.assertRaisesRegex(EngineError, 'secure_terminal_required'):
                enroll(self.root)
        self.assertEqual(before, self.snapshots())

    def test_discovery_authorization_checked_before_any_file_is_created(self):
        with self.assertRaisesRegex(EngineError, 'live_telegram_authorization_required'):
            enroll(self.root, discovery=True)
        self.assertFalse((self.root/'config.yaml').exists())

    def test_discovery_never_acknowledges_or_prints_unrecognized_content(self):
        api = MagicMock()
        api.call.return_value = [{'message': {'from': {'id': 1001, 'is_bot': False},
            'chat': {'id': 1001, 'type': 'private'}, 'text': '/cadastro_morador'}},
            {'message': {'from': {'id': 2002, 'is_bot': False},
            'chat': {'id': 2002, 'type': 'private'}, 'text': 'PRIVATE_UNRECOGNIZED_CONTENT'}}]
        with redirect_stdout(self.stream):
            discover(api)
        api.call.assert_called_once_with('getUpdates', {'limit': 100, 'timeout': 0})
        self.assertIn('1001', self.stream.getvalue())  # IDs appear only in the user's local terminal.
        self.assertIn('2002', self.stream.getvalue())
        self.assertNotIn('PRIVATE_UNRECOGNIZED_CONTENT', self.stream.getvalue())

    def test_existing_i1_configuration_is_not_converted(self):
        self.configured()
        shutil.copyfile(ROOT/'config.example.yaml', self.root/'config.yaml')
        before = self.snapshots()
        with self.assertRaisesRegex(EngineError, 'existing_config_requires_manual_review'):
            enroll(self.root)
        self.assertEqual(before, self.snapshots())

    def test_bot_change_is_rejected_and_existing_files_preserved(self):
        self.configured()
        text = (self.root/'secrets.yaml').read_text(encoding='utf-8').replace('9009:', '8008:')
        (self.root/'secrets.yaml').write_text(text, encoding='utf-8')
        before = self.snapshots()
        with self.assertRaisesRegex(EngineError, 'existing_bot_mismatch'):
            enroll(self.root)
        self.assertEqual(before, self.snapshots())

    def test_check_offline_never_calls_api_or_opens_database(self):
        self.configured()
        with patch('scripts.check_telegram_i2.TelegramAPI', side_effect=AssertionError('No API')):
            report = check(self.root)
        self.assertEqual(report['local_token'], 'passed')
        self.assertFalse(report['external_api_attempted'])
        self.assertFalse(report['database_opened'])
        self.assertEqual(report['live_acceptance'], 'blocked')
        self.assertEqual(report['participant_identity'], 'not_run')
        self.assertNotIn(FAKE_TOKEN, json.dumps(report))

    def test_incomplete_setup_blocks_live_api_without_loading_runtime_token(self):
        prepare(self.root)
        with patch('scripts.check_telegram_i2.load_telegram_token', side_effect=AssertionError('No token read')), \
                patch('scripts.check_telegram_i2.TelegramAPI', side_effect=AssertionError('No API')):
            report = check(self.root, allow_live=True)
        self.assertEqual(report['local_configuration'], 'blocked')
        self.assertFalse(report['external_api_attempted'])

    def test_live_preflight_is_real_only_when_enabled_and_not_message_acceptance(self):
        self.configured()
        with patch('scripts.check_telegram_i2.TelegramAPI') as api:
            api.return_value.call.side_effect = [{'id': 9009, 'is_bot': True}, {'url': ''}]
            report = check(self.root, allow_live=True)
        self.assertEqual([c.args[0] for c in api.return_value.call.call_args_list], ['getMe', 'getWebhookInfo'])
        self.assertEqual(report['getMe_and_getWebhookInfo'], 'passed')
        self.assertEqual(report['live_acceptance'], 'blocked')
        self.assertFalse(report['messages_sent'])
        self.assertNotIn(FAKE_TOKEN, json.dumps(report))
        self.assertNotIn('9009', json.dumps(report))

    def test_active_webhook_is_reported_without_url_or_deletion(self):
        self.configured()
        with patch('scripts.check_telegram_i2.TelegramAPI') as api:
            api.return_value.call.side_effect = [{'id': 9009, 'is_bot': True}, {'url': 'https://PRIVATE_WEBHOOK'}]
            report = check(self.root, allow_live=True)
        self.assertEqual(report['reason'], 'telegram_webhook_active')
        self.assertEqual(report['getMe_and_getWebhookInfo'], 'failed')
        self.assertNotIn('PRIVATE_WEBHOOK', json.dumps(report))
        self.assertEqual(api.return_value.call.call_count, 2)

    def api_updates(self):
        return [{'message': {'from': {'id': uid, 'is_bot': False},
                'chat': {'id': uid, 'type': 'private'}, 'text': '/start'}} for uid in (10101, 20202)]

    def api_response(self, method, parameters):
        if method == 'getMe':
            return {'id': 9009, 'is_bot': True, 'username': 'AlfredoVert2GoBot'}
        if method == 'getWebhookInfo':
            return {'url': ''}
        if method == 'getUpdates':
            return self.api_updates()
        raise AssertionError('No other API methods authorized in enrollment')

    def test_prompt_token_failures_have_exact_safe_codes(self):
        cases = {'empty': ('', 'telegram_token_input_empty'),
                 'control': ('\x16', 'telegram_token_input_control_characters'),
                 'whitespace': ('9009:XX XX', 'telegram_token_input_whitespace'),
                 'label': ('Token:9009:XXXX', 'telegram_token_input_format_invalid'),
                 'quote': ('"'+FAKE_TOKEN+'"', 'telegram_token_input_format_invalid'),
                 'url': ('https://api.telegram.org/bot'+FAKE_TOKEN, 'telegram_token_input_format_invalid'),
                 'short': ('9009:ABC', 'telegram_token_input_format_invalid')}
        for label, (value, code) in cases.items():
            with self.subTest(case=label), self.assertRaises(TelegramSecretsError) as error:
                validate_telegram_token(value, prompt=True)
            self.assertEqual(error.exception.code, code)
            self.assertEqual(error.exception.diagnostic['source'], 'hidden_prompt')
            self.assertNotIn(FAKE_TOKEN, str(error.exception))

    def test_prompt_retries_and_normalizes_only_boundary_whitespace(self):
        with patch('sys.stdin.isatty', return_value=True), \
                patch('getpass.getpass', side_effect=['', 'not-a-token', ' \t'+FAKE_TOKEN+'\r\n']), \
                redirect_stdout(self.stream):
            self.assertEqual(read_token(), FAKE_TOKEN)
        self.assertIn('telegram_token_input_empty', self.stream.getvalue())
        self.assertIn('telegram_token_input_format_invalid', self.stream.getvalue())
        self.assertNotIn(FAKE_TOKEN, self.stream.getvalue())

    def test_three_invalid_prompt_attempts_do_not_call_api_or_write_credentials(self):
        prepare(self.root)
        before = self.snapshots()
        with patch('sys.stdin.isatty', return_value=True), patch('getpass.getpass', return_value=''), \
                patch('scripts.setup_telegram_i2.TelegramAPI', side_effect=AssertionError('No API')), \
                redirect_stdout(self.stream):
            with self.assertRaisesRegex(TelegramSecretsError, 'telegram_token_input_empty'):
                enroll(self.root, discovery=True, allow_live=True)
        self.assertEqual(before, self.snapshots())

    def test_stored_token_is_not_silently_normalized_or_overwritten(self):
        self.configured()
        raw = read_yaml(self.root/'secrets.yaml')
        raw['telegram_bot_token'] = ' '+FAKE_TOKEN
        (self.root/'secrets.yaml').write_text(yaml.safe_dump(raw), encoding='utf-8')
        before = self.snapshots()
        with self.assertRaisesRegex(TelegramSecretsError, 'telegram_token_stored_whitespace'):
            enroll(self.root)
        self.assertEqual(before, self.snapshots())

    def test_secrets_schema_error_is_distinct_from_prompt_or_file_read(self):
        prepare(self.root)
        (self.root/'secrets.yaml').write_text('telegram_bot_token: null\n', encoding='utf-8')
        with self.assertRaisesRegex(TelegramSecretsError, 'telegram_secrets_schema_invalid'):
            load_enrollment_secrets(self.root/'secrets.yaml')

    def test_real_bot_id_range_and_runtime_prefix_match_remain_mandatory(self):
        for token, bot_id, code in ((str(2**52)+':'+'X'*30, None, 'telegram_token_bot_id_invalid'),
                                    (FAKE_TOKEN, 8008, 'telegram_token_bot_id_mismatch')):
            with self.assertRaisesRegex(TelegramSecretsError, code):
                validate_telegram_token(token, bot_id)

    def test_discovery_start_messages_complete_explicit_roles_after_token_saved(self):
        prepare(self.root)
        evidence = {}
        def response(method, parameters):
            if method == 'getUpdates':
                self.assertEqual(load_enrollment_secrets(self.root/'secrets.yaml')['telegram_bot_token'], FAKE_TOKEN)
                self.assertEqual(load_enrollment_config(self.root/'config.yaml')['channels']['telegram']['bot_id'], 9009)
            return self.api_response(method, parameters)
        with patch('sys.stdin.isatty', return_value=True), patch('getpass.getpass', return_value=FAKE_TOKEN), \
                patch('builtins.input', side_effect=['10101', '20202']), \
                patch('scripts.setup_telegram_i2.TelegramAPI') as api, redirect_stdout(self.stream):
            api.return_value.call.side_effect = response
            enroll(self.root, discovery=True, allow_live=True, expected_username='AlfredoVert2GoBot', evidence=evidence)
        self.assertEqual(evidence['stage'], 'enrollment_complete')
        self.assertEqual([c.args[0] for c in api.return_value.call.call_args_list], ['getMe','getWebhookInfo','getUpdates'])
        self.assertNotIn(FAKE_TOKEN, self.stream.getvalue())
        self.assertNotIn(FAKE_TOKEN, json.dumps(evidence))
        self.assertEqual([u.channel_user_id for u in load_config(self.root/'config.yaml').users], [10101,20202])

    def test_discovery_failure_preserves_registered_token_and_can_resume(self):
        prepare(self.root)
        with patch('sys.stdin.isatty', return_value=True), patch('getpass.getpass', return_value=FAKE_TOKEN), \
                patch('scripts.setup_telegram_i2.TelegramAPI') as api, redirect_stdout(self.stream):
            api.return_value.call.side_effect = lambda method, params: [] if method=='getUpdates' else self.api_response(method, params)
            with self.assertRaisesRegex(EngineError, 'telegram_private_participants_unavailable'):
                enroll(self.root, discovery=True, allow_live=True, expected_username='AlfredoVert2GoBot')
        stored = (self.root/'secrets.yaml').read_bytes()
        with patch('getpass.getpass', side_effect=AssertionError('Token already saved')), \
                patch('builtins.input', side_effect=['10101','20202']), \
                patch('scripts.setup_telegram_i2.TelegramAPI') as api, redirect_stdout(self.stream):
            api.return_value.call.side_effect = self.api_response
            enroll(self.root, discovery=True, allow_live=True, expected_username='AlfredoVert2GoBot')
        self.assertEqual(stored, (self.root/'secrets.yaml').read_bytes())

    def test_wrong_bot_username_is_rejected_before_any_token_write(self):
        prepare(self.root)
        before = self.snapshots()
        with patch('sys.stdin.isatty', return_value=True), patch('getpass.getpass', return_value=FAKE_TOKEN), \
                patch('scripts.setup_telegram_i2.TelegramAPI') as api:
            api.return_value.call.return_value = {'id':9009,'is_bot':True,'username':'AnotherBot'}
            with self.assertRaisesRegex(EngineError, 'telegram_bot_username_mismatch'):
                enroll(self.root, discovery=True, allow_live=True, expected_username='AlfredoVert2GoBot')
        self.assertEqual(before, self.snapshots())
        self.assertEqual(api.return_value.call.call_count, 1)

    def test_discovery_does_not_accept_unseen_id_as_participant(self):
        prepare(self.root)
        with patch('sys.stdin.isatty', return_value=True), patch('getpass.getpass', return_value=FAKE_TOKEN), \
                patch('builtins.input', return_value='30303'), \
                patch('scripts.setup_telegram_i2.TelegramAPI') as api, redirect_stdout(self.stream):
            api.return_value.call.side_effect = self.api_response
            with self.assertRaisesRegex(EngineError, 'participant_not_discovered'):
                enroll(self.root, discovery=True, allow_live=True)
        self.assertTrue(all(u['channel_user_id'] is None for u in read_yaml(self.root/'config.yaml')['users']))

    def test_token_only_never_polls_and_check_can_validate_bot_before_participants(self):
        prepare(self.root)
        with patch('sys.stdin.isatty', return_value=True), patch('getpass.getpass', return_value=FAKE_TOKEN), \
                patch('builtins.input', side_effect=AssertionError('No participant prompts')), \
                patch('scripts.setup_telegram_i2.TelegramAPI') as api, redirect_stdout(self.stream):
            api.return_value.call.side_effect = self.api_response
            enroll(self.root, discovery=True, allow_live=True, token_only=True, expected_username='AlfredoVert2GoBot')
        self.assertEqual([c.args[0] for c in api.return_value.call.call_args_list], ['getMe','getWebhookInfo'])
        with patch('scripts.check_telegram_i2.TelegramAPI') as api:
            api.return_value.call.side_effect = self.api_response
            report = check(self.root, allow_live=True, expected_username='AlfredoVert2GoBot')
        self.assertEqual(report['local_token'], 'passed')
        self.assertEqual(report['getMe_and_getWebhookInfo'], 'passed')
        self.assertEqual(report['reason'], 'telegram_enrollment_incomplete')
        self.assertEqual(len(report['missing_fields']), 2)

    def test_cli_records_failed_input_stage_without_token_or_provider_payload(self):
        prepare(self.root)
        (self.root/'docs'/'evidencias').mkdir(parents=True)
        with patch('scripts.setup_telegram_i2.ROOT', self.root), \
                patch('scripts.setup_telegram_i2.enroll', side_effect=TelegramSecretsError(
                    'telegram_token_input_empty', source='hidden_prompt', stage='token_input')), redirect_stdout(self.stream):
            self.assertEqual(main(['--discover','--allow-live-telegram']), 1)
        evidence = json.loads((self.root/'docs/evidencias/i2-enrollment.json').read_text(encoding='utf-8'))
        self.assertEqual(evidence['reason'], 'telegram_token_input_empty')
        self.assertEqual(evidence['diagnostic']['stage'], 'token_input')
        self.assertFalse(evidence['external_api_attempted'])
        self.assertFalse(evidence['token_saved'])

    def test_provider_rejection_is_a_distinct_stage_and_does_not_save_token(self):
        prepare(self.root)
        before = self.snapshots()
        evidence = {}
        with patch('sys.stdin.isatty', return_value=True), patch('getpass.getpass', return_value=FAKE_TOKEN), \
                patch('scripts.setup_telegram_i2.TelegramAPI') as api:
            api.return_value.call.side_effect = TelegramError('telegram_access_or_conflict')
            with self.assertRaisesRegex(EngineError, 'telegram_access_or_conflict'):
                enroll(self.root, discovery=True, allow_live=True, evidence=evidence)
        self.assertEqual(before, self.snapshots())
        self.assertEqual(evidence['stage'], 'getMe')
        self.assertTrue(evidence['external_api_attempted'])
        self.assertFalse(evidence.get('token_saved', False))

    def test_active_webhook_preserves_verified_token_without_deleting_webhook(self):
        prepare(self.root)
        with patch('sys.stdin.isatty', return_value=True), patch('getpass.getpass', return_value=FAKE_TOKEN), \
                patch('scripts.setup_telegram_i2.TelegramAPI') as api, redirect_stdout(self.stream):
            api.return_value.call.side_effect = [self.api_response('getMe', {}), {'url':'https://PRIVATE_WEBHOOK'}]
            with self.assertRaisesRegex(EngineError, 'telegram_webhook_active'):
                enroll(self.root, discovery=True, allow_live=True)
        self.assertEqual(load_enrollment_secrets(self.root/'secrets.yaml')['telegram_bot_token'], FAKE_TOKEN)
        self.assertEqual([c.args[0] for c in api.return_value.call.call_args_list], ['getMe','getWebhookInfo'])
        self.assertNotIn('PRIVATE_WEBHOOK', self.stream.getvalue())

    def test_discovery_rejects_groups_media_forwarded_and_malformed_text(self):
        import copy
        invalid = []
        for edit in (lambda msg: msg['chat'].update(type='group',id=-99),
                     lambda msg: msg.update(text=['FAKE_PRIVATE_CONTENT']),
                     lambda msg: msg.update(forward_origin={'type':'user'}),
                     lambda msg: msg['from'].update(is_bot=True)):
            entry = copy.deepcopy(self.api_updates()[0])
            edit(entry['message'])
            invalid.append(entry)
        api = MagicMock()
        api.call.return_value = invalid
        with self.assertRaisesRegex(EngineError, 'telegram_private_participants_unavailable'), redirect_stdout(self.stream):
            discover(api)
        self.assertNotIn('FAKE_PRIVATE_CONTENT', self.stream.getvalue())
