"""I4 declarations and consent. Parsing never reads credentials or uses the network."""
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from types import MappingProxyType
import re
from app.core.contracts import EngineError, instant


def fail():
    raise EngineError('knowledge_configuration_invalid')


def exact(raw, names):
    if type(raw) is not dict or set(raw) != set(names):
        fail()


def name(value, prefix=None):
    if type(value) is not str or not re.fullmatch(r'[A-Za-z0-9_-]{1,200}', value):
        fail()
    if prefix and not value.startswith(prefix):
        fail()
    return value


def model_name(value):
    """Model identifiers may contain dots; project and store IDs keep their own rules."""
    if type(value) is not str or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,199}', value):
        fail()
    return value


def amount(value):
    try:
        if type(value) not in (str, int):
            fail()
        result = Decimal(value)
        if not result.is_finite() or result < 0:
            fail()
        return result
    except (InvalidOperation, ValueError):
        fail()


@dataclass(frozen=True)
class AuthorizedDocument:
    id: str
    title: str
    sha256: str


@dataclass(frozen=True)
class KnowledgeConfig:
    enabled: bool
    project_id: str
    model: str
    vector_store_id: str | None
    accepted_i3: bool
    authorized_at: str | None
    telegram_authorized: bool
    documents: tuple
    limits: object
    prices: object

    def require_consent(self, *, telegram=False):
        if not self.enabled or not self.accepted_i3 or self.authorized_at is None or not self.documents:
            raise EngineError('knowledge_g3_required')
        if telegram and not self.telegram_authorized:
            raise EngineError('knowledge_telegram_authorization_required')


def parse_knowledge(raw, google):
    if raw is None:
        return None
    exact(raw, ('enabled','project_id','model','vector_store_id','authorization','documents','limits','prices'))
    auth = raw['authorization']
    exact(auth, ('accepted_i3','authorized_at','telegram'))
    if any(type(v) is not bool for v in (raw['enabled'], auth['accepted_i3'], auth['telegram'])):
        fail()
    if auth['authorized_at'] is not None:
        if type(auth['authorized_at']) is not str:
            fail()
        instant(auth['authorized_at'])
    project, model = name(raw['project_id'], 'proj_'), model_name(raw['model'])
    store = raw['vector_store_id']
    if store is not None:
        name(store, 'vs_')
    if type(raw['documents']) is not list or not 1 <= len(raw['documents']) <= 20 or google is None:
        fail()
    docs = []
    allowed = {d.id: d for d in google.documents}
    for doc in raw['documents']:
        exact(doc, ('id','title','sha256'))
        if (type(doc['id']) is not str or doc['id'] not in allowed or
                allowed[doc['id']].classification == 'unverified' or
                type(doc['title']) is not str or not 1 <= len(doc['title']) <= 160 or
                any(ord(c) < 32 for c in doc['title']) or
                type(doc['sha256']) is not str or not re.fullmatch('[0-9a-f]{64}', doc['sha256'])):
            fail()
        docs.append(AuthorizedDocument(**doc))
    if len({d.id for d in docs}) != len(docs):
        fail()
    bounds = dict(timeout_seconds=(1,60), max_question_chars=(32,4000), max_output_tokens=(128,4096),
                  max_results=(1,10), max_response_bytes=(1024,2097152), max_poll_attempts=(1,20),
                  poll_seconds=(1,5), max_storage_bytes=(1024,1073741824), max_input_tokens=(1024,131072))
    limits = raw['limits']
    exact(limits, bounds)
    for key, (low, high) in bounds.items():
        if type(limits[key]) is not int or not low <= limits[key] <= high:
            fail()
    # Bound a question plus the maximum supported chunk size per result and instruction overhead.
    if limits['max_input_tokens'] < limits['max_question_chars']+limits['max_results']*4096+2048:
        fail()
    prices = raw['prices'].copy() if type(raw['prices']) is dict else {}
    exact(prices, ('search_usd_per_call','storage_usd_per_gb_day','reference_date','reference_url'))
    for key in ('search_usd_per_call','storage_usd_per_gb_day'):
        prices[key] = amount(prices[key])
    from datetime import date
    try:
        date.fromisoformat(prices['reference_date'])
    except (TypeError, ValueError):
        fail()
    if type(prices['reference_url']) is not str or not prices['reference_url'].startswith('https://developers.openai.com/'):
        fail()
    return KnowledgeConfig(raw['enabled'], project, model, store, auth['accepted_i3'], auth['authorized_at'],
                           auth['telegram'], tuple(docs), MappingProxyType(limits.copy()), MappingProxyType(prices))


def validate_api_key(value):
    # Opaque secret, never normalize stored values, and never include it in errors.
    if value is not None and (type(value) is not str or not re.fullmatch(r'sk-[A-Za-z0-9_-]{20,1024}', value)):
        raise EngineError('openai_key_invalid')


def load_api_key(path):
    from app.config.schema import load_enrollment_secrets
    from app.integrations.private_files import private_acl
    private_acl(path)
    value = load_enrollment_secrets(path)['openai_api_key']
    if value is None:
        raise EngineError('openai_key_missing')
    return value
