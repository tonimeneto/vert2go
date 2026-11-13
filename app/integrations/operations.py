"""I5 allowlisted writes. No delete, arbitrary URL, append or automatic write retry."""
from contextlib import contextmanager
import hashlib
import logging
import re
from urllib.parse import quote
from app.core.contracts import EngineError, instant
from app.integrations.google_http import GoogleHTTP, Payload

LOG = logging.getLogger('alfredo.google')


class OperationsHTTP(GoogleHTTP):
    def __init__(self, config, bearer, **kwargs):
        if config.operations is None:
            raise EngineError('operations_not_configured')
        self.operations = config.operations
        self.environment_id = config.environment_id
        super().__init__(config.google,bearer,**kwargs)

    def _consent(self):
        self.operations.require_live()
        if self.allow_live is not True or not self.policy.config.write_access:
            raise EngineError('live_google_writes_authorization_required')

    def event_request(self, method, calendar_id, *, event_id=None, event=None):
        self._consent()
        c = self.policy.config
        if calendar_id != self.operations.calendar_id:
            raise EngineError('google_resource_denied')
        base = 'https://www.googleapis.com/calendar/v3/calendars/'+quote(calendar_id,safe='')+'/events'
        if method == 'GET' and event is None and type(event_id) is str and re.fullmatch('[0-9a-f]{64}',event_id):
            return self._request('GET',base+'/'+event_id,{},None,'calendar.get',calendar_id)
        if method != 'POST' or event_id is not None or type(event) is not dict:
            raise EngineError('google_operation_denied')
        if set(event) != {'id','summary','description','start','end','extendedProperties'}:
            raise EngineError('google_operation_denied')
        if type(event['id']) is not str or not re.fullmatch('[0-9a-f]{64}',event['id']):
            raise EngineError('google_operation_denied')
        for key in ('start','end'):
            value = event[key]
            if type(value) is not dict or set(value) != {'dateTime','timeZone'} or value['timeZone'] != 'America/Sao_Paulo':
                raise EngineError('google_operation_denied')
        if not instant(c.window_start) <= instant(event['start']['dateTime']) < instant(event['end']['dateTime']) <= instant(c.window_end):
            raise EngineError('google_resource_denied')
        if (event['summary'] != 'Reserva experimental Alfredo' or event['description'] != 'Simulação sem validade oficial.'
                or type(event['extendedProperties']) is not dict or set(event['extendedProperties']) != {'private'}):
            raise EngineError('google_operation_denied')
        props = event['extendedProperties']['private']
        if (type(props) is not dict or set(props) != {'operation_id','environment_id','resource_id','owner_ref','proposal_hash'}
                or any(type(v) is not str or not 1 <= len(v) <= 128 for v in props.values())):
            raise EngineError('google_operation_denied')
        from app.core.contracts import digest
        from app.services.operational_memory import identifier
        identifier(props['operation_id'])
        if (props['environment_id'] != self.environment_id or props['resource_id'] not in self.operations.resources
                or event['id'] != digest([self.environment_id,props['operation_id']])
                or any(not re.fullmatch('[0-9a-f]{64}',props[key]) for key in ('owner_ref','proposal_hash'))):
            raise EngineError('google_operation_denied')
        return self._request('POST',base,{'sendUpdates':'none'},event,'calendar.insert',calendar_id)

    def row_request(self, spreadsheet_id, target, values):
        self._consent()
        region = re.fullmatch(r'(.+)!A([0-9]+):J([0-9]+)',self.operations.sheet_range)
        row = re.fullmatch(r'(.+)!A([0-9]+):J([0-9]+)',target) if type(target) is str else None
        if (spreadsheet_id != self.operations.spreadsheet_id or row is None or row[1] != region[1]
                or row[2] != row[3] or not int(region[2]) <= int(row[2]) <= int(region[3])
                or type(values) is not list or len(values) != 10
                or any(type(v) is not str or len(v) > 16000 for v in values)):
            raise EngineError('google_resource_denied')
        url = 'https://sheets.googleapis.com/v4/spreadsheets/'+quote(spreadsheet_id,safe='')+'/values/'+quote(target,safe='')
        return self._request('PUT',url,{'valueInputOption':'RAW'},
                             {'range':target,'majorDimension':'ROWS','values':[values]},'sheets.update',spreadsheet_id)

    def _request(self, method, url, params, body, operation, resource):
        # Exactly one network attempt. Any lost/malformed response is reconciled by the engine.
        self._consent()
        import requests
        from app.integrations.google_auth import quiet_oauth_logs
        response, status = None,None
        try:
            token = self.bearer()
            timeout = min(self.policy.config.timeout_seconds,self.remaining())
            with quiet_oauth_logs():
                response = self._session.request(method,url,params=params,json=body,
                    headers={'Authorization':'Bearer '+token},timeout=timeout,allow_redirects=False,stream=True)
            status = response.status_code
            output = bytearray()
            for block in response.iter_content(chunk_size=65536):
                self.remaining()
                output.extend(block)
                if len(output) > self.policy.config.max_bytes:
                    raise EngineError('google_response_limit')
            if status == 409 and operation == 'calendar.insert':
                return {}  # Existing deterministic ID must still be read and strictly validated.
            if status == 401:
                raise EngineError('google_reauthorization_required')
            if status == 403:
                raise EngineError('google_access_denied')
            if not 200 <= status < 300:
                raise EngineError('google_operation_uncertain')
            return Payload(bytes(output)).json()
        except requests.RequestException:
            raise EngineError('google_operation_uncertain') from None
        finally:
            LOG.info('google_operation_finished operation=%s resource=%s status=%s',operation,
                     hashlib.sha256(resource.encode()).hexdigest()[:24],status if status is not None else 'none')
            if response is not None:
                response.close()


class FreshGoogle:
    """Each bounded operation gets a fresh HTTP budget, using the existing OAuth store."""
    def __init__(self, config, secrets_path, *, allow_live=False):
        self.config,self.secrets_path,self.allow_live = config,secrets_path,allow_live

    @contextmanager
    def connection(self):
        from app.integrations.google_auth import GoogleAuth
        self.config.operations.require_live()
        if self.allow_live is not True:
            raise EngineError('live_google_writes_authorization_required')
        auth = GoogleAuth(self.config.google,self.secrets_path,allow_live=True)
        http = OperationsHTTP(self.config,auth.bearer,allow_live=True,refresh=lambda:auth.bearer(force_refresh=True))
        try:
            yield http
        finally:
            http.close()

    def read_events(self, calendar_id, start, end):
        from app.integrations.calendar import Calendar
        with self.connection() as http:
            return Calendar(self.config.google,http).read_events(calendar_id,start,end)

    def create_event(self, calendar_id, event):
        with self.connection() as http:
            return http.event_request('POST',calendar_id,event=event)

    def get_event(self, calendar_id, event_id):
        with self.connection() as http:
            return http.event_request('GET',calendar_id,event_id=event_id)

    def read_range(self, spreadsheet_id, target):
        from app.integrations.sheets import Sheets
        with self.connection() as http:
            return Sheets(self.config.google,http).read_range(spreadsheet_id,target)

    def write_row(self, spreadsheet_id, target, values):
        with self.connection() as http:
            return http.row_request(spreadsheet_id,target,values)
