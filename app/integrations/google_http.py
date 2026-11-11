"""GET-only endpoint allowlist. Callers cannot supply URLs, methods or field masks."""
from dataclasses import dataclass, field
from datetime import timezone
import hashlib
import json
import logging
import random
import time
from urllib.parse import quote
from uuid import uuid4
from app.core.contracts import EngineError, instant
from app.integrations.google_config import a1_range

LOG = logging.getLogger('alfredo.google')


@dataclass(frozen=True)
class Payload:
    body: bytes = field(repr=False)

    def json(self):
        try:
            value = json.loads(self.body)
            if type(value) is not dict:
                raise ValueError
            return value
        except (ValueError, UnicodeError, RecursionError):
            raise EngineError('google_response_invalid') from None


class ReadPolicy:
    def __init__(self, config):
        if config is None:
            raise EngineError('google_not_configured')
        self.config = config

    def request(self, operation, resource, arguments):
        c = self.config
        if type(operation) is not str or type(resource) is not str or type(arguments) is not dict:
            raise EngineError('google_resource_denied')
        drive = 'https://www.googleapis.com/drive/v3'
        if operation == 'identity' and resource == '' and not arguments:
            return drive+'/about', {'fields': 'user(emailAddress)'}
        doc = next((d for d in c.documents if d.id == resource), None)
        if operation.startswith('drive.') and doc is not None:
            url = drive+'/files/'+quote(resource, safe='')
            if operation == 'drive.metadata' and not arguments:
                return url, {'fields': 'id,mimeType,version,modifiedTime,size,trashed,capabilities(canDownload)', 'supportsAllDrives': 'true'}
            if operation == 'drive.download' and not arguments:
                return url, {'alt': 'media', 'supportsAllDrives': 'true'}
            if operation == 'drive.export' and not arguments and doc.export_mime is not None:
                return url+'/export', {'mimeType': doc.export_mime}
        if operation == 'calendar.events' and resource == c.calendar_id and c.calendar_id:
            if not set(arguments) <= {'start','end','page_token'} or 'start' not in arguments or 'end' not in arguments:
                raise EngineError('google_resource_denied')
            start, end = arguments['start'], arguments['end']
            if type(start) is not str or type(end) is not str or not instant(c.window_start) <= instant(start) < instant(end) <= instant(c.window_end):
                raise EngineError('google_resource_denied')
            params = {'timeMin': start, 'timeMax': end, 'singleEvents': 'true',
                      'orderBy': 'startTime', 'maxResults': 100, 'timeZone': 'America/Sao_Paulo',
                      'fields': 'timeZone,accessRole,nextPageToken,items(id,status,start,end,transparency,updated,etag)'}
            if 'page_token' in arguments:
                token = arguments['page_token']
                if type(token) is not str or not 1 <= len(token) <= 4096 or any(ord(ch)<32 for ch in token):
                    raise EngineError('google_response_invalid')
                params['pageToken'] = token
            return 'https://www.googleapis.com/calendar/v3/calendars/'+quote(resource, safe='')+'/events', params
        if resource == c.spreadsheet_id and c.spreadsheet_id:
            url = 'https://sheets.googleapis.com/v4/spreadsheets/'+quote(resource, safe='')
            if operation == 'sheets.metadata' and not arguments:
                return url, {'fields': 'spreadsheetId,properties(timeZone)', 'includeGridData': 'false'}
            if operation == 'sheets.structure' and not arguments and c.discover_structure:
                return url, {'fields': 'spreadsheetId,sheets(properties(sheetId,title,sheetType,gridProperties(rowCount,columnCount))),namedRanges(name,range(sheetId,startRowIndex,endRowIndex,startColumnIndex,endColumnIndex))',
                             'includeGridData': 'false'}
            if operation == 'sheets.values' and set(arguments) == {'range'}:
                target = arguments['range']
                if type(target) is str and target in c.ranges and a1_range(target) <= c.max_cells:
                    return url+'/values/'+quote(target, safe=''), {'majorDimension': 'ROWS', 'valueRenderOption': 'UNFORMATTED_VALUE', 'dateTimeRenderOption': 'SERIAL_NUMBER'}
        raise EngineError('google_resource_denied')


