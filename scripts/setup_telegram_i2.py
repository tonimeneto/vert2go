"""Local I2 enrollment. Credentials are prompted without echo, never CLI arguments."""
import argparse
from copy import deepcopy
import getpass
import json
from datetime import datetime, timezone
from pathlib import Path
import re
import sys
import tempfile
import warnings

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import yaml
from app.channels.telegram import TelegramAPI
from app.config.schema import (ConfigurationFileError, load_config, load_enrollment_config,
                               load_enrollment_secrets, load_telegram_token,
                               read_configuration_bytes, read_yaml, validate_telegram_token,
                               TelegramSecretsError)
from app.core.contracts import EngineError

def prepare(root=ROOT):
    """Exclusive creation only; existing private files are never replaced here."""
    config = read_yaml(root/'config.telegram.example.yaml')
    config['environment_id'] = 'i2-experimental'
    config['channels']['telegram']['bot_id'] = None
    for user in config['users']:
        user['channel_user_id'], user['chat_ids'] = None, [None]
    for name, raw in (('config.yaml', config), ('secrets.yaml', {
            'telegram_bot_token': None, 'openai_api_key': None, 'google_oauth': None})):
        path = root/name
        try:
            # On Windows, exclusive open can raise PermissionError for an existing
            # protected file. Do not request write access just to preserve it.
            if path.exists():
                continue
            with path.open('x', encoding='utf-8') as handle:
                handle.write('# Particular I2; nao publicar nem enviar ao chat.\n')
                yaml.safe_dump(raw, handle, allow_unicode=True, sort_keys=False)
        except FileExistsError:
            pass
        except OSError:
            raise ConfigurationFileError('configuration_write_denied', path) from None


def read_id(prompt, candidates=None):
    value = input(prompt).strip()
    if not re.fullmatch(r'[1-9][0-9]{0,15}', value) or not 0 < int(value) < 2**52:
        raise EngineError('invalid_participant_id')
    uid = int(value)
    if candidates is not None and uid not in candidates:
        raise EngineError('participant_not_discovered')
    return uid


def identify_bot(api, bot_id, expected_username=None):
    me = api.call('getMe', {})
    if type(me) is not dict or type(me.get('id')) is not int or me['id'] != bot_id or me.get('is_bot') is not True:
        raise EngineError('telegram_bot_mismatch')
    if expected_username is not None and (type(me.get('username')) is not str or
            me['username'].casefold() != expected_username.casefold()):
        raise EngineError('telegram_bot_username_mismatch')
    return me


def verify_webhook(api):
    webhook = api.call('getWebhookInfo', {})
    if type(webhook) is not dict or webhook.get('url') != '':
        raise EngineError('telegram_webhook_active')


def verify_bot(api, bot_id, expected_username=None):
    me = identify_bot(api, bot_id, expected_username)
    verify_webhook(api)
    return me


def discover(api):
    # No offset and no allowed_updates: do not acknowledge or change update selection.
    updates = api.call('getUpdates', {'limit': 100, 'timeout': 0})
    if type(updates) is not list or len(updates) > 100:
        raise EngineError('telegram_response_invalid')
    found = {}
    for update in updates:
        msg = update.get('message') if type(update) is dict else None
        if type(msg) is not dict:
            continue
        sender, chat = msg.get('from'), msg.get('chat')
        if (type(sender) is not dict or type(chat) is not dict or chat.get('type') != 'private'
                or sender.get('is_bot') is not False or type(sender.get('id')) is not int
                or not 0 < sender['id'] < 2**52 or type(chat.get('id')) is not int
                or sender['id'] != chat['id'] or type(msg.get('text')) is not str
                or not msg['text'].strip() or any(key in msg for key in
                    ('forward_origin', 'forward_date', 'sender_chat', 'business_connection_id'))):
            continue
        label = {'/cadastro_morador': 'morador', '/cadastro_sindica': 'sindica'}.get(msg.get('text'))
        found.setdefault(sender['id'], set())
        if label:
            found[sender['id']].add(label)
    for uid, labels in sorted(found.items()):
        hint = ', '.join(sorted(labels)) or 'sem marcador de perfil'
        print(f'Participante privado encontrado ({hint}), ID numerico: {uid}')
    if not found:
        raise EngineError('telegram_private_participants_unavailable')
    print('Confirme pessoalmente a conta de cada participante; nenhuma mensagem concede perfil.')
    return frozenset(found)


