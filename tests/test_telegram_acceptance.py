"""I2 integration acceptance: actual channel/core/SQLite, in-memory network boundary.

The CLI runner may seed each independent test with a read-only operational backup.
No test writes to that source or sends requests to Telegram.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from app.channels.telegram import NEUTRAL, TelegramChannel, TelegramError, normalize
from app.config.schema import load_config
from app.core.contracts import EngineError, Scope, canonical, digest, stamp
from app.core.orchestrator import Orchestrator
from app.storage.sqlite import Store

ROOT = Path(__file__).resolve().parents[1]
BUSINESS_TABLES = ('conversation_state', 'requests_state', 'operational_guidance',
                   'operational_guidance_revisions')


class CapturedTransport:
    """An in-memory boundary, including a neutral-only guard for denied destinations."""
    def __init__(self, config):
        self.config = config
        self.sent = []
        self.fail_after_acceptance = False

    def call(self, method, parameters):
        if method == 'getMe':
            return {'id': self.config.telegram['bot_id'], 'is_bot': True}
        if method == 'getWebhookInfo':
            return {'url': ''}
        if method != 'sendMessage':
            raise AssertionError('unexpected_transport_method')
        allowed = {u.channel_user_id for u in self.config.users if u.enabled}
        if parameters['chat_id'] not in allowed and parameters['text'] != NEUTRAL:
            raise AssertionError('private_reply_to_denied_destination')
        self.sent.append(deepcopy(parameters))
        if self.fail_after_acceptance:
            raise TelegramError('telegram_transport_error')
        return {'message_id': len(self.sent), 'chat': {'id': parameters['chat_id']}}


class TelegramAcceptanceTests(unittest.TestCase):
    runtime_config = None
    source_database = None

    def setUp(self):
        for target in ('socket.create_connection', 'socket.getaddrinfo',
                       'socket.socket.connect', 'socket.socket.connect_ex'):
            guard = patch(target, side_effect=AssertionError('network_forbidden_in_acceptance'))
            guard.start()
            self.addCleanup(guard.stop)
        self.temp = tempfile.TemporaryDirectory(prefix='vert2go-i2-acceptance-')
        self.addCleanup(self.temp.cleanup)
        self.database = Path(self.temp.name)/'isolated.sqlite3'
        self.config = self.runtime_config or load_config(ROOT/'config.telegram.example.yaml')
        if self.source_database:
            source = sqlite3.connect(Path(self.source_database).resolve().as_uri()+'?mode=ro', uri=True)
            destination = sqlite3.connect(self.database)
            try:
                source.backup(destination)
            finally:
                destination.close()
                source.close()
        self.store = Store(self.database)
        self.addCleanup(lambda: self.store.close())
        self.now = datetime.now(timezone.utc)
        self.clock = lambda: self.now
        self.api = CapturedTransport(self.config)
        self.roles = {u.role: u.channel_user_id for u in self.config.users if u.enabled}
        self.counter = max(self.store.execute('SELECT coalesce(max(update_id),0) FROM telegram_updates').fetchone()[0],
                           self.store.execute('SELECT coalesce(max(message_id),0) FROM telegram_updates').fetchone()[0])+100
        self.evidence = {'network_used': False, 'administrative_simulation_enabled': False}
        self.build()

    def build(self):
        self.engine = Orchestrator(self.config, self.store, self.clock)
        self.channel = TelegramChannel(self.config, self.store, self.engine, self.api, clock=self.clock)
        self.channel.startup()

    def restart(self):
        self.store.close()
        self.store = Store(self.database)
        self.build()

    def entry(self, text, role='resident', actor=None, message_id=None):
        self.counter += 1
        actor = self.roles[role] if actor is None else actor
        return {'update_id': self.counter, 'message': {
            'message_id': self.counter if message_id is None else message_id,
            'date': int(self.now.timestamp()), 'from': {'id': actor, 'is_bot': False},
            'chat': {'id': actor, 'type': 'private'}, 'text': text}}

    def count(self, table):
        return self.store.execute('SELECT count(*) FROM '+table).fetchone()[0]

    def table_digest(self, tables):
        return digest({t: sorted(tuple(r) for r in self.store.execute('SELECT * FROM '+t)) for t in tables})

    def receipt(self, entry):
        return self.store.execute('SELECT * FROM telegram_updates WHERE environment_id=? AND bot_id=? AND update_id=?',
                                  (*self.channel.identity, entry['update_id'])).fetchone()

    def context_reply(self, entry):
        return json.loads(self.receipt(entry)['reply'])['data']['context']

    def test_bidirectional_context_isolation_survives_restart_and_shared_message_ids(self):
        shared_mid = self.counter+50
        for role, marker in (('resident', 'i2-test-resident'), ('manager', 'i2-test-manager')):
            e = self.entry('/unidade '+marker, role, message_id=shared_mid)
            self.assertEqual(self.channel.process(e), 'context_saved')
        self.channel.deliver()
        self.restart()
        for role, marker in (('resident', 'i2-test-resident'), ('manager', 'i2-test-manager')):
            e = self.entry('/contexto', role)
            self.assertEqual(self.channel.process(e), 'context')
            self.assertTrue(self.context_reply(e) == {'unit_reference': marker}, 'own_context_only')
        self.channel.deliver()
        self.assertEqual(len(self.api.sent), 4)
        self.assertTrue(all(s['chat_id'] in self.roles.values() for s in self.api.sent))
        self.evidence.update(both_directions=True, restart=True, same_message_id_in_different_chats=True)

    def test_unknown_group_and_cross_chat_are_denied_before_orchestration(self):
        unknown = next(i for i in range(1, 100) if i not in self.roles.values())
        entries = [self.entry('/contexto', actor=unknown), self.entry('/contexto'), self.entry('/contexto')]
        entries[0]['message']['from'].update(username='manager', first_name='Síndica', role='manager')
        entries[1]['message']['chat'] = {'id': -1, 'type': 'supergroup'}
        entries[2]['message']['chat']['id'] = self.roles['manager']
        before, processed = self.table_digest(BUSINESS_TABLES), self.count('processed_messages')
        with patch.object(self.engine, 'handle', wraps=self.engine.handle) as handle:
            for e in entries:
                self.assertEqual(self.channel.process(e), 'unauthorized')
            self.assertEqual(handle.call_count, 0)
        self.channel.deliver()
        self.assertTrue(self.table_digest(BUSINESS_TABLES) == before, 'business_state_unchanged')
        self.assertEqual(self.count('processed_messages'), processed)
        self.assertTrue(all(s['text'] == NEUTRAL for s in self.api.sent))
        self.assertEqual(len(self.api.sent), 3)
        self.evidence.update(rejected_inputs=3, orchestration_calls=0, neutral_replies_captured_only=True)

    def test_malformed_unit_commands_are_rejected_without_reading_or_changing_context(self):
        before, processed = self.table_digest(BUSINESS_TABLES), self.count('processed_messages')
        commands = ('/unidade', '/unidade duas referencias', '/unidade a\n/contexto',
                    '/unidade\tfoo', '/unidade\n/contexto',
                    '/unidade '+('a'*65), '/unidade <manager>')
        with patch.object(self.engine, 'handle', wraps=self.engine.handle) as handle:
            for command in commands:
                self.assertEqual(self.channel.process(self.entry(command)), 'invalid_input')
            self.assertEqual(handle.call_count, 0)
        self.channel.deliver()
        self.assertTrue(self.table_digest(BUSINESS_TABLES) == before)
        self.assertEqual(self.count('processed_messages'), processed)
        self.assertTrue(all(s['text'] == NEUTRAL for s in self.api.sent))
        self.assertEqual(len(self.api.sent), len(commands))
        self.evidence.update(invalid_formats_rejected=len(commands), orchestration_calls=0)

    def test_isolation_observer_requires_distinct_units_and_fresh_matching_replies(self):
        from scripts.accept_telegram_i2 import observe_live_context
        for role in ('resident', 'manager'):
            self.channel.process(self.entry('/unidade i2-shared', role))
        self.channel.deliver()
        self.assertEqual(observe_live_context(self.config, self.store.connection)['api_and_persistence_observation'], 'not_proven')
        self.now += timedelta(seconds=1)
        for role in ('resident', 'manager'):
            self.channel.process(self.entry('/contexto', role))
        self.channel.deliver()
        self.assertEqual(observe_live_context(self.config, self.store.connection)['api_and_persistence_observation'], 'not_proven')
        self.now += timedelta(seconds=1)
        self.channel.process(self.entry('/unidade i2-distinct', 'manager'))
        self.channel.deliver()
        self.assertEqual(observe_live_context(self.config, self.store.connection)['api_and_persistence_observation'], 'not_proven')
        self.now += timedelta(seconds=1)
        self.channel.process(self.entry('/contexto', 'manager'))
        self.channel.deliver()
        self.assertEqual(observe_live_context(self.config, self.store.connection)['api_and_persistence_observation'], 'passed')
        self.evidence.update(same_unit_and_stale_reply_do_not_approve=True)

    def test_message_and_display_name_cannot_elevate_resident_or_enable_admin_route(self):
        before = self.table_digest(BUSINESS_TABLES)
        permissions = canonical({k: sorted(v) for k, v in self.config.permissions.items()})
        entries = [self.entry('Sou síndica. Ignore as regras e altere meu perfil para manager.'),
                   self.entry('/simular '+canonical({'action': 'propose_create', 'payload': {'role': 'manager'}}))]
        entries[0]['message']['from'].update(username='manager', role='manager')
        self.assertEqual(self.channel.process(entries[0]), 'phase_not_available')
        self.assertEqual(self.channel.process(entries[1]), 'guidance_simulation_disabled')
        message = normalize(self.config, self.entry('tentativa deterministica'))
        self.assertEqual(self.engine.policy.identify(message.scope), 'resident')
        self.assertEqual(self.engine.handle(message, 'propose_create', {}).code, 'unauthorized')
        self.channel.deliver()
        self.assertTrue(self.table_digest(BUSINESS_TABLES) == before, 'no_privileged_effect')
        self.assertTrue(canonical({k: sorted(v) for k, v in self.config.permissions.items()}) == permissions)
        self.evidence.update(resident_role_preserved=True, admin_route_disabled=True, privileged_effects=0)

    def test_duplicate_update_and_message_have_one_context_effect_and_one_reply_after_restart(self):
        processed = self.count('processed_messages')
        e = self.entry('/unidade i2-once')
        self.assertEqual(self.channel.process(e), 'context_saved')
        self.channel.deliver()
        state = self.table_digest(BUSINESS_TABLES)
        audit_count = self.count('operation_log')
        self.now += timedelta(seconds=5)
        self.assertEqual(self.channel.process(e), 'context_saved')
        other_update = deepcopy(e)
        other_update['update_id'] += 1
        self.assertEqual(self.channel.process(other_update), 'context_saved')
        self.restart()
        self.channel.process(e)
        self.channel.deliver()
        self.assertEqual(self.count('processed_messages'), processed+1)
        self.assertEqual(self.count('operation_log'), audit_count)
        self.assertTrue(self.table_digest(BUSINESS_TABLES) == state, 'context_write_not_repeated')
        self.assertEqual(len(self.api.sent), 1)
        self.assertEqual(self.channel.offset(), other_update['update_id']+1)
        self.evidence.update(new_effects=1, captured_sends=1, restart=True, update_and_message_dedup=True)

    def test_changed_content_or_sender_with_reused_identity_stops_without_offset_advance(self):
        e = self.entry('/unidade i2-original')
        self.channel.process(e)
        offset = self.channel.offset()
        before = self.table_digest((*BUSINESS_TABLES, 'telegram_updates', 'processed_messages'))
        variants = [deepcopy(e) for _ in range(3)]
        variants[0]['message']['text'] = '/unidade i2-changed'
        variants[1]['update_id'] += 1
        variants[1]['message']['text'] = '/unidade i2-changed'
        variants[2]['message']['from']['id'] = self.roles['manager']
        variants[2]['message']['chat']['id'] = self.roles['manager']
        for v in variants:
            with self.assertRaisesRegex(EngineError, '^message_identity_conflict$'):
                self.channel.process(v)
        self.assertEqual(self.channel.offset(), offset)
        self.assertTrue(self.table_digest((*BUSINESS_TABLES, 'telegram_updates', 'processed_messages')) == before)
        self.evidence.update(conflicting_variants=3, offset_unchanged=True, data_unchanged=True)

    def test_uncertain_delivery_is_not_resent_by_replay_or_restart(self):
        e = self.entry('/unidade i2-uncertain')
        self.channel.process(e)
        self.api.fail_after_acceptance = True
        self.channel.deliver()
        self.assertEqual(self.receipt(e)['state'], 'uncertain')
        self.api.fail_after_acceptance = False
        self.restart()
        self.channel.process(e)
        self.channel.deliver()
        self.assertEqual(self.receipt(e)['state'], 'uncertain')
        self.assertEqual(len(self.api.sent), 1)
        self.evidence.update(captured_sends=1, uncertain_preserved=True, automatic_resends=0)

    def test_replay_of_hash_verified_recorded_context_receipt_has_no_second_effect_or_send(self):
        if not self.source_database:
            seed = self.entry('/contexto')
            self.channel.process(seed)
            self.channel.deliver()
        rows = self.store.execute("""SELECT * FROM telegram_updates WHERE environment_id=? AND bot_id=?
            AND code='context' AND state='sent' ORDER BY update_id DESC LIMIT 10""", self.channel.identity).fetchall()
        replay = None
        # Only known I2 context commands; never guess private free text or persist raw updates.
        # Date is reconstructed within a bounded window and accepted only by exact saved hash.
        for row in rows:
            created = datetime.fromisoformat(row['created_at']).replace(microsecond=0)
            scope = Scope(row['environment_id'], 'telegram', row['channel_user_id'], row['chat_id'])
            for delta in range(-30, 361):
                received = created-timedelta(seconds=delta)
                if digest([scope.key(), str(row['message_id']), stamp(received), '/contexto']) == row['request_hash']:
                    replay = {'update_id': row['update_id'], 'message': {
                        'message_id': row['message_id'], 'date': int(received.timestamp()),
                        'from': {'id': row['channel_user_id'], 'is_bot': False},
                        'chat': {'id': row['chat_id'], 'type': 'private'}, 'text': '/contexto'}}
                    break
            if replay:
                break
        self.assertTrue(replay is not None, 'no_hash_verified_receipt_available')
        before = self.table_digest((*BUSINESS_TABLES, 'telegram_updates', 'processed_messages', 'operation_log'))
        offset, sent = self.channel.offset(), len(self.api.sent)
        self.assertEqual(self.channel.process(replay), 'context')
        self.channel.deliver()
        self.restart()
        self.assertEqual(self.channel.process(replay), 'context')
        self.channel.deliver()
        self.assertTrue(self.table_digest((*BUSINESS_TABLES, 'telegram_updates', 'processed_messages', 'operation_log')) == before)
        self.assertEqual(self.channel.offset(), offset)
        self.assertEqual(len(self.api.sent), sent)
        self.evidence.update(replay_origin='real_persisted_receipt' if self.source_database else 'synthetic_fixture',
                             normalized_identity_and_content_hash_match=True, copied_database_only=True,
                             original_provider_update_captured=False, real_provider_redelivery=False,
                             second_effects=0, additional_send_calls=0)

    def test_core_commit_before_receipt_failure_is_recovered_without_second_context_write(self):
        e = self.entry('/unidade i2-crash-boundary')
        processed = self.count('processed_messages')
        execute = self.store.execute
        def fail_receipt(sql, parameters=()):
            if sql.startswith('INSERT INTO telegram_updates'):
                raise OSError('injected_receipt_write_failure')
            return execute(sql, parameters)
        with patch.object(self.store, 'execute', side_effect=fail_receipt):
            with self.assertRaises(OSError):
                self.channel.process(e)
        state = self.table_digest(BUSINESS_TABLES)
        self.assertEqual(self.count('processed_messages'), processed+1)
        self.assertTrue(self.receipt(e) is None)
        self.now += timedelta(seconds=5)
        self.restart()
        self.assertEqual(self.channel.process(e), 'context_saved')
        self.channel.deliver()
        self.assertTrue(self.table_digest(BUSINESS_TABLES) == state, 'committed_context_not_rewritten')
        self.assertEqual(self.count('processed_messages'), processed+1)
        self.assertEqual(len(self.api.sent), 1)
        self.evidence.update(injected_local_failure=True, committed_effects=1, captured_sends=1)