class GoogleHTTP:
    def __init__(self, config, bearer, *, allow_live=False, session=None, clock=time.monotonic, sleep=time.sleep, refresh=None):
        self.policy, self.bearer = ReadPolicy(config), bearer
        self.allow_live, self.clock, self.sleep = allow_live, clock, sleep
        self.started, self.bytes_read, self.calls = clock(), 0, []
        self._session = session
        self.refresh = refresh
        if session is None:
            try:
                import requests
                self._session = requests.Session()
                self._session.trust_env = False
            except ImportError:
                raise EngineError('google_dependencies_missing') from None

    def close(self):
        self._session.close()

    def remaining(self):
        left = self.policy.config.total_seconds-(self.clock()-self.started)
        if left <= 0:
            raise EngineError('google_deadline_exceeded')
        return left

    def read(self, operation, resource, **arguments):
        # Resource and operation checks precede authentication, session calls and retries.
        url, params = self.policy.request(operation, resource, arguments)
        if self.allow_live is not True:
            raise EngineError('live_google_authorization_required')
        config = self.policy.config
        correlation = uuid4().hex
        reference = hashlib.sha256(resource.encode()).hexdigest()[:24]
        import requests
        refreshed = False
        for attempt in range(config.max_attempts):
            response = None
            status, error_code, retry = None, 'google_transport_error', False
            start = self.clock()
            try:
                self.remaining()
                token = self.bearer()
                timeout = min(config.timeout_seconds, self.remaining())
                from app.integrations.google_auth import quiet_oauth_logs
                with quiet_oauth_logs():
                    response = self._session.get(url, params=params, headers={'Authorization': 'Bearer '+token},
                                                 timeout=timeout, allow_redirects=False, stream=True)
                status = response.status_code
                body = bytearray()
                for block in response.iter_content(chunk_size=65536):
                    self.remaining()
                    self.bytes_read += len(block)
                    if self.bytes_read > config.max_bytes:
                        raise EngineError('google_response_limit')
                    body.extend(block)
                if 200 <= status < 300:
                    error_code = None
                    return Payload(bytes(body))
                if status == 401:
                    error_code = 'google_reauthorization_required'
                    retry = self.refresh is not None and not refreshed and attempt+1 < config.max_attempts
                elif status == 403:
                    error_code = 'google_access_denied'
                    try:
                        value = json.loads(body)
                        reasons = [e.get('reason') for e in value.get('error', {}).get('errors', []) if type(e) is dict]
                        retry = any(r in ('rateLimitExceeded', 'userRateLimitExceeded') for r in reasons)
                    except (ValueError, AttributeError, TypeError):
                        pass
                elif status == 404:
                    error_code = 'google_not_found_or_inaccessible'
                elif status == 429:
                    error_code, retry = 'google_rate_limited', True
                elif 500 <= status < 600:
                    error_code, retry = 'google_service_unavailable', True
                elif 300 <= status < 400:
                    error_code = 'google_redirect_denied'
                else:
                    error_code = 'google_request_rejected'
            except requests.RequestException:
                retry = True
            except EngineError as error:
                error_code = error.code
                raise
            finally:
                duration = round((self.clock()-start)*1000)
                record = {'correlation_id': correlation, 'operation': operation, 'resource_ref': reference,
                          'method': 'GET', 'attempt': attempt+1, 'http_status': status, 'duration_ms': duration,
                          'safe_error': error_code}
                self.calls.append(record)
                LOG.info('google_read operation=%s resource=%s correlation=%s attempt=%d status=%s duration_ms=%d',
                         operation, reference, correlation, attempt+1, status if status is not None else 'none', duration)
                if response is not None:
                    response.close()
            if not retry or attempt+1 >= config.max_attempts:
                raise EngineError(error_code)
            if status == 401:
                self.refresh()
                refreshed = True
                continue
            wait = 2**attempt + random.uniform(0, 0.25)
            if response is not None:
                header = response.headers.get('Retry-After', '')
                if header:
                    try:
                        wait = max(wait, float(header))
                    except (ValueError, TypeError):
                        from email.utils import parsedate_to_datetime
                        from datetime import datetime
                        try:
                            wait = max(wait, (parsedate_to_datetime(header)-datetime.now(timezone.utc)).total_seconds())
                        except (ValueError, TypeError, OverflowError):
                            raise EngineError('google_retry_after_invalid') from None
            if not 0 <= wait < self.remaining():
                raise EngineError('google_deadline_exceeded')
            self.sleep(wait)
        raise EngineError('google_transport_error')
