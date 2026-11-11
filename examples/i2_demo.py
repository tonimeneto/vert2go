"""Fictional Telegram rehearsal, temporary database, no credentials or network."""
from datetime import datetime, timezone
from pathlib import Path
import json
import tempfile
from app.channels.telegram import TelegramChannel
from app.config.schema import load_config
from app.core.contracts import canonical
from app.core.orchestrator import Orchestrator
from app.storage.sqlite import Store

ROOT = Path(__file__).resolve().parents[1]


class FakeTelegram:
    def __init__(self):
        self.sent = []
        self.updates = []

    def call(self, method, parameters):
        if method == 'getMe':
            return {'id': 9009, 'is_bot': True}
        if method == 'getWebhookInfo':
            return {'url': ''}
        if method == 'getUpdates':
            updates, self.updates = self.updates, []
            return updates
        if method == 'sendMessage':
            self.sent.append(parameters)
            return {'message_id': len(self.sent), 'chat': {'id': parameters['chat_id']}}
        raise AssertionError('unexpected method')


def update(number, text, clock, actor=2002):
    return {'update_id': number, 'message': {'message_id': number, 'date': int(clock().timestamp()),
        'from': {'id': actor, 'is_bot': False, 'first_name': 'Fictício'},
        'chat': {'id': actor, 'type': 'private'}, 'text': text}}


def main():
    config = load_config(ROOT/'config.telegram.example.yaml')
    clock, api = lambda: datetime(2026, 11, 5, 15, tzinfo=timezone.utc), FakeTelegram()
    with tempfile.TemporaryDirectory(prefix='vert2go-i2-demo-') as folder:
        store = Store(Path(folder)/'demo.sqlite3')
        try:
            engine = Orchestrator(config, store, clock)
            channel = TelegramChannel(config, store, engine, api, simulate_guidance=True, clock=clock)
            channel.startup()
            for entry in (update(1, '/unidade ficticia-101', clock, 1001),
                          update(2, '/contexto', clock), update(3, '/contexto', clock, 1001)):
                channel.process(entry)
            proposal = update(4, '/simular '+canonical({'action': 'propose_create', 'payload': {
                'topic': 'fachada', 'content': 'Ensaio fictício: janelas fechadas.', 'audience': 'residents',
                'effective_from': '2026-11-05T12:00:00-03:00',
                'effective_until': '2026-11-05T18:00:00-03:00', 'timezone': 'America/Sao_Paulo'}}), clock)
            channel.process(proposal)
            data = json.loads(store.execute('SELECT reply FROM telegram_updates WHERE update_id=4').fetchone()[0])['data']
            confirm = update(5, '/simular '+canonical({'action': 'confirm', 'payload': {
                'explicit': True, 'operation_id': data['operation_id'], 'proposal_hash': data['proposal_hash']}}), clock)
            channel.process(confirm)
            channel.process(confirm)
            channel.deliver()
            result = {'phase': 'I2', 'network_used': False, 'offset': channel.offset(),
                'receipts': store.execute('SELECT count(*) FROM telegram_updates').fetchone()[0],
                'guidance_revisions': store.execute('SELECT count(*) FROM operational_guidance_revisions').fetchone()[0],
                'replies_sent_to_fake': len(api.sent), 'integrity_check': store.execute('PRAGMA integrity_check').fetchone()[0]}
            print(json.dumps(result))
        finally:
            store.close()


if __name__ == '__main__':
    main()
