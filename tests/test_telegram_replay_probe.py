import json
from unittest.mock import patch

from app.channels.telegram import TelegramChannel
from app.channels.telegram_replay_probe import ReceiptReplayProbe, effects_fingerprint
from app.core.orchestrator import Orchestrator
from app.main import main
from examples.i2_demo import FakeTelegram, update
from tests.support import EngineCase


class ReplayProbeTests(EngineCase):
    def setUp(self):
        super().setUp()
        for user in self.raw['users']:
            user['channel'] = 'telegram'
            user['chat_ids'] = [user['channel_user_id']]
        self.raw['channels'] = {'telegram': {'bot_id': 9009, 'poll_seconds': 25,
            'request_seconds': 35, 'batch_size': 100, 'retry_seconds': 5}}
        self.save_config()
        self.path = self.folder/'replay.json'
        self.probe = ReceiptReplayProbe(self.path)
        self.api = FakeTelegram()
        self.engine = Orchestrator(self.config, self.store, self.clock)
        self.channel = TelegramChannel(self.config, self.store, self.engine, self.api,
                                       clock=self.clock, receipt_observer=self.probe)
        self.channel.startup()

    def test_probe_runs_after_delivery_without_source_change_network_or_private_output(self):
        received = update(1, '/contexto', self.clock)
        received['message']['from']['first_name'] = 'PRIVATE_DISPLAY_NAME'
        self.api.updates = [received]
        observed = []
        def observer(channel, original):
            self.assertTrue(original is received)
            self.assertEqual(self.store.execute('SELECT state FROM telegram_updates').fetchone()[0], 'sent')
            before = effects_fingerprint(self.store)
            self.probe(channel, original)
            observed.append(effects_fingerprint(self.store) == before)
        self.channel.receipt_observer = observer
        self.channel.poll_once()
        report = json.loads(self.path.read_text(encoding='utf-8'))
        self.assertEqual(report['result'], 'passed')
        self.assertTrue(report['original_provider_update_in_memory'])
        self.assertTrue(report['canonical_input_hash_matches_receipt'])
        self.assertTrue(report['second_effects_absent'])
        self.assertTrue(report['offset_unchanged'])
        self.assertEqual(report['additional_send_calls'], 0)
        self.assertEqual(observed, [True])
        self.assertEqual(len(self.api.sent), 1)
        self.assertNotIn('PRIVATE_DISPLAY_NAME', self.path.read_text(encoding='utf-8'))
        self.assertNotIn('2002', self.path.read_text(encoding='utf-8'))

    def test_probe_is_once_only_and_skips_non_context_or_denied_inputs(self):
        self.api.updates = [update(1, '/ajuda', self.clock), update(2, '/contexto', self.clock, 9999)]
        self.channel.poll_once()
        self.assertFalse(self.path.exists())
        self.api.updates = [update(3, '/contexto', self.clock)]
        self.channel.poll_once()
        original_evidence = self.path.read_bytes()
        self.api.updates = [update(4, '/contexto', self.clock)]
        self.channel.poll_once()
        self.assertEqual(self.path.read_bytes(), original_evidence)

    def test_probe_failure_is_redacted_and_does_not_change_operational_state(self):
        received = update(1, '/contexto', self.clock)
        self.channel.process(received)
        self.channel.deliver()
        before = effects_fingerprint(self.store)
        with patch('app.channels.telegram_replay_probe.effects_fingerprint', side_effect=RuntimeError('PRIVATE_FAKE_ERROR')):
            self.probe(self.channel, received)
        report = json.loads(self.path.read_text(encoding='utf-8'))
        self.assertEqual(report['result'], 'failed')
        self.assertEqual(report['reason'], 'replay_probe_error')
        self.assertNotIn('PRIVATE_FAKE_ERROR', self.path.read_text(encoding='utf-8'))
        self.assertEqual(effects_fingerprint(self.store), before)

    def test_changed_input_cannot_pass_a_saved_receipt_hash(self):
        received = update(1, '/contexto', self.clock)
        self.channel.process(received)
        self.channel.deliver()
        before = effects_fingerprint(self.store)
        received['message']['text'] += ' '
        self.probe(self.channel, received)
        report = json.loads(self.path.read_text(encoding='utf-8'))
        self.assertEqual(report['result'], 'failed')
        self.assertFalse(report['canonical_input_hash_matches_receipt'])
        self.assertEqual(effects_fingerprint(self.store), before)

    def test_replay_cli_flag_without_telegram_cannot_read_secrets_or_open_store(self):
        with patch('app.main.load_telegram_token', side_effect=AssertionError('must_not_read')) as secret:
            with patch('app.main.Store', side_effect=AssertionError('must_not_open')) as storage:
                self.assertEqual(main(['--config', str(self.config_path), '--database', str(self.database),
                                       '--i2-replay-evidence']), 1)
        secret.assert_not_called()
        storage.assert_not_called()