def read_token():
    if not sys.stdin.isatty():
        raise EngineError('interactive_terminal_required')
    print('A entrada e totalmente oculta: nao aparecem caracteres nem asteriscos. Cole somente o token e pressione Enter.')
    for attempt in range(3):
        with warnings.catch_warnings():
            warnings.simplefilter('error', getpass.GetPassWarning)
            try:
                entered = getpass.getpass('Token completo do BotFather, sem rotulo/aspas (entrada oculta): ')
            except getpass.GetPassWarning:
                raise EngineError('secure_terminal_required') from None
        try:
            token = validate_telegram_token(entered, prompt=True)
        except TelegramSecretsError as error:
            print('Entrada recusada: '+error.code)
            if attempt == 2:
                raise
            print('Cole somente o token completo. Se a colagem nao chegou, tente Shift+Insert ou clique direito.')
        else:
            if token != entered:
                print('Espacos externos removidos da nova entrada; formato validado.')
            return token


def save_enrollment(root, config, secrets, originals):
    """Save intentional progress with existing ACLs, no secret backup or temporary copy."""
    paths = root/'config.yaml', root/'secrets.yaml'
    if tuple(read_configuration_bytes(path) for path in paths) != originals:
        raise EngineError('configuration_changed_during_enrollment')
    old_secrets = read_yaml(paths[1])
    if old_secrets['telegram_bot_token'] is not None and old_secrets != secrets:
        raise EngineError('existing_token_change_denied')
    with tempfile.TemporaryDirectory(prefix='i2-enroll-', dir=root) as folder:
        cp = Path(folder)/'config.yaml'
        cp.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding='utf-8')
        load_enrollment_config(cp)
    validate_telegram_token(secrets['telegram_bot_token'], config['channels']['telegram']['bot_id'])
    for path, value in zip(paths, (config, secrets)):
        if read_yaml(path) != value:
            try:
                path.write_text(yaml.safe_dump(value, allow_unicode=True, sort_keys=False), encoding='utf-8')
            except OSError:
                raise ConfigurationFileError('configuration_write_denied', path) from None
    return tuple(read_configuration_bytes(path) for path in paths)


def enroll(root=ROOT, *, discovery=False, allow_live=False, expected_username=None,
           token_only=False, evidence=None):
    evidence = evidence if evidence is not None else {}
    evidence['stage'] = 'authorization'
    if discovery and not allow_live:
        raise EngineError('live_telegram_authorization_required')
    if token_only and not discovery:
        raise EngineError('token_only_requires_discovery')
    if expected_username is not None and (type(expected_username) is not str or
            not re.fullmatch(r'[A-Za-z0-9_]{5,32}', expected_username)):
        raise EngineError('invalid_expected_bot_username')
    evidence['stage'] = 'local_files'
    prepare(root)
    config_path, secrets_path = root/'config.yaml', root/'secrets.yaml'
    originals = read_configuration_bytes(config_path), read_configuration_bytes(secrets_path)
    config, secrets = deepcopy(read_yaml(config_path)), deepcopy(read_yaml(secrets_path))
    # Only the prepared Telegram layout may be completed. Never convert an I1 config.
    if (type(config) is not dict or type(config.get('channels')) is not dict
            or type(config['channels'].get('telegram')) is not dict
            or type(config.get('users')) is not list or len(config['users']) != 2
            or any(type(u) is not dict or u.get('channel') != 'telegram' for u in config['users'])
            or {u.get('role') for u in config['users']} != {'resident', 'manager'}):
        raise EngineError('existing_config_requires_manual_review')
    # Validate every non-identity field before prompting or touching the network.
    load_enrollment_config(config_path)
    load_enrollment_secrets(secrets_path)
    token = secrets['telegram_bot_token']
    if token is None:
        evidence['stage'] = 'token_input'
        token = read_token()
    else:
        validate_telegram_token(token)
    bot_id = int(token.split(':', 1)[0])
    existing_bot = config['channels']['telegram'].get('bot_id')
    if existing_bot is not None and existing_bot != bot_id:
        raise EngineError('existing_bot_mismatch')
    config['channels']['telegram']['bot_id'] = bot_id
    secrets['telegram_bot_token'] = token
    api = None
    if discovery:
        api = TelegramAPI(token, config['channels']['telegram']['request_seconds'])
        evidence.update(stage='getMe', external_api_attempted=True)
        identify_bot(api, bot_id, expected_username)
        evidence['getMe'] = 'passed'
        if expected_username:
            print('Identidade do bot confirmada pela API oficial: @'+expected_username)
    # Preserve a valid token before participant discovery can fail or be cancelled.
    evidence['stage'] = 'token_persistence'
    originals = save_enrollment(root, config, secrets, originals)
    evidence['token_saved'] = True
    print('Token e ID do bot gravados localmente; participantes podem ser concluidos em nova execucao.')
    if discovery:
        evidence['stage'] = 'getWebhookInfo'
        verify_webhook(api)
        evidence['getWebhookInfo'] = 'passed'
    if token_only:
        evidence['stage'] = 'token_registered'
        return
    candidates = None
    if discovery and any(u['channel_user_id'] is None for u in config['users']):
        evidence['stage'] = 'getUpdates'
        candidates = discover(api)
        evidence['candidate_count'] = len(candidates)
    evidence['stage'] = 'participant_confirmation'
    for user in config['users']:
        if user.get('channel_user_id') is None and user.get('chat_ids') == [None]:
            label = 'morador' if user['role'] == 'resident' else 'sindica'
            uid = read_id(f'ID numerico confirmado do participante {label}: ', candidates)
            user['channel_user_id'], user['chat_ids'] = uid, [uid]
    # Validate the complete pair in a private temporary directory, before any replacement.
    with tempfile.TemporaryDirectory(prefix='i2-enroll-', dir=root) as folder:
        cp = Path(folder)/'config.yaml'
        # Temporary artifacts contain config only; never make a temporary copy of the token.
        cp.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding='utf-8')
        checked = load_config(cp)
        if checked.telegram['bot_id'] != bot_id:
            raise EngineError('telegram_bot_mismatch')
    evidence['stage'] = 'participant_persistence'
    save_enrollment(root, config, secrets, originals)
    load_telegram_token(secrets_path, bot_id)
    evidence['stage'] = 'enrollment_complete'
    print('Cadastro local validado. Token e IDs nao foram gravados em evidencias publicas.')


