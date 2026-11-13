"""Strict, bounded YAML parsing. Parser diagnostics never expose input values."""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from types import MappingProxyType
from datetime import date
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import re
import yaml
from app.core.contracts import EngineError

ROLE_CAPABILITIES = {
    'resident': frozenset({'guidance.read', 'context.read', 'context.write', 'knowledge.read',
                           'reservation.create', 'reservation.read', 'request.create', 'request.read'}),
    'manager': frozenset({'guidance.read', 'guidance.create', 'guidance.correct',
                          'guidance.cancel', 'guidance.history', 'context.read', 'context.write', 'knowledge.read',
                          'request.read', 'request.respond', 'report.read', 'operations.reconcile'}),
}
TELEGRAM_TOKEN_PATTERN = re.compile(r'[1-9][0-9]*:[A-Za-z0-9_-]{20,128}')


class TelegramSecretsError(EngineError):
    def __init__(self, code, *, source='secrets.yaml', stage='secrets_schema', field='telegram_bot_token'):
        super().__init__(code)
        self.diagnostic = {'source': source, 'stage': stage}
        if field is not None:
            self.diagnostic['field'] = field


def validate_telegram_token(token, bot_id=None, *, prompt=False):
    """One format contract. Normalize boundary whitespace only in new prompt input."""
    source, stage = ('hidden_prompt', 'token_input') if prompt else ('secrets.yaml', 'stored_token')
    def reject(reason):
        raise TelegramSecretsError('telegram_token_'+reason, source=source, stage=stage)
    if type(token) is not str:
        reject('type_invalid')
    if prompt:
        token = token.strip(' \t\r\n')
    if not token:
        reject('input_empty' if prompt else 'stored_empty')
    if any(ord(char) < 32 or ord(char) == 127 for char in token):
        reject('input_control_characters' if prompt else 'stored_control_characters')
    if any(char.isspace() for char in token):
        reject('input_whitespace' if prompt else 'stored_whitespace')
    if not TELEGRAM_TOKEN_PATTERN.fullmatch(token):
        reject('input_format_invalid' if prompt else 'stored_format_invalid')
    prefix = token.split(':', 1)[0]
    if len(prefix) > 16 or not 0 < int(prefix) < 2**52:
        reject('bot_id_invalid')
    if bot_id is not None and prefix != str(bot_id):
        reject('bot_id_mismatch')
    return token


class ConfigurationFileError(EngineError):
    """Only fixed file labels and parser coordinates may leave the reader."""
    def __init__(self, code, path, *, line=None, column=None):
        super().__init__(code)
        name = Path(path).name
        self.diagnostic = {'file': name if name in {
            'config.yaml', 'secrets.yaml', 'config.example.yaml',
            'config.telegram.example.yaml', 'secrets.example.yaml'} else 'configuration_file'}
        if line is not None:
            self.diagnostic.update(line=line, column=column)


def read_configuration_bytes(path):
    try:
        with Path(path).open('rb') as handle:
            data = handle.read(65537)
    except PermissionError:
        raise ConfigurationFileError('configuration_read_denied', path) from None
    except FileNotFoundError:
        raise ConfigurationFileError('configuration_file_missing', path) from None
    except OSError:
        raise ConfigurationFileError('configuration_read_error', path) from None
    if len(data) > 65536:
        raise ConfigurationFileError('invalid_yaml_size', path)
    return data


class StrictLoader(yaml.SafeLoader):
    def construct_mapping(self, node, deep=False):
        result = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str) or key in result or key == '<<':
                raise EngineError('invalid_yaml')
            result[key] = self.construct_object(value_node, deep=deep)
        return result


def read_yaml(path):
    try:
        source = read_configuration_bytes(path).decode('utf-8-sig')
        # Anchors/aliases can introduce recursion or expansion; unnecessary in I1.
        if any(isinstance(t, (yaml.tokens.AnchorToken, yaml.tokens.AliasToken)) for t in yaml.scan(source)):
            raise EngineError('invalid_yaml')
        return yaml.load(source, Loader=StrictLoader)
    except ConfigurationFileError:
        raise
    except UnicodeError:
        raise ConfigurationFileError('invalid_yaml_encoding', path) from None
    except yaml.YAMLError as error:
        mark = getattr(error, 'problem_mark', None)
        raise ConfigurationFileError('invalid_yaml', path,
            line=mark.line+1 if mark else None, column=mark.column+1 if mark else None) from None
    except (EngineError, RecursionError):
        raise ConfigurationFileError('invalid_yaml', path) from None


