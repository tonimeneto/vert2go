from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
import http.client
import json
import sqlite3
from unittest.mock import patch, MagicMock

from app.channels.telegram import TelegramAPI, TelegramChannel, TelegramError, normalize
from app.config.schema import load_config, load_telegram_token
from app.core.contracts import EngineError, Scope, Result, canonical
from app.core.orchestrator import Orchestrator
from app.main import main
from app.storage.sqlite import Store, MIGRATION, APPLICATION_ID
from examples.i2_demo import FakeTelegram, update
from scripts.inspect_telegram_i2 import inspect as inspect_runtime
from tests.support import EngineCase, ROOT


class TelegramTests(EngineCase):
    def setUp(self):
        super().setUp()
        self.raw['environment_id'] = 'i2-fictional'
        for user in self.raw['users']:
            user['channel'] = 'telegram'
            user['chat_ids'] = [user['channel_user_id']]
        self.raw['channels'] = {'telegram': {'bot_id': 9009, 'poll_seconds': 25,
            'request_seconds': 35, 'batch_size': 100, 'retry_seconds': 5}}
        self.save_config()
        self.api = FakeTelegram()
        self.build()

    def build(self, simulation=True):
        self.engine = Orchestrator(self.config, self.store, self.clock)
        self.channel = TelegramChannel(self.config, self.store, self.engine, self.api,
                                       simulate_guidance=simulation, clock=self.clock)

    def entry(self, number=1, text='/contexto', actor=2002):
        return update(number, text, self.clock, actor)

    def state(self, number=1):
        return self.store.execute('SELECT state FROM telegram_updates WHERE update_id=?', (number,)).fetchone()[0]

    def simulation(self, number, action, payload, actor=2002):
        return self.entry(number, '/simular '+canonical({'action': action, 'payload': payload}), actor)

    def proposal(self, number=1, actor=2002):
        entry = self.simulation(number, 'propose_create', self.fields(), actor)
        code = self.channel.process(entry)
        if code != 'proposal':
            return code
        return json.loads(self.store.execute('SELECT reply FROM telegram_updates WHERE update_id=?',
                                            (number,)).fetchone()[0])['data']

    def confirm_entry(self, data, number=2):
        return self.simulation(number, 'confirm', {'explicit': True, 'operation_id': data['operation_id'],
                                                  'proposal_hash': data['proposal_hash']})

    def test_normalization_preserves_original_identity_date_and_ids(self):
        entry = self.entry()
        entry['message']['from']['username'] = 'manager'
        message = normalize(self.config, entry)
        self.assertEqual(message.scope, Scope('i2-fictional', 'telegram', 2002, 2002))
        self.assertEqual(message.update_id, '1')
        self.assertEqual(message.message_id, '1')
        self.assertEqual(message.received_at, self.clock())

    def test_unknown_group_and_spoofed_chat_denied_without_internal_reply(self):
        entries = [self.entry(1, actor=9999), self.entry(2), self.entry(3)]
        entries[1]['message']['chat'] = {'type': 'group', 'id': -99}
        entries[2]['message']['chat']['id'] = 1001
        for entry in entries:
            self.assertEqual(self.channel.process(entry), 'unauthorized')
        self.channel.deliver()
        self.assertEqual(len(self.api.sent), 3)
        self.assertEqual(len({reply['text'] for reply in self.api.sent}), 1)
        self.assertEqual(self.count('processed_messages'), 0)
        self.assertEqual(self.channel.offset(), 4)

    def test_only_text_no_download_or_media_interpretation(self):
        entry = self.entry()
        del entry['message']['text']
        entry['message']['voice'] = {'file_id': 'FAKE_PRIVATE_FILE'}
        self.assertEqual(self.channel.process(entry), 'telegram_text_only')
        self.channel.deliver()
        self.assertEqual(len(self.api.sent), 1)
        self.assertNotIn('FAKE_PRIVATE_FILE', self.api.sent[0]['text'])

    def test_edits_callbacks_forwarded_and_bot_messages_never_execute(self):
        entries = [self.entry(i) for i in range(1, 6)]
        entries[0]['edited_message'] = entries[0].pop('message')
        entries[1]['callback_query'] = entries[1].pop('message')
        entries[2]['message']['forward_origin'] = {'type': 'user'}
        entries[3]['message']['from']['is_bot'] = True
        entries[4]['message']['from']['id'] = True
        for entry in entries:
            self.channel.process(entry)
        self.assertEqual(self.count('processed_messages'), 0)
        self.assertEqual(self.channel.offset(), 6)

    def test_entry_limits_future_dates_and_invalid_dates(self):
        long = self.entry(1, 'x'*4097)
        future, invalid = self.entry(2), self.entry(3)
        future['message']['date'] += 60
        invalid['message']['date'] = 10**30
        self.assertEqual(self.channel.process(long), 'input_limit')
        self.assertEqual(self.channel.process(future), 'future_message')
        self.assertEqual(self.channel.process(invalid), 'telegram_update_invalid')

    def test_rate_limit_covers_help_unknown_text_and_simulation_commands(self):
        self.raw['limits']['messages_per_minute'] = 2
        self.save_config()
        self.build()
        self.channel.process(self.entry(1, '/ajuda'))
        self.channel.process(self.entry(2, 'texto livre'))
        self.assertEqual(self.proposal(3), 'rate_limit')
        self.assertEqual(self.count('requests_state'), 0)
        self.clock.advance(seconds=61)
        self.assertEqual(self.channel.process(self.entry(4)), 'context')

    def test_context_isolated_and_survives_restart(self):
        self.channel.process(self.entry(1, '/unidade ficticia-101', 1001))
        self.store.close()
        self.store = Store(self.database)
        self.build()
        self.channel.startup()
        self.channel.process(self.entry(2, '/contexto', 1001))
        self.channel.process(self.entry(3, '/contexto', 2002))
        rows = self.store.execute('SELECT reply FROM telegram_updates WHERE update_id IN (2,3) ORDER BY update_id').fetchall()
        self.assertIn('ficticia-101', rows[0][0])
        self.assertNotIn('ficticia-101', rows[1][0])
        self.assertEqual(self.channel.offset(), 4)

    def test_duplicate_update_and_message_id_have_one_effect_and_reply(self):
        data = self.proposal()
        entry = self.confirm_entry(data)
        self.assertEqual(self.channel.process(entry), 'confirmed')
        self.assertEqual(self.channel.process(entry), 'confirmed')
        duplicate = deepcopy(entry)
        duplicate['update_id'] = 3
        self.assertEqual(self.channel.process(duplicate), 'confirmed')
        self.channel.deliver()
        self.channel.deliver()
        self.assertEqual(self.count('operational_guidance_revisions'), 1)
        self.assertEqual(len(self.api.sent), 2)
        self.assertEqual(self.channel.offset(), 4)

    def test_conflicting_identity_stops_without_advancing(self):
        self.channel.process(self.entry())
        with self.assertRaisesRegex(EngineError, 'message_identity_conflict'):
            self.channel.process(self.entry(text='/unidade altered'))
        self.assertEqual(self.channel.offset(), 2)

    def test_resident_cannot_create_or_confirm_manager_guidance(self):
        self.assertEqual(self.proposal(actor=1001), 'unauthorized')
        data = self.proposal(2)
        entry = self.confirm_entry(data, 3)
        entry['message']['from']['id'] = 1001
        entry['message']['chat']['id'] = 1001
        self.assertEqual(self.channel.process(entry), 'operation_not_found')
        self.assertEqual(self.count('operational_guidance_revisions'), 0)

    def test_simulation_disabled_for_live_route_and_real_transport(self):
        self.build(simulation=False)
        self.assertEqual(self.proposal(), 'guidance_simulation_disabled')
        self.assertEqual(self.count('requests_state'), 0)
        with self.assertRaisesRegex(EngineError, 'offline_only'):
            TelegramChannel(self.config, self.store, self.engine, TelegramAPI('fake', 35), simulate_guidance=True)

    def test_crash_between_core_commit_and_channel_receipt_does_not_repeat_effect(self):
        data = self.proposal()
        entry = self.confirm_entry(data)
        execute = self.store.execute
        def crash(sql, parameters=()):
            if sql.startswith('INSERT INTO telegram_updates'):
                raise OSError('FAKE_SECRET_CRASH')
            return execute(sql, parameters)
        with patch.object(self.store, 'execute', side_effect=crash):
            with self.assertRaises(OSError):
                self.channel.process(entry)
        self.assertEqual(self.channel.offset(), 2)
        self.assertEqual(self.count('operational_guidance_revisions'), 1)
        self.store.close()
        self.store = Store(self.database)
        self.build()
        self.channel.startup()
        self.assertEqual(self.channel.process(entry), 'confirmed')
        self.assertEqual(self.count('operational_guidance_revisions'), 1)

    def test_storage_failure_does_not_acknowledge_update(self):
        with patch.object(self.engine, 'handle', return_value=Result('error','storage_error')):
            with self.assertRaisesRegex(EngineError, 'storage_error'):
                self.channel.process(self.entry())
        self.assertEqual(self.channel.offset(), 0)
        self.assertEqual(self.count('telegram_updates'), 0)

    def test_timeout_after_possible_send_is_uncertain_and_never_blindly_resent(self):
        self.channel.process(self.entry())
        call = self.api.call
        def timeout(method, parameters):
            result = call(method, parameters)
            if method == 'sendMessage':
                raise TelegramError('telegram_transport_error')
            return result
        with patch.object(self.api, 'call', side_effect=timeout):
            self.channel.deliver()
        self.assertEqual(self.state(), 'uncertain')
        self.channel.startup()
        self.channel.deliver()
        self.assertEqual(len(self.api.sent), 1)

    def test_connect_failure_keeps_unsent_reply_pending_until_safe_retry(self):
        self.channel.process(self.entry())
        with patch.object(self.api,'call',side_effect=TelegramError('telegram_transport_error',definitely_not_sent=True)):
            self.channel.deliver()
        self.assertEqual(self.state(),'pending');self.assertEqual(len(self.api.sent),0)
        self.channel.deliver();self.assertEqual(len(self.api.sent),0)
        self.clock.advance(seconds=self.config.telegram['retry_seconds']+1)
        self.channel.deliver();self.channel.deliver()
        self.assertEqual(self.state(),'sent');self.assertEqual(len(self.api.sent),1)

    def test_restart_in_sending_marks_uncertain_but_pending_is_delivered(self):
        self.channel.process(self.entry())
        self.channel.process(self.entry(2))
        self.store.execute("UPDATE telegram_updates SET state='sending' WHERE update_id=1")
        self.store.close()
        self.store = Store(self.database)
        self.build()
        self.channel.startup()
        self.channel.deliver()
        self.assertEqual(self.state(), 'uncertain')
        self.assertEqual(self.state(2), 'sent')
        self.assertEqual(len(self.api.sent), 1)

    def test_flood_control_defers_without_sleeping_or_sending_other_replies(self):
        self.channel.process(self.entry())
        self.channel.process(self.entry(2))
        with patch.object(self.api, 'call', side_effect=TelegramError('telegram_rate_limit', 31)) as call:
            self.channel.deliver()
            self.assertEqual(call.call_count, 1)
        self.assertEqual(self.state(), 'pending')
        self.channel.deliver()
        self.assertEqual(len(self.api.sent), 0)
        self.clock.advance(seconds=32)
        self.channel.deliver()
        self.assertEqual(self.state(), 'sent')

    def test_revocation_prevents_pending_reply_from_leaking_context(self):
        self.channel.process(self.entry())
        self.raw['users'][1]['channel_user_id'] = 3003
        self.raw['users'][1]['chat_ids'] = [3003]
        self.save_config()
        self.build()
        self.channel.deliver()
        self.assertEqual(self.api.sent, [])
        self.assertEqual(self.state(), 'discarded')

    def test_poll_uses_durable_offset_and_text_filter(self):
        self.channel.process(self.entry())
        calls = []
        def capture(method, params):
            calls.append((method, params))
            return [] if method == 'getUpdates' else {'message_id': 1, 'chat': {'id': params['chat_id']}}
        with patch.object(self.api, 'call', side_effect=capture):
            self.channel.poll_once()
        params = [p for method, p in calls if method == 'getUpdates'][0]
        self.assertEqual(params, {'offset': 2, 'timeout': 25, 'limit': 100, 'allowed_updates': ['message']})

    def test_malformed_or_unordered_batch_never_acknowledged(self):
        for batch in ([self.entry(2), self.entry(1)], [self.entry(), {'update_id': True}], {}):
            with patch.object(self.api, 'call', return_value=batch):
                with self.assertRaises(EngineError):
                    self.channel.poll_once()
            self.assertEqual(self.channel.offset(), 0)

    def test_webhook_or_wrong_bot_fails_without_mutating_provider(self):
        for method, value, code in [('getMe', {'id': 99, 'is_bot': True}, 'telegram_bot_mismatch'),
                                    ('getWebhookInfo', {'url': 'https://fake.example'}, 'telegram_webhook_active')]:
            original = self.api.call
            with patch.object(self.api, 'call', side_effect=lambda m,p: value if m == method else original(m,p)):
                with self.assertRaisesRegex(EngineError, code):
                    self.channel.startup()

    def test_live_gate_precedes_secret_read_database_and_network(self):
        target = self.folder/'not-created.sqlite3'
        with patch('app.main.load_telegram_token', side_effect=AssertionError('must not read')):
            with self.assertLogs(level='ERROR'):
                self.assertEqual(main(['--config', str(self.config_path), '--database', str(target), '--telegram']), 1)
        self.assertFalse(target.exists())

    def test_telegram_configuration_rejects_mixed_duplicate_ids_and_bad_limits(self):
        original = deepcopy(self.raw)
        for mutate in (lambda r: r['users'][0].update(channel='local'),
                       lambda r: r['users'][1].update(channel_user_id=1001, chat_ids=[1001]),
                       lambda r: r['users'][1].update(chat_ids=[2002,2003]),
                       lambda r: r['channels']['telegram'].update(request_seconds=20),
                       lambda r: r['channels']['telegram'].update(batch_size=101)):
            self.raw = deepcopy(original)
            mutate(self.raw)
            with self.assertRaises(EngineError):
                self.save_config()

    def test_token_schema_and_bot_match_without_echo(self):
        path = self.folder/'secret-test.yaml'
        for token in ('9009:'+'x'*30, '99:'+'x'*30, 'FAKE_SECRET', None):
            path.write_text('telegram_bot_token: '+(token or 'null')+'\nopenai_api_key: null\ngoogle_oauth: null\n', encoding='utf-8')
            if token and token.startswith('9009:'):
                self.assertEqual(load_telegram_token(path, 9009), token)
            else:
                with self.assertRaises(EngineError) as error:
                    load_telegram_token(path, 9009)
                self.assertNotIn('FAKE_SECRET', str(error.exception))

    def test_logs_and_audit_never_contain_raw_update_or_secret_text(self):
        marker = 'FAKE_SECRET_CONTENT_123'
        entry = self.entry(text=marker)
        with self.assertLogs('alfredo', level='INFO') as logs:
            self.channel.process(entry)
        self.assertNotIn(marker, ' '.join(logs.output))
        audit = [dict(row) for row in self.store.execute('SELECT * FROM operation_log')]
        self.assertNotIn(marker, json.dumps(audit))
        self.assertNotIn(marker, json.dumps([dict(r) for r in self.store.execute('SELECT * FROM telegram_updates')]))

    def test_known_i1_database_migration_preserves_context(self):
        path = self.folder/'v1.sqlite3'
        con = sqlite3.connect(path)
        con.executescript(MIGRATION.read_text(encoding='utf-8'))
        con.execute(f'PRAGMA application_id={APPLICATION_ID}')
        con.execute('PRAGMA user_version=1')
        con.execute("INSERT INTO conversation_state VALUES ('old','local',1,1,'context','{}','old','future')")
        con.commit()
        con.close()
        store = Store(path)
        try:
            self.assertEqual(store.execute('PRAGMA user_version').fetchone()[0], 2)
            self.assertEqual(store.execute('SELECT environment_id FROM conversation_state').fetchone()[0], 'old')
            store.verify()
        finally:
            store.close()

    def test_correction_cancellation_and_relevant_query_through_fake_channel(self):
        data = self.proposal()
        self.channel.process(self.confirm_entry(data))
        self.channel.process(self.simulation(3, 'find_guidance', {'topic':'fachada'}, actor=1001))
        self.assertIn('guidance', self.store.execute('SELECT reply FROM telegram_updates WHERE update_id=3').fetchone()[0])
        correction = {**self.fields(content='Correção fictícia'), 'guidance_id':data['guidance_id'], 'expected_version':1}
        self.assertEqual(self.channel.process(self.simulation(4, 'propose_correct', correction)), 'proposal')
        corrected = json.loads(self.store.execute('SELECT reply FROM telegram_updates WHERE update_id=4').fetchone()[0])['data']
        self.assertEqual(self.channel.process(self.confirm_entry(corrected, 5)), 'confirmed')
        cancel = {'guidance_id':data['guidance_id'], 'expected_version':2}
        self.assertEqual(self.channel.process(self.simulation(6, 'propose_cancel', cancel)), 'proposal')
        cancelled = json.loads(self.store.execute('SELECT reply FROM telegram_updates WHERE update_id=6').fetchone()[0])['data']
        self.assertEqual(self.channel.process(self.confirm_entry(cancelled, 7)), 'confirmed')
        self.assertEqual(self.count('operational_guidance_revisions'), 3)
        self.assertEqual(self.api.sent, [])  # No broadcast is generated by administrative changes.

    def test_failed_migration_rolls_back_and_tampered_v1_is_not_adopted(self):
        from app.storage.sqlite import TELEGRAM_MIGRATION
        for tampered in (False, True):
            path = self.folder/('bad-v1.sqlite3' if tampered else 'rollback-v1.sqlite3')
            con = sqlite3.connect(path)
            con.executescript(MIGRATION.read_text(encoding='utf-8'))
            con.execute(f'PRAGMA application_id={APPLICATION_ID}')
            con.execute('PRAGMA user_version=1')
            if tampered:
                con.execute('CREATE TABLE unexpected(value)')
            con.commit()
            con.close()
            migration = MagicMock()
            migration.read_text.return_value = TELEGRAM_MIGRATION.read_text(encoding='utf-8')+'\nINVALID SQL;'
            with patch('app.storage.sqlite.TELEGRAM_MIGRATION', migration):
                with self.assertRaises(EngineError if tampered else sqlite3.Error):
                    Store(path)
            con = sqlite3.connect(path)
            try:
                self.assertEqual(con.execute('PRAGMA user_version').fetchone()[0], 1)
                self.assertEqual(con.execute("SELECT count(*) FROM sqlite_master WHERE name='telegram_updates'").fetchone()[0], 0)
            finally:
                con.close()

    def test_denied_message_replay_and_revoked_cached_message_do_not_repeat(self):
        entry = self.entry(actor=9999)
        self.channel.process(entry)
        entry['update_id'] = 2
        self.assertEqual(self.channel.process(entry), 'unauthorized')
        known = self.entry(3)
        self.channel.process(known)
        self.raw['users'][1].update(channel_user_id=3003, chat_ids=[3003])
        self.save_config()
        self.build()
        known['update_id'] = 4
        self.assertEqual(self.channel.process(known), 'context')
        self.assertEqual(self.count('telegram_updates'), 2)
        self.channel.deliver()
        self.assertEqual(len(self.api.sent), 1)  # Only the constant neutral denial.

    def test_delayed_confirmation_keeps_original_timestamp_and_expires(self):
        data = self.proposal()
        self.clock.advance(seconds=self.config.limits['confirmation_seconds']+1)
        self.assertEqual(self.channel.process(self.confirm_entry(data)), 'confirmation_expired')
        self.assertEqual(self.count('operational_guidance_revisions'), 0)

    def test_pending_reply_older_than_retention_is_discarded(self):
        self.channel.process(self.entry())
        self.clock.advance(days=31)
        self.channel.deliver()
        self.assertEqual(self.state(), 'discarded')
        candidates = self.store.retention_candidates(self.config, self.clock())['telegram_updates']
        self.assertEqual(len(candidates), 1)
        self.store.execute("UPDATE telegram_updates SET state='uncertain'")
        self.assertEqual(self.store.retention_candidates(self.config, self.clock())['telegram_updates'], [])

    def test_poll_transient_error_waits_then_stops_and_auth_failure_exits(self):
        def stop_wait(seconds):
            self.assertEqual(seconds, 5)
            self.channel.stop.set()
        with patch.object(self.channel, 'poll_once', side_effect=TelegramError('telegram_transport_error')):
            with patch.object(self.channel.stop, 'wait', side_effect=stop_wait):
                self.channel.run()
        self.channel.stop.clear()
        with patch.object(self.channel, 'poll_once', side_effect=TelegramError('telegram_access_or_conflict')):
            with self.assertRaises(TelegramError):
                self.channel.run()

    def test_manual_cli_interrupt_closes_store_and_releases_lock(self):
        path = self.folder/'cli.sqlite3'
        with patch('app.main.load_telegram_token', return_value='9009:'+'x'*30):
            with patch('app.channels.telegram.TelegramChannel.run', side_effect=KeyboardInterrupt):
                self.assertEqual(main(['--config', str(self.config_path), '--database', str(path),
                                      '--telegram', '--allow-live-telegram']), 130)
        from app.main import instance_lock
        with instance_lock(path):
            reopened = Store(path)
            reopened.close()

    def test_control_receives_readiness_disconnect_and_recovery(self):
        states=[]
        self.channel.lifecycle_observer=lambda state,code:states.append((state,code))
        attempts=[]
        def poll():
            attempts.append(1)
            if len(attempts)==1:
                raise TelegramError('telegram_transport_error')
            self.channel.stop.set()
        with patch.object(self.channel,'poll_once',side_effect=poll), \
             patch.object(self.channel.stop,'wait',return_value=False):
            self.channel.run()
        self.assertEqual(states,[('ready',None),('unavailable','telegram_transport_error'),('ready',None)])

    def test_startup_transport_failure_retries_before_announcing_ready(self):
        states=[];self.channel.lifecycle_observer=lambda state,code:states.append((state,code))
        with patch.object(self.channel,'startup',side_effect=[TelegramError('telegram_transport_error'),None]) as startup, \
             patch.object(self.channel,'poll_once',side_effect=self.channel.stop.set), \
             patch.object(self.channel.stop,'wait',return_value=False):
            self.channel.run()
        self.assertEqual(startup.call_count,2)
        self.assertEqual(states,[('unavailable','telegram_transport_error'),('ready',None)])

    def test_stop_during_startup_retry_never_announces_active(self):
        states=[];self.channel.lifecycle_observer=lambda state,code:states.append((state,code))
        with patch.object(self.channel,'startup',side_effect=TelegramError('telegram_transport_error')), \
             patch.object(self.channel.stop,'wait',side_effect=lambda _:self.channel.stop.set()):self.channel.run()
        self.assertNotIn(('ready',None),states)

    def test_startup_authentication_error_is_not_retried(self):
        with patch.object(self.channel,'startup',side_effect=TelegramError('telegram_access_or_conflict')) as startup:
            with self.assertRaisesRegex(TelegramError,'telegram_access_or_conflict'):self.channel.run()
        self.assertEqual(startup.call_count,1)

    def test_main_control_uses_shared_stop_and_closes_canonical_store(self):
        from threading import Event
        from app.main import instance_lock
        stop=Event();states=[];path=self.folder/'controlled.sqlite3'
        observer=lambda state,code:states.append((state,code))
        def run(channel):
            self.assertIs(channel.stop,stop)
            self.assertIs(channel.lifecycle_observer,observer)
            channel.lifecycle_observer('ready',None)
            stop.set()
        with patch('app.main.load_telegram_token',return_value='9009:'+'x'*30), \
             patch('app.channels.telegram.TelegramChannel.run',new=run):
            result=main(['--config',str(self.config_path),'--database',str(path),'--telegram','--allow-live-telegram'],
                        stop_event=stop,lifecycle_observer=observer)
        self.assertEqual(result,0)
        self.assertEqual(states,[('starting',None),('ready',None)])
        with instance_lock(path):
            reopened=Store(path);reopened.close()

    def test_operational_events_cover_authorization_command_and_api_delivery_without_private_data(self):
        with self.assertLogs('alfredo', level='INFO') as logs:
            self.channel.startup()
            self.channel.process(self.entry(1, '/unidade FAKE_PRIVATE_UNIT'))
            self.channel.deliver()
        events = '\n'.join(logs.output)
        for event in ('telegram_starting','telegram_identity_verified','telegram_webhook_clear',
                      'telegram_update_received','telegram_sender_authorized role=manager',
                      'telegram_command_started command=unit','telegram_update_processed',
                      'telegram_reply_sending','telegram_reply_sent confirmation=api_accepted'):
            self.assertIn(event, events)
        self.assertNotIn('FAKE_PRIVATE_UNIT', events)
        self.assertNotIn('channel_user_id', events)

    def test_duplicate_event_does_not_trigger_another_api_send(self):
        entry = self.entry()
        self.channel.process(entry)
        self.channel.deliver()
        with self.assertLogs('alfredo', level='INFO') as logs:
            self.channel.process(entry)
            self.channel.deliver()
        self.assertIn('telegram_update_deduplicated', '\n'.join(logs.output))
        self.assertEqual(len(self.api.sent), 1)

    def test_runtime_inspection_of_missing_database_does_not_create_it(self):
        missing = self.folder/'missing.sqlite3'
        report = inspect_runtime(self.config, missing)
        self.assertFalse(missing.exists())
        self.assertEqual(report['reason'], 'telegram_database_not_created')
        self.assertFalse(report['external_api_attempted'])

    def test_runtime_inspection_redacts_and_preserves_operational_rows(self):
        self.channel.process(self.entry(1, '/unidade FAKE_PRIVATE_UNIT'))
        self.channel.process(self.entry(2, '/contexto'))
        self.channel.deliver()
        version = self.store.execute('PRAGMA data_version').fetchone()[0]
        report = inspect_runtime(self.config, self.database)
        self.assertEqual(version, self.store.execute('PRAGMA data_version').fetchone()[0])
        self.assertEqual(report['result'], 'passed')
        self.assertEqual(report['api_accepted_commands']['manager']['context'], 1)
        self.assertTrue(report['offset_covers_receipts'])
        self.assertEqual(report['delivery_states']['sent'], 2)
        self.assertNotIn('FAKE_PRIVATE_UNIT', json.dumps(report))
        self.assertNotIn('channel_user_id', json.dumps(report))
        self.assertEqual(report['live_acceptance'], 'blocked')

    def test_runtime_inspection_never_repairs_uncertain_delivery(self):
        self.channel.process(self.entry())
        self.store.execute("UPDATE telegram_updates SET state='uncertain'")
        report = inspect_runtime(self.config, self.database)
        self.assertEqual(report['delivery_states']['uncertain'], 1)
        self.assertEqual(self.state(), 'uncertain')
        self.assertEqual(self.api.sent, [])

    def test_empty_poll_emits_safe_heartbeat_without_sending(self):
        with self.assertLogs('alfredo', level='INFO') as logs:
            self.channel.poll_once()
        self.assertIn('telegram_poll_started', '\n'.join(logs.output))
        self.assertIn('telegram_poll_received updates=0', '\n'.join(logs.output))
        self.assertEqual(self.api.sent, [])

    def test_transient_poll_failure_emits_recovery_after_success(self):
        attempts = []
        def poll():
            attempts.append(1)
            if len(attempts) == 1:
                raise TelegramError('telegram_transport_error')
            self.channel.stop.set()
        with patch.object(self.channel, 'poll_once', side_effect=poll), \
                patch.object(self.channel.stop, 'wait', return_value=False), \
                self.assertLogs('alfredo', level='INFO') as logs:
            self.channel.run()
        self.assertIn('telegram_poll_recovered', '\n'.join(logs.output))
        self.assertEqual(len(attempts), 2)