def main(argv=None):
    parser = argparse.ArgumentParser(description='Cadastro local seguro dos dois participantes I2')
    parser.add_argument('--prepare', action='store_true', help='Criar somente arquivos ausentes, sem ler segredos')
    parser.add_argument('--discover', action='store_true', help='Consultar marcadores de cadastro via API oficial')
    parser.add_argument('--allow-live-telegram', action='store_true')
    parser.add_argument('--expected-bot', default='AlfredoVert2GoBot', help='Username esperado, sem @; nao recebe token')
    parser.add_argument('--token-only', action='store_true', help='Validar/salvar token e bot pela API, sem cadastrar participantes')
    args = parser.parse_args(argv)
    evidence = {'phase': 'I2', 'scope': 'telegram_enrollment',
                'updated_at': datetime.now(timezone.utc).isoformat(),
                'stage': 'start', 'result': 'not_run', 'external_api_attempted': False,
                'getMe': 'not_run', 'getWebhookInfo': 'not_run', 'token_saved': False,
                'messages_sent': False, 'database_opened': False, 'live_acceptance': 'blocked'}
    try:
        if args.prepare:
            if args.discover or args.allow_live_telegram or args.token_only:
                raise EngineError('incompatible_setup_options')
            prepare()
            evidence['stage'] = 'files_prepared'
            print('Arquivos particulares preparados; existentes preservados; nenhuma chamada externa.')
        else:
            enroll(discovery=args.discover, allow_live=args.allow_live_telegram,
                   expected_username=args.expected_bot if args.discover else None,
                   token_only=args.token_only, evidence=evidence)
        evidence['result'] = 'passed' if evidence['stage'] in ('enrollment_complete', 'files_prepared') else 'partial'
        return 0
    except EngineError as error:
        evidence.update(result='blocked', reason=error.code)
        print('Cadastro interrompido: '+error.code)
        if isinstance(error, (ConfigurationFileError, TelegramSecretsError)):
            evidence['diagnostic'] = error.diagnostic
            print(json.dumps(error.diagnostic, ensure_ascii=False))
        return 1
    except (OSError, ValueError, TypeError, KeyError, EOFError):
        evidence.update(result='blocked', reason='local_setup_error')
        print('Cadastro interrompido: local_setup_error')
        return 1
    except KeyboardInterrupt:
        evidence.update(result='cancelled', reason='operator_interrupted')
        print('Cadastro cancelado; etapas ja gravadas permanecem locais para retomada.')
        return 130
    finally:
        try:
            (ROOT/'docs'/'evidencias'/'i2-enrollment.json').write_text(
                json.dumps(evidence, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        except OSError:
            print('Evidencia indisponivel: enrollment_evidence_write_error')


if __name__ == '__main__':
    raise SystemExit(main())