def keys(value, expected):
    if type(value) is not dict or set(value) != set(expected):
        raise EngineError('invalid_configuration')


def positive(value):
    if type(value) is not int or value <= 0:
        raise EngineError('invalid_configuration')
    return value


def decimal(value):
    if type(value) not in (str, int):
        raise EngineError('invalid_configuration')
    try:
        result = Decimal(value)
        if not result.is_finite() or result < 0:
            raise InvalidOperation
        return result
    except (InvalidOperation, ValueError):
        raise EngineError('invalid_configuration') from None


@dataclass(frozen=True)
class User:
    channel: str
    channel_user_id: int
    chat_ids: tuple
    role: str
    enabled: bool


@dataclass(frozen=True)
class Config:
    environment_id: str
    users: tuple
    permissions: object
    limits: object
    retention: object
    openai: object
    timezone: str = 'America/Sao_Paulo'
    telegram: object = None
    google: object = None
    knowledge: object = None
    operations: object = None


def load_config(path):
    return _parse_config(read_yaml(path))


def load_enrollment_config(path):
    """Validate the same schema, allowing null identity fields only during enrollment.

    Return raw data, never an operational Config with missing identities.
    """
    raw = read_yaml(path)
    parsed = _parse_config(raw, enrollment=True)
    if not parsed.telegram:
        raise EngineError('telegram_not_configured')
    return raw


