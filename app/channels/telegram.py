"""Text-only Telegram polling, durable receipts and conservative reply delivery."""
from datetime import datetime, timedelta, timezone
import http.client
import json
import logging
import re
import ssl
import time
from threading import Event
from uuid import NAMESPACE_URL, uuid5

from app.core.contracts import EngineError, Message, Scope, canonical, digest, stamp, utcnow
from app.channels.telegram_connection import connect_telegram

LOG = logging.getLogger('alfredo')
HELP = ('Alfredo experimental — canal de teste I2. Comandos: /ajuda, /contexto, '
        '/unidade REFERENCIA. Interpretação natural e operações externas dependem das próximas fases.')
NEUTRAL = 'Não foi possível atender esta mensagem neste canal de teste.'


class TelegramError(EngineError):
    def __init__(self, code, retry_after=0):
        super().__init__(code)
        self.retry_after = retry_after


class TelegramAPI:
    """Fixed TLS host, no redirects, payload/URL diagnostics or automatic retries."""
    def __init__(self, token, request_seconds):
        self._token = token
        self.request_seconds = request_seconds

    def call(self, method, parameters):
        if method not in ('getMe', 'getWebhookInfo', 'getUpdates', 'sendMessage'):
            raise TelegramError('telegram_method_denied')
        connection = http.client.HTTPSConnection('api.telegram.org', timeout=self.request_seconds,
                                                context=ssl.create_default_context())
        connection._create_connection = connect_telegram
        started = time.perf_counter()
        try:
            connection.request('POST', '/bot' + self._token + '/' + method,
                               body=canonical(parameters).encode('utf-8'),
                               headers={'Content-Type': 'application/json'})
            response = connection.getresponse()
            body = response.read(4 * 1024 * 1024 + 1)
            if len(body) > 4 * 1024 * 1024:
                raise TelegramError('telegram_response_invalid')
            data = json.loads(body)
            if type(data) is not dict:
                raise TelegramError('telegram_response_invalid')
            if response.status == 429 or data.get('error_code') == 429:
                params = data.get('parameters')
                delay = params.get('retry_after') if type(params) is dict else None
                if type(delay) is not int or not 1 <= delay <= 86400:
                    raise TelegramError('telegram_response_invalid')
                raise TelegramError('telegram_rate_limit', delay)
            if response.status in (401, 403, 409) or data.get('error_code') in (401, 403, 409):
                raise TelegramError('telegram_access_or_conflict')
            if response.status != 200 or data.get('ok') is not True or 'result' not in data:
                # A server error may follow acceptance of sendMessage: outcome uncertain.
                raise TelegramError('telegram_result_uncertain')
            return data['result']
        except (OSError, http.client.HTTPException, ValueError, RecursionError):
            raise TelegramError('telegram_transport_error') from None
        finally:
            connection.close()
            LOG.info('telegram_http_finished method=%s elapsed_ms=%d', method,
                     round((time.perf_counter()-started)*1000))


def normalize(config, update):
    """Never derive identity from username, text, forwarded author or supplied role."""
    if type(update) is not dict or type(update.get('update_id')) is not int or not 0 <= update['update_id'] < 2**63-1:
        raise EngineError('telegram_update_invalid')
    raw = update.get('message')
    if type(raw) is not dict:
        raise EngineError('telegram_update_unsupported')
    sender, chat = raw.get('from'), raw.get('chat')
    if type(sender) is not dict or type(chat) is not dict:
        raise EngineError('telegram_update_invalid')
    if (type(sender.get('id')) is not int or not 0 < sender['id'] < 2**52 or sender.get('is_bot') is not False
            or type(chat.get('id')) is not int or not 0 < abs(chat['id']) < 2**52
            or type(raw.get('message_id')) is not int or not 0 < raw['message_id'] < 2**52
            or type(raw.get('date')) is not int or raw['date'] <= 0):
        raise EngineError('telegram_update_invalid')
    if chat.get('type') != 'private' or chat['id'] != sender['id']:
        raise EngineError('unauthorized')
    if any(key in raw for key in ('forward_origin', 'forward_date', 'sender_chat', 'business_connection_id')):
        raise EngineError('telegram_update_unsupported')
    if type(raw.get('text')) is not str or not raw['text'].strip():
        raise EngineError('telegram_text_only')
    if len(raw['text']) > min(4096, config.limits['max_message_chars']):
        raise EngineError('input_limit')
    try:
        received = datetime.fromtimestamp(raw['date'], timezone.utc)
    except (OverflowError, OSError, ValueError):
        raise EngineError('telegram_update_invalid') from None
    return Message(Scope(config.environment_id, 'telegram', sender['id'], chat['id']),
                   str(raw['message_id']), received, 'telegram_' + str(update['update_id']),
                   raw['text'], str(update['update_id']))


