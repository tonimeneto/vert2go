from pathlib import Path
from unittest.mock import patch
import yaml
from app.config.schema import load_config, validate_secrets
from app.core.contracts import EngineError, relative_day_interval
from tests.support import EngineCase


class ConfigurationTests(EngineCase):
    def assert_bad(self, raw=None, text=None):
        self.config_path.write_text(text if text is not None else yaml.safe_dump(raw),encoding='utf-8')
        with self.assertRaises(EngineError) as captured:
            load_config(self.config_path)
        self.assertNotIn('FAKE_SECRET',str(captured.exception))

    def test_valid_yaml_and_immutable_permissions(self):
        self.assertEqual(self.config.environment_id,'i1-fictional')
        with self.assertRaises(TypeError):
            self.config.permissions['resident'] = {'guidance.create'}

    def test_invalid_yaml_is_sanitized(self):
        self.assert_bad(text='openai: [FAKE_SECRET')

    def test_missing_required_field(self):
        del self.raw['users']
        self.assert_bad(self.raw)

    def test_unknown_field_rejected(self):
        self.raw['api_key']='FAKE_SECRET'
        self.assert_bad(self.raw)

    def test_missing_secrets_allowed(self):
        validate_secrets(self.folder/'absent.yaml')
        validate_secrets()

    def test_empty_secrets_example_allowed(self):
        path=self.folder/'secrets.yaml'
        path.write_text('telegram_bot_token: null\nopenai_api_key: null\ngoogle_oauth: null\n',encoding='utf-8')
        validate_secrets(path)

    def test_real_secrets_rejected_without_echo(self):
        path=self.folder/'secrets.yaml'
        path.write_text('telegram_bot_token: FAKE_SECRET\nopenai_api_key: null\ngoogle_oauth: null\n',encoding='utf-8')
        with self.assertRaises(EngineError) as error:
            validate_secrets(path)
        self.assertNotIn('FAKE_SECRET',str(error.exception))

    def test_simulation_mandatory(self):
        self.raw['simulation_mode']=False
        self.assert_bad(self.raw)

    def test_timezone_mandatory(self):
        self.raw['timezone']='UTC'
        self.assert_bad(self.raw)

    def test_missing_zone_database_safe_error(self):
        from zoneinfo import ZoneInfoNotFoundError
        with patch('app.config.schema.ZoneInfo',side_effect=ZoneInfoNotFoundError()):
            with self.assertRaisesRegex(EngineError,'timezone_data_missing'):
                load_config(self.config_path)

    def test_duplicate_keys_rejected(self):
        self.assert_bad(text='environment_id: a\nenvironment_id: b\n')

    def test_unsafe_yaml_tag_rejected(self):
        self.assert_bad(text='!!python/object/apply:os.system [FAKE_SECRET]')

    def test_alias_recursion_rejected(self):
        self.assert_bad(text='data: &x [*x]')

    def test_boolean_user_id_rejected(self):
        self.raw['users'][0]['channel_user_id']=True
        self.assert_bad(self.raw)

    def test_duplicate_users_rejected(self):
        self.raw['users'][1]['channel_user_id']=1001
        self.assert_bad(self.raw)

    def test_resident_cannot_gain_capability_in_yaml(self):
        self.raw['permissions']['resident'].append('guidance.create')
        self.assert_bad(self.raw)

    def test_wrong_numeric_types(self):
        self.raw['limits']['confirmation_seconds']='300'
        self.assert_bad(self.raw)

    def test_retention_cannot_be_shortened(self):
        self.raw['retention']['audit_days']=10
        self.assert_bad(self.raw)

    def test_nonfinite_budget_rejected(self):
        self.raw['openai']['monthly_budget_brl']='NaN'
        self.assert_bad(self.raw)

    def test_relative_day_uses_original_message(self):
        start,end=relative_day_interval('2026-11-06T01:00:00+00:00',0,'09:00','18:00')
        self.assertEqual(start[:10],'2026-11-05')
        self.assertEqual(end,'2026-11-05T21:00:00.000000+00:00')

    def test_relative_day_requires_explicit_end(self):
        with self.assertRaises(EngineError):
            relative_day_interval(self.clock(),0,'09:00',None)

    def test_offsetless_times_rejected(self):
        result=self.propose(effective_from='2026-11-05T09:00:00')
        self.assertEqual(result.code,'invalid_datetime')

    def test_malformed_role_and_nested_input_types_rejected(self):
        self.raw['users'][0]['role']={'invalid':'resident'}
        self.assert_bad(self.raw)

    def test_nonserializable_and_nonfinite_structured_payload_rejected(self):
        for payload in ({'topic':float('nan')},{'topic':object()},{1:'mixed','topic':'fachada'}):
            self.assertEqual(self.engine.handle(self.msg(),'find_guidance',payload).code,'invalid_input')

    def test_confirmation_summary_identifies_actor_chat_and_original_time(self):
        proposal=self.propose()
        self.assertEqual(proposal.data['scope'],list(self.manager.key()))
        self.assertTrue(proposal.data['original_message_at'].startswith('2026-11-05'))