def _parse_config(raw, *, enrollment=False):
    expected = ('environment_id', 'simulation_mode', 'agent_name', 'locale', 'timezone',
                'users', 'permissions', 'limits', 'retention', 'openai')
    optional = tuple(k for k in ('channels', 'google', 'knowledge', 'operations') if type(raw) is dict and k in raw)
    keys(raw, (*expected, *optional))
    from app.integrations.google_config import parse_google
    google = parse_google(raw.get('google'))
    from app.ai.configuration import parse_knowledge
    knowledge = parse_knowledge(raw.get('knowledge'), google)
    from app.config.operations import parse_operations
    operations = parse_operations(raw.get('operations'), google)
    if operations is not None and operations.live_authorized:
        from dataclasses import replace
        google = replace(google, write_access=True)
    telegram = None
    if 'channels' in raw:
        keys(raw['channels'], ('telegram',))
        tg = raw['channels']['telegram']
        keys(tg, ('bot_id', 'poll_seconds', 'request_seconds', 'batch_size', 'retry_seconds'))
        for key, value in tg.items():
            if not (enrollment and key == 'bot_id' and value is None):
                positive(value)
        if not ((tg['bot_id'] is None or tg['bot_id'] < 2**52) and 1 <= tg['poll_seconds'] <= 50 and tg['poll_seconds'] < tg['request_seconds'] <= 60
                and tg['batch_size'] <= 100 and tg['retry_seconds'] <= 60):
            raise EngineError('unsafe_configuration')
        telegram = MappingProxyType(tg)
    env = raw['environment_id']
    import re
    if not isinstance(env, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', env):
        raise EngineError('invalid_configuration')
    if raw['simulation_mode'] is not True or raw['agent_name'] != 'Alfredo' or raw['locale'] != 'pt-BR':
        raise EngineError('unsafe_configuration')
    if raw['timezone'] != 'America/Sao_Paulo':
        raise EngineError('invalid_timezone')
    try:
        ZoneInfo(raw['timezone'])
    except ZoneInfoNotFoundError:
        raise EngineError('timezone_data_missing') from None
    users, seen = [], set()
    if type(raw['users']) is not list or not raw['users']:
        raise EngineError('invalid_configuration')
    for u in raw['users']:
        keys(u, ('channel', 'channel_user_id', 'chat_ids', 'role', 'enabled'))
        if u['channel'] != ('telegram' if telegram else 'local') or type(u['role']) is not str or u['role'] not in ROLE_CAPABILITIES or type(u['enabled']) is not bool:
            raise EngineError('unsafe_configuration')
        uid = None if enrollment and telegram and u['channel_user_id'] is None else positive(u['channel_user_id'])
        if type(u['chat_ids']) is not list or not u['chat_ids']:
            raise EngineError('invalid_configuration')
        chats = tuple(None if enrollment and telegram and c is None else positive(c) for c in u['chat_ids'])
        if len(set(chats)) != len(chats) or (uid is not None and (u['channel'], uid) in seen):
            raise EngineError('invalid_configuration')
        seen.add((u['channel'], uid))
        users.append(User(u['channel'], uid, chats, u['role'], u['enabled']))
    if telegram and (len(users) != 2 or any(not u.enabled or
            (u.channel_user_id is not None and u.channel_user_id >= 2**52) or u.chat_ids != (u.channel_user_id,)
            or (u.channel_user_id is not None and u.channel_user_id == telegram['bot_id']) for u in users)):
        raise EngineError('unsafe_configuration')
    if {u.role for u in users if u.enabled} != {'resident', 'manager'}:
        raise EngineError('invalid_configuration')
    if operations is not None and set(operations.units) != {str(u.channel_user_id) for u in users if u.enabled and u.role == 'resident'}:
        raise EngineError('operations_units_invalid')
    keys(raw['permissions'], ROLE_CAPABILITIES)
    perms = {}
    for role, allowed in ROLE_CAPABILITIES.items():
        configured = raw['permissions'][role]
        if type(configured) is not list or not all(type(p) is str for p in configured) or not set(configured) <= allowed:
            raise EngineError('unsafe_permissions')
        perms[role] = frozenset(configured)
    keys(raw['limits'], ('confirmation_seconds', 'max_message_chars', 'messages_per_minute'))
    for value in raw['limits'].values():
        positive(value)
    if raw['limits']['confirmation_seconds'] > 3600 or raw['limits']['max_message_chars'] > 65536:
        raise EngineError('unsafe_configuration')
    retention = raw['retention']
    minima = dict(conversation_days=30, deduplication_days=30, audit_days=90,
                  closed_request_days=90, guidance_audit_days=90)
    keys(retention, minima)
    for key, minimum in minima.items():
        if positive(retention[key]) < minimum:
            raise EngineError('unsafe_retention')
    budget = raw['openai'].copy() if type(raw['openai']) is dict else {}
    money_keys = ('monthly_budget_brl', 'alert_brl', 'usd_brl', 'input_usd_per_million', 'output_usd_per_million')
    keys(budget, (*money_keys, 'reference_date', 'reference_label', 'missing_measurement'))
    for key in money_keys:
        budget[key] = decimal(budget[key])
    if not 0 < budget['alert_brl'] < budget['monthly_budget_brl'] or budget['usd_brl'] <= 0:
        raise EngineError('invalid_configuration')
    try:
        date.fromisoformat(budget['reference_date'])
    except (ValueError, TypeError):
        raise EngineError('invalid_configuration') from None
    if budget['missing_measurement'] != 'block' or type(budget['reference_label']) is not str or not budget['reference_label']:
        raise EngineError('unsafe_configuration')
    return Config(env, tuple(users), MappingProxyType(perms), MappingProxyType(raw['limits']),
                  MappingProxyType(retention), MappingProxyType(budget), telegram=telegram, google=google,
                  knowledge=knowledge, operations=operations)


def load_telegram_token(path, bot_id):
    """Called only by explicitly enabled live polling. Never echo credential values."""
    raw = load_enrollment_secrets(path, bot_id)
    if raw['telegram_bot_token'] is None:
        raise TelegramSecretsError('telegram_token_missing', stage='stored_token')
    return raw['telegram_bot_token']


def load_enrollment_secrets(path, bot_id=None):
    """Null token is a valid draft; all other secret constraints remain mandatory."""
    raw = read_yaml(path)
    try:
        keys(raw, ('telegram_bot_token', 'openai_api_key', 'google_oauth'))
    except EngineError:
        raise TelegramSecretsError('telegram_secrets_schema_invalid', field=None) from None
    token = raw['telegram_bot_token']
    from app.ai.configuration import validate_api_key
    validate_api_key(raw['openai_api_key'])
    # I3 replaces the blanket Google prohibition with a strict read-only schema.
    # Every Telegram consumer uses this same loader; malformed material still fails closed.
    from app.integrations.google_config import validate_oauth
    validate_oauth(raw['google_oauth'])
    if token is not None:
        validate_telegram_token(token, bot_id)
    return raw


def validate_secrets(path=None):
    """Optional schema for future secrets; no credentials are needed by I1."""
    if path is None or not Path(path).exists():
        return
    raw = read_yaml(path)
    keys(raw, ('telegram_bot_token', 'openai_api_key', 'google_oauth'))
    if any(v is not None for v in raw.values()):
        raise EngineError('real_secrets_not_supported_in_i1')