class TelegramChannel:
    def __init__(self, config, store, engine, api, *, simulate_guidance=False, clock=utcnow,
                 receipt_observer=None):
        if not config.telegram:
            raise EngineError('telegram_not_configured')
        # Simulation is only available with an injected fake API, never the real transport.
        if simulate_guidance and isinstance(api, TelegramAPI):
            raise EngineError('guidance_simulation_offline_only')
        self.config, self.store, self.engine, self.api = config, store, engine, api
        self.clock, self.simulate_guidance = clock, simulate_guidance
        self.receipt_observer = receipt_observer
        self.lifecycle_observer = None
        self.identity = (config.environment_id, config.telegram['bot_id'])
        self.stop = Event()

    def startup(self):
        LOG.info('telegram_starting')
        self.engine.startup()
        with self.store.transaction():
            recovered = self.store.execute("""UPDATE telegram_updates SET state='uncertain',updated_at=?
                WHERE environment_id=? AND bot_id=? AND state='sending'""", (stamp(self.clock()), *self.identity))
        LOG.info('telegram_delivery_recovered uncertain=%d', recovered.rowcount)
        me = self.api.call('getMe', {})
        if type(me) is not dict or me.get('id') != self.identity[1] or me.get('is_bot') is not True:
            raise EngineError('telegram_bot_mismatch')
        LOG.info('telegram_identity_verified')
        webhook = self.api.call('getWebhookInfo', {})
        if type(webhook) is not dict or webhook.get('url') != '':
            raise EngineError('telegram_webhook_active')
        LOG.info('telegram_webhook_clear')

    def offset(self):
        row = self.store.execute('SELECT next_offset FROM telegram_poll_state WHERE environment_id=? AND bot_id=?',
                                 self.identity).fetchone()
        return row[0] if row else 0

    def _advance(self, update_id):
        self.store.execute("""INSERT INTO telegram_poll_state VALUES (?,?,?,?) ON CONFLICT(environment_id,bot_id)
            DO UPDATE SET next_offset=max(next_offset,excluded.next_offset),updated_at=excluded.updated_at""",
                           (*self.identity, update_id + 1, stamp(self.clock())))

    def _route(self, message):
        text = message.text.strip()
        command = ('help' if text in ('/start', '/ajuda', '/help') else 'context' if text == '/contexto'
                   else 'unit' if re.fullmatch(r'/unidade [a-zA-Z0-9_-]{1,64}', text)
                   else 'simulation' if text.startswith('/simular ') else 'unsupported')
        LOG.info('telegram_command_started command=%s', command)
        if text in ('/start', '/ajuda', '/help'):
            action, payload = 'get_context', {}
        elif text == '/contexto':
            action, payload = 'get_context', {}
        elif re.fullmatch(r'/unidade [a-zA-Z0-9_-]{1,64}', text):
            action, payload = 'set_context', {'context': {'unit_reference': text.split()[1]}}
        elif re.match(r'/unidade(?:\s|$)', text):
            return 'invalid_input', NEUTRAL
        elif text.startswith('/simular '):
            if not self.simulate_guidance:
                return 'guidance_simulation_disabled', 'Simulação administrativa disponível apenas no ensaio local autorizado.'
            try:
                command = json.loads(text[9:])
                if type(command) is not dict or set(command) != {'action', 'payload'}:
                    raise ValueError
                action, payload = command['action'], command['payload']
                if action not in ('propose_create', 'propose_correct', 'propose_cancel', 'confirm',
                                   'find_guidance', 'guidance_history') or type(payload) is not dict:
                    raise ValueError
                if action.startswith('propose_'):
                    stable = str(uuid5(NAMESPACE_URL, canonical([message.scope.key(), message.message_id])))
                    payload = {**payload, 'operation_id': stable, 'idempotency_key': stable}
            except (ValueError, TypeError, RecursionError):
                return 'invalid_input', NEUTRAL
        else:
            action, payload = ('query_documents' if self.engine.knowledge is not None and not text.startswith('/')
                               else 'get_context'), {}
        result = self.engine.handle(message, action, payload)
        if result.code == 'storage_error':
            raise EngineError('storage_error')
        if result.status == 'rejected':
            return result.code, NEUTRAL
        if action == 'query_documents':
            return result.code, result.data.get('reply', 'Não foi possível verificar a regra documental.')
        if text in ('/start', '/ajuda', '/help'):
            if self.engine.knowledge is not None:
                return 'help', ('Alfredo experimental — consulta documental I4. Pergunte em linguagem natural sobre '
                                'os documentos autorizados. Comandos: /ajuda, /contexto, /unidade REFERENCIA. '
                                'Reservas e alterações administrativas não estão habilitadas.')
            return 'help', HELP
        if text == '/contexto' or text.startswith('/unidade ') or text.startswith('/simular '):
            rendered = canonical(result.as_dict())
            if len(rendered.encode('utf-16-le')) // 2 > 4096:
                rendered = 'Resultado excede o limite do canal; consulte o ensaio local protegido.'
            return result.code, rendered
        return 'phase_not_available', HELP

    def process(self, update):
        if type(update) is not dict or type(update.get('update_id')) is not int or not 0 <= update['update_id'] < 2**63-1:
            raise EngineError('telegram_update_invalid')
        uid, now = update['update_id'], self.clock()
        LOG.info('telegram_update_received')
        # Message hash deliberately excludes mutable display names and irrelevant metadata.
        message = None
        try:
            message = normalize(self.config, update)
            fingerprint = digest([message.scope.key(), message.message_id, stamp(message.received_at), message.text])
            role = self.engine.policy.identify(message.scope)
            LOG.info('telegram_sender_authorized role=%s', role)
        except EngineError as error:
            code = error.code
            LOG.info('telegram_input_rejected code=%s', code)
            if message is None:
                fingerprint = None
        else:
            code = None
        raw = update.get('message') if type(update.get('message')) is dict else {}
        chat = raw.get('chat') if type(raw.get('chat')) is dict else {}
        sender = raw.get('from') if type(raw.get('from')) is dict else {}
        safe_int = lambda value: value if type(value) is int and -(2**63) < value < 2**63 else 0
        chat_id, mid, actor = safe_int(chat.get('id')), safe_int(raw.get('message_id')), safe_int(sender.get('id'))
        # Non-message updates use a unique negative synthetic identity, not (0,0).
        if not chat_id or mid <= 0:
            chat_id, mid = 0, -(uid + 1)
        if fingerprint is None:
            fingerprint = digest({'rejected_identity': [actor, chat_id, mid]})
        existing = self.store.execute("""SELECT * FROM telegram_updates WHERE environment_id=? AND bot_id=?
            AND (update_id=? OR (chat_id=? AND message_id=?))""", (*self.identity, uid, chat_id, mid)).fetchone()
        if existing:
            if existing['request_hash'] != fingerprint:
                raise EngineError('message_identity_conflict')
            with self.store.transaction():
                self._advance(uid)
            LOG.info('telegram_update_deduplicated')
            return existing['code']
        reply = NEUTRAL if chat_id else None
        count = self.store.execute("""SELECT count(*) FROM telegram_updates WHERE environment_id=? AND bot_id=?
            AND channel_user_id=? AND chat_id=? AND created_at>?""",
            (*self.identity, actor, chat_id, stamp(now-timedelta(minutes=1)))).fetchone()[0]
        if count >= self.config.limits['messages_per_minute']:
            code, reply = 'rate_limit', None
        if code is None:
            if message.received_at > now + timedelta(seconds=30):
                code = 'future_message'
            elif message.received_at <= now-timedelta(days=self.config.retention['deduplication_days']):
                code = 'message_expired'
            else:
                code, reply = self._route(message)
        if code in ('telegram_update_invalid', 'telegram_update_unsupported'):
            reply = None
        with self.store.transaction():
            self.store.execute('INSERT INTO telegram_updates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (*self.identity, uid, actor, chat_id, mid, fingerprint, code, reply,
                 'pending' if reply else 'discarded', stamp(now), stamp(now), stamp(now)))
            self._advance(uid)
            audit = message or Message(Scope(self.identity[0], 'telegram', actor, chat_id), str(mid), now, 'tg_'+str(uid))
            role = 'unknown'
            try:
                role = self.engine.policy.identify(audit.scope)
            except EngineError:
                pass
            self.store.audit(audit, role, 'telegram.receive', 'success' if code in ('help','context','context_saved')
                             else 'processed', now, safe_error=None if reply else code)
        LOG.info('telegram_update_processed code=%s', code)
        return code

    def deliver(self):
        # A Telegram flood limit affects the bot, including replies to other chats.
        deferred = self.store.execute("""SELECT max(next_attempt_at) FROM telegram_updates
            WHERE environment_id=? AND bot_id=? AND state='pending'""", self.identity).fetchone()[0]
        if deferred and deferred > stamp(self.clock()):
            LOG.info('telegram_delivery_deferred')
            return
        rows = self.store.execute("""SELECT * FROM telegram_updates WHERE environment_id=? AND bot_id=?
            AND state='pending' AND next_attempt_at<=? ORDER BY created_at,update_id LIMIT ?""",
            (*self.identity, stamp(self.clock()), self.config.telegram['batch_size'])).fetchall()
        for row in rows:
            if self.stop.is_set():
                break
            key = (*self.identity, row['update_id'])
            # Authorization can have changed since receipt/restart.
            if row['created_at'] <= stamp(self.clock()-timedelta(days=self.config.retention['conversation_days'])):
                self._delivery_state(key, 'discarded')
                LOG.info('telegram_reply_discarded code=retention_expired')
                continue
            try:
                self.engine.policy.identify(Scope(self.identity[0], 'telegram', row['channel_user_id'], row['chat_id']))
            except EngineError:
                # Only a constant neutral rejection can be sent to a denied source.
                if row['reply'] != NEUTRAL:
                    self._delivery_state(key, 'discarded')
                    LOG.info('telegram_reply_discarded code=authorization_changed')
                    continue
            reply = row['reply']
            if row['code'].startswith('knowledge_') and reply != NEUTRAL:
                try:
                    if self.engine.knowledge is None:
                        raise EngineError('knowledge_not_enabled')
                    scope = Scope(self.identity[0],'telegram',row['channel_user_id'],row['chat_id'])
                    self.engine.knowledge.validate_delivery(scope,str(row['message_id']),reply,
                                                           has_evidence=row['code'] == 'knowledge_answer')
                except EngineError:
                    reply = NEUTRAL
                    with self.store.transaction():
                        self.store.execute("UPDATE telegram_updates SET reply=?,code='knowledge_delivery_invalidated' WHERE environment_id=? AND bot_id=? AND update_id=?",
                                           (reply,*key))
                    LOG.info('telegram_knowledge_reply_invalidated')
            self._delivery_state(key, 'sending')
            LOG.info('telegram_reply_sending')
            try:
                sent = self.api.call('sendMessage', {'chat_id': row['chat_id'], 'text': reply,
                    'link_preview_options': {'is_disabled': True}})
                if (type(sent) is not dict or type(sent.get('message_id')) is not int
                        or type(sent.get('chat')) is not dict or sent['chat'].get('id') != row['chat_id']):
                    raise TelegramError('telegram_response_invalid')
            except TelegramError as error:
                if error.retry_after:
                    self._delivery_state(key, 'pending', error.retry_after)
                    LOG.warning('telegram_reply_deferred code=%s retry_seconds=%d', error.code, error.retry_after)
                    return  # Respect bot-wide flood control before any other send.
                self._delivery_state(key, 'failed' if error.code == 'telegram_access_or_conflict' else 'uncertain')
                LOG.warning('telegram_reply_unavailable code=%s', error.code)
            else:
                self._delivery_state(key, 'sent')
                LOG.info('telegram_reply_sent confirmation=api_accepted')

    def _delivery_state(self, key, state, delay=0):
        with self.store.transaction():
            self.store.execute("""UPDATE telegram_updates SET state=?,updated_at=?,next_attempt_at=?
                WHERE environment_id=? AND bot_id=? AND update_id=?""",
                (state, stamp(self.clock()), stamp(self.clock()+timedelta(seconds=delay)), *key))

    def poll_once(self):
        self.deliver()
        LOG.info('telegram_poll_started')
        updates = self.api.call('getUpdates', {'offset': self.offset(), 'timeout': self.config.telegram['poll_seconds'],
            'limit': self.config.telegram['batch_size'], 'allowed_updates': ['message']})
        if type(updates) is not list or len(updates) > self.config.telegram['batch_size']:
            raise EngineError('telegram_response_invalid')
        previous = -1
        # Validate complete batch ordering before acknowledging any item.
        for update in updates:
            uid = update.get('update_id') if type(update) is dict else None
            if type(uid) is not int or not 0 <= uid < 2**63-1 or uid <= previous:
                raise EngineError('telegram_update_invalid')
            previous = uid
        LOG.info('telegram_poll_received updates=%d', len(updates))
        processed = []
        for update in updates:
            if self.stop.is_set():
                break
            self.process(update)
            processed.append(update)
        self.deliver()
        if self.receipt_observer:
            for update in processed:
                self.receipt_observer(self, update)

    def _lifecycle(self, state, code=None):
        if self.lifecycle_observer is not None:
            self.lifecycle_observer(state,code)

    def run(self):
        if self.stop.is_set():
            return
        self.startup()
        LOG.info('telegram_ready simulation=true')
        self._lifecycle('ready')
        unavailable = False
        while not self.stop.is_set():
            try:
                self.poll_once()
                if unavailable:
                    LOG.info('telegram_poll_recovered')
                    self._lifecycle('ready')
                    unavailable = False
            except TelegramError as error:
                unavailable = True
                LOG.warning('telegram_poll_unavailable code=%s', error.code)
                self._lifecycle('unavailable',error.code)
                if error.code == 'telegram_access_or_conflict':
                    raise
                self.stop.wait(error.retry_after or self.config.telegram['retry_seconds'])
