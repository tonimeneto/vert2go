"""Bounded immutable resource declarations. No network and no credential I/O."""
from dataclasses import dataclass
from datetime import timedelta
import re
from app.core.contracts import EngineError, instant

DRIVE_SCOPE = 'https://www.googleapis.com/auth/drive.readonly'
CALENDAR_SCOPE = 'https://www.googleapis.com/auth/calendar.events.readonly'
OWNED_SCOPE = 'https://www.googleapis.com/auth/calendar.events.owned.readonly'
CALENDAR_WRITE_SCOPE = 'https://www.googleapis.com/auth/calendar.events'
OWNED_WRITE_SCOPE = 'https://www.googleapis.com/auth/calendar.events.owned'
SHEETS_WRITE_SCOPE = 'https://www.googleapis.com/auth/spreadsheets'
AUTH_URI = 'https://accounts.google.com/o/oauth2/auth'
AUTH_URIS = (AUTH_URI, 'https://accounts.google.com/o/oauth2/v2/auth')
TOKEN_URI = 'https://oauth2.googleapis.com/token'
ALLOWED_SCOPES = frozenset((DRIVE_SCOPE, CALENDAR_SCOPE, OWNED_SCOPE,
                          CALENDAR_WRITE_SCOPE, OWNED_WRITE_SCOPE, SHEETS_WRITE_SCOPE))


def reject(code='google_configuration_invalid'):
    raise EngineError(code)


def exact(value, names):
    if type(value) is not dict or set(value) != set(names):
        reject()


def identifier(value, *, calendar=False):
    pattern = r'[A-Za-z0-9_@.\-]{1,254}' if calendar else r'[A-Za-z0-9_\-]{1,200}'
    if type(value) is not str or not re.fullmatch(pattern, value) or value in ('primary', '.', '..'):
        reject()
    return value


def account(value):
    if type(value) is not str or not re.fullmatch(r'[A-Za-z0-9.!#$%&\x27*+/=?^_`{|}~\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,63}', value) or len(value) > 254:
        reject()
    return value.casefold()


def bounded(value, low, high):
    if type(value) is not int or not low <= value <= high:
        reject()
    return value


def a1_range(value):
    # Explicit tab and finite rectangular range only; no whole columns/rows/named ranges.
    if type(value) is not str or len(value) > 180:
        reject()
    match = re.fullmatch(r"(?:'((?:[^'!\r\n]|''){1,100})'|([A-Za-z_][A-Za-z0-9_ ]{0,99}))!([A-Z]{1,3})([1-9][0-9]{0,5}):([A-Z]{1,3})([1-9][0-9]{0,5})", value)
    if not match:
        reject()
    def col(text):
        n = 0
        for ch in text:
            n = n*26 + ord(ch)-64
        return n
    left, top, right, bottom = col(match[3]), int(match[4]), col(match[5]), int(match[6])
    if right < left or bottom < top or right > 18278:
        reject()
    return (right-left+1)*(bottom-top+1)


@dataclass(frozen=True)
class Document:
    id: str
    classification: str
    export_mime: str | None


@dataclass(frozen=True)
class GoogleConfig:
    expected_account: str
    documents: tuple
    calendar_id: str | None
    calendar_owned: bool
    window_start: str | None
    window_end: str | None
    spreadsheet_id: str | None
    ranges: tuple
    timeout_seconds: int
    total_seconds: int
    max_attempts: int
    max_pages: int
    max_bytes: int
    max_cells: int
    discover_structure: bool = False
    write_access: bool = False

    @property
    def scopes(self):
        if self.write_access:
            return (DRIVE_SCOPE, OWNED_WRITE_SCOPE if self.calendar_owned else CALENDAR_WRITE_SCOPE, SHEETS_WRITE_SCOPE)
        return (DRIVE_SCOPE,) + ((OWNED_SCOPE if self.calendar_owned else CALENDAR_SCOPE,) if self.calendar_id else ())


