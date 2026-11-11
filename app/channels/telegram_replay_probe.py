"""Opt-in I2 probe: replay one original live context update in SQLite memory copies.

No raw update is persisted. The operational connection is a backup source only;
all replay processing/delivery uses memory stores and a non-network sink.
"""
from datetime import datetime, timezone
import json
import logging
from app.core.contracts import EngineError, digest, stamp
from app.core.orchestrator import Orchestrator
from app.storage.sqlite import Store

LOG = logging.getLogger('alfredo')


class ReplaySink:
    def __init__(self, bot_id):
        self.bot_id, self.sends = bot_id, 0

    def call(self, method, parameters):
        if method == 'getMe':
            return {'id': self.bot_id, 'is_bot': True}
        if method == 'getWebhookInfo':
            return {'url': ''}
        if method == 'sendMessage':
            self.sends += 1
            return {'message_id': self.sends, 'chat': {'id': parameters['chat_id']}}
        raise EngineError('replay_probe_method_denied')


def effects_fingerprint(store):
    tables = ('conversation_state', 'requests_state', 'operational_guidance',
              'operational_guidance_revisions', 'processed_messages', 'operation_log', 'telegram_updates')
    return digest({t: sorted(tuple(r) for r in store.execute('SELECT * FROM '+t)) for t in tables})


class ReceiptReplayProbe:
    def __init__(self, evidence_path):
        self.path, self.done = evidence_path, False

    def __call__(self, channel, update):
        from app.channels.telegram import TelegramChannel, normalize
        if self.done:
            return
        try:
            message = normalize(channel.config, update)
            role = channel.engine.policy.identify(message.scope)
        except EngineError:
            return
        if message.text.strip() != '/contexto':
            return
        row = channel.store.execute("""SELECT * FROM telegram_updates WHERE environment_id=?
            AND bot_id=? AND update_id=? AND code='context' AND state='sent'""",
            (*channel.identity, update['update_id'])).fetchone()
        if row is None:
            return
        self.done = True
        report = {'phase': 'I2', 'scope': 'original_live_update_replayed_in_memory_copies',
            'updated_at': datetime.now(timezone.utc).isoformat(), 'result': 'failed',
            'original_provider_update_in_memory': True, 'incoming_role': role,
            'raw_update_persisted': False, 'participant_ids_published': False,
            'operational_database_write_attempted': False,
            'probe_external_api_attempted': False, 'probe_messages_sent_to_telegram': False,
            'live_acceptance': 'not_decided_by_this_probe'}
        copies = []
        try:
            expected = digest([message.scope.key(), message.message_id, stamp(message.received_at), message.text])
            report['canonical_input_hash_matches_receipt'] = expected == row['request_hash']
            sink = ReplaySink(channel.identity[1])
            clone = Store(':memory:')
            copies.append(clone)
            channel.store.connection.backup(clone.connection)
            clone.verify()
            before = effects_fingerprint(clone)
            expected_offset = channel.offset()
            unchanged, offsets = True, True
            for attempt in range(2):
                if attempt:
                    reopened = Store(':memory:')
                    copies.append(reopened)
                    clone.connection.backup(reopened.connection)
                    clone = reopened
                engine = Orchestrator(channel.config, clone, channel.clock)
                replay = TelegramChannel(channel.config, clone, engine, sink, clock=channel.clock)
                replay.startup()
                replay.process(update)
                replay.deliver()
                unchanged = unchanged and effects_fingerprint(clone) == before
                offsets = offsets and replay.offset() == expected_offset
            report.update(replay_attempts=2, second_effects_absent=unchanged,
                          offset_unchanged=offsets, additional_send_calls=sink.sends,
                          memory_store_reopen_exercised=True)
            if report['canonical_input_hash_matches_receipt'] and unchanged and offsets and sink.sends == 0:
                report['result'] = 'passed'
        except Exception:
            # Probe failure never publishes provider data or interrupts the real consumer.
            report['reason'] = 'replay_probe_error'
        finally:
            for clone in copies:
                clone.close()
        try:
            self.path.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        except OSError:
            LOG.error('telegram_i2_replay_probe result=evidence_write_failed')
        else:
            LOG.info('telegram_i2_replay_probe result=%s', report['result'])