class TransportTests(EngineCase):
    def test_successful_keepalive_connection_is_reused_and_closed_explicitly(self):
        connection=MagicMock();response=connection.getresponse.return_value
        response.status=200;response.will_close=False;response.read.return_value=b'{"ok":true,"result":{}}'
        api=TelegramAPI('9009:FAKE_SECRET',35)
        with patch('http.client.HTTPSConnection',return_value=connection) as make:
            api.call('getMe',{});api.call('getWebhookInfo',{})
        self.assertEqual(make.call_count,1);self.assertEqual(connection.connect.call_count,1)
        self.assertFalse(connection.close.called);api.close();self.assertTrue(connection.close.called)

    def test_connect_failure_proves_message_was_not_transmitted(self):
        connection=MagicMock();connection.connect.side_effect=TimeoutError('PRIVATE')
        with patch('http.client.HTTPSConnection',return_value=connection):
            with self.assertRaises(TelegramError) as error:TelegramAPI('9009:FAKE_SECRET',35).call('sendMessage',{})
        self.assertTrue(error.exception.definitely_not_sent);connection.request.assert_not_called()
        self.assertNotIn('PRIVATE',str(error.exception))

    def test_failure_after_request_never_claims_message_not_sent_or_retries(self):
        connection=MagicMock();connection.getresponse.side_effect=TimeoutError('PRIVATE')
        with patch('http.client.HTTPSConnection',return_value=connection):
            with self.assertRaises(TelegramError) as error:TelegramAPI('9009:FAKE_SECRET',35).call('sendMessage',{})
        self.assertFalse(error.exception.definitely_not_sent);self.assertEqual(connection.request.call_count,1)

    def test_server_closed_connection_is_reestablished_for_next_request(self):
        connection=MagicMock();response=connection.getresponse.return_value
        response.status=200;response.will_close=True;response.read.return_value=b'{"ok":true,"result":{}}'
        api=TelegramAPI('9009:FAKE_SECRET',35)
        with patch('http.client.HTTPSConnection',return_value=connection) as make:
            api.call('getMe',{});api.call('getWebhookInfo',{})
        self.assertEqual(make.call_count,2)
    def invoke(self, body, status=200):
        connection = MagicMock()
        connection.getresponse.return_value.status = status
        connection.getresponse.return_value.read.return_value = body
        with patch('http.client.HTTPSConnection', return_value=connection):
            result = TelegramAPI('9009:FAKE_SECRET', 35).call('getMe', {})
        self.assertTrue(connection.close.called)
        return result

    def test_tls_fixed_host_json_post_and_plain_success(self):
        self.assertEqual(self.invoke(b'{"ok":true,"result":{"id":9009}}'), {'id': 9009})

    def test_failures_are_sanitized_and_never_include_provider_description(self):
        for status, body in [(401, b'{"ok":false,"error_code":401,"description":"FAKE_SECRET"}'),
                             (409, b'{"ok":false,"error_code":409}'),
                             (500, b'{"ok":false}'), (302, b'FAKE_SECRET'),
                             (200, b'not json FAKE_SECRET'), (200, b'[]')]:
            with self.assertRaises(TelegramError) as error:
                self.invoke(body, status)
            self.assertNotIn('FAKE_SECRET', str(error.exception))

    def test_retry_after_and_response_size_are_bounded(self):
        with self.assertRaises(TelegramError) as error:
            self.invoke(b'{"error_code":429,"parameters":{"retry_after":15}}', 429)
        self.assertEqual(error.exception.retry_after, 15)
        with self.assertRaises(TelegramError):
            self.invoke(b'x'*(4*1024*1024+1))

    def test_network_failure_and_disallowed_methods_are_safe(self):
        connection = MagicMock()
        connection.request.side_effect = OSError('FAKE_SECRET')
        with patch('http.client.HTTPSConnection', return_value=connection):
            with self.assertRaises(TelegramError) as error:
                TelegramAPI('9009:FAKE_SECRET', 35).call('getUpdates', {})
            self.assertNotIn('FAKE_SECRET', str(error.exception))
        with self.assertRaisesRegex(TelegramError, 'method_denied'):
            TelegramAPI('fake', 35).call('deleteWebhook', {})