def parse_google(raw):
    if raw is None:
        return None
    exact(raw, ('expected_account', 'drive_documents', 'calendar', 'sheets', 'limits'))
    email = account(raw['expected_account'])
    docs = raw['drive_documents']
    if type(docs) is not list or not 1 <= len(docs) <= 20:
        reject()
    documents = []
    for doc in docs:
        exact(doc, ('id', 'classification', 'export_mime'))
        if doc['classification'] not in ('official', 'authorized_operational', 'simulation', 'unverified') or doc['export_mime'] not in (None, 'text/plain', 'application/pdf'):
            reject()
        documents.append(Document(identifier(doc['id']), doc['classification'], doc['export_mime']))
    if len({d.id for d in documents}) != len(documents):
        reject()
    calendar_id, owned, start, end = None, False, None, None
    if raw['calendar'] is not None:
        cal = raw['calendar']
        exact(cal, ('id', 'owned', 'window_start', 'window_end'))
        calendar_id = identifier(cal['id'], calendar=True)
        if type(cal['owned']) is not bool or type(cal['window_start']) is not str or type(cal['window_end']) is not str:
            reject()
        owned, start, end = cal['owned'], cal['window_start'], cal['window_end']
        if not timedelta(0) < instant(end)-instant(start) <= timedelta(days=31):
            reject()
    spreadsheet_id, ranges, discover_structure = None, (), False
    if raw['sheets'] is not None:
        sheet = raw['sheets']
        exact(sheet, ('id', 'ranges', 'discover_structure') if type(sheet) is dict and 'discover_structure' in sheet else ('id', 'ranges'))
        spreadsheet_id = identifier(sheet['id'])
        discover_structure = sheet.get('discover_structure', False)
        if type(discover_structure) is not bool:
            reject()
        if type(sheet['ranges']) is not list or not (0 if discover_structure else 1) <= len(sheet['ranges']) <= 10 or any(type(r) is not str for r in sheet['ranges']):
            reject()
        ranges = tuple(sheet['ranges'])
        if len(set(ranges)) != len(ranges):
            reject()
    limits = raw['limits']
    bounds = {'timeout_seconds': (1,30), 'total_seconds': (1,120), 'max_attempts': (1,3),
              'max_pages': (1,10), 'max_bytes': (1,10485760), 'max_cells': (1,5000)}
    exact(limits, bounds)
    for name, (low, high) in bounds.items():
        bounded(limits[name], low, high)
    if limits['total_seconds'] < limits['timeout_seconds'] or sum(a1_range(r) for r in ranges) > limits['max_cells']:
        reject()
    return GoogleConfig(email, tuple(documents), calendar_id, owned, start, end,
                        spreadsheet_id, ranges, discover_structure=discover_structure, **limits)


def validate_oauth(raw):
    """Validate structure without ever including a value in an exception."""
    if raw is None:
        return
    try:
        exact(raw, ('client', 'token'))
        client = raw['client']
        exact(client, ('client_id', 'client_secret', 'project_id', 'auth_uri', 'token_uri'))
        for key in ('client_id', 'client_secret', 'project_id'):
            if type(client[key]) is not str or not 1 <= len(client[key]) <= 4096 or any(c.isspace() for c in client[key]):
                reject()
        if not client['client_id'].endswith('.apps.googleusercontent.com') or client['auth_uri'] not in AUTH_URIS or client['token_uri'] != TOKEN_URI:
            reject()
        token = raw['token']
        if token is not None:
            exact(token, ('access_token', 'refresh_token', 'expiry', 'scopes', 'account'))
            for key in ('access_token', 'refresh_token'):
                if type(token[key]) is not str or not 1 <= len(token[key]) <= 8192 or any(c.isspace() for c in token[key]):
                    reject()
            if type(token['expiry']) is not str:
                reject()
            instant(token['expiry'])
            account(token['account'])
            scopes = token['scopes']
            if type(scopes) is not list or not 1 <= len(scopes) <= 3 or any(type(s) is not str for s in scopes) or len(set(scopes)) != len(scopes) or not set(scopes) <= ALLOWED_SCOPES or DRIVE_SCOPE not in scopes:
                reject()
    except (EngineError, TypeError, ValueError, KeyError):
        raise EngineError('google_oauth_schema_invalid') from None


def validate_binding(raw, config):
    validate_oauth(raw)
    if raw is None:
        reject('google_client_missing')
    if raw['token'] is None:
        reject('google_reauthorization_required')
    token = raw['token']
    if token['account'].casefold() != config.expected_account:
        reject('google_account_mismatch')
    if set(token['scopes']) != set(config.scopes):
        reject('google_scope_mismatch')
