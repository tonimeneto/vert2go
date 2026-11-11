"""I3 security and integration contracts, with fictitious data and blocked network."""
from contextlib import redirect_stdout
from copy import deepcopy
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlsplit
import yaml

from app.config.schema import _parse_config, load_telegram_token, load_enrollment_secrets
from app.core.contracts import EngineError
from app.integrations.google_config import (parse_google, validate_oauth, a1_range,
    DRIVE_SCOPE, CALENDAR_SCOPE, OWNED_SCOPE, AUTH_URI, TOKEN_URI)
from app.integrations.google_auth import GoogleAuth, credential_record, quiet_oauth_logs, import_desktop_client
from app.integrations.google_http import GoogleHTTP, ReadPolicy, Payload
from app.integrations.drive import Drive
from app.integrations.calendar import Calendar
from app.integrations.sheets import Sheets
from app.integrations.private_files import atomic_yaml, private_lock, private_acl
from scripts.check_google_i3 import check
from scripts.setup_google_i3 import configure, authorize, stage_downloaded_client

ROOT = Path(__file__).resolve().parents[1]
MARKER = 'PRIVATE_MARKER_NEVER_LOG'


def declaration():
    return {'expected_account': 'alfredo@example.invalid',
            'drive_documents': [{'id': 'doc-fictional', 'classification': 'official', 'export_mime': 'text/plain'}],
            'calendar': {'id': 'calendar-fictional@group.calendar.google.com', 'owned': False,
                         'window_start': '2026-11-01T00:00:00-03:00', 'window_end': '2026-11-30T00:00:00-03:00'},
            'sheets': {'id': 'sheet-fictional', 'ranges': ["'Operacao'!A1:B2"]},
            'limits': {'timeout_seconds': 2, 'total_seconds': 20, 'max_attempts': 3,
                       'max_pages': 2, 'max_bytes': 100000, 'max_cells': 20}}


def secrets(config=None):
    config = config or parse_google(declaration())
    return {'telegram_bot_token': '9009:'+'X'*30, 'openai_api_key': None,
            'google_oauth': {'client': {'client_id': 'fictional.apps.googleusercontent.com',
                'client_secret': MARKER, 'project_id': 'fictional', 'auth_uri': AUTH_URI, 'token_uri': TOKEN_URI},
                'token': {'access_token': MARKER, 'refresh_token': MARKER,
                          'expiry': '2099-01-01T00:00:00+00:00', 'scopes': list(config.scopes),
                          'account': config.expected_account}}}


def response(value=None, status=200, headers=None):
    obj = MagicMock()
    obj.status_code = status
    obj.headers = headers or {}
    obj.iter_content.return_value = [value if type(value) is bytes else json.dumps(value or {}).encode()]
    return obj


def metadata(**values):
    return {'id':'doc-fictional', 'version':'1', 'modifiedTime':'2026-11-09T12:00:00Z',
            'mimeType':'text/plain', 'size':'5', 'trashed':False, 'capabilities':{'canDownload':True}, **values}


class GoogleCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='vert2go-i3-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = parse_google(declaration())
        self.bearer = MagicMock(return_value=MARKER)
        self.session = MagicMock()
        self.http = GoogleHTTP(self.config, self.bearer, allow_live=True, session=self.session, sleep=lambda _: None)
        self.addCleanup(self.http.close)
        for name in ('socket.socket.connect', 'socket.socket.connect_ex', 'socket.create_connection'):
            blocker = patch(name, side_effect=AssertionError('Live network forbidden in I3 unit tests'))
            blocker.start()
            self.addCleanup(blocker.stop)

    def write_private(self):
        self.path = self.root/'secrets.yaml'
        self.path.write_text(yaml.safe_dump(secrets(self.config)), encoding='utf-8')
        # Most tests focus on CAS/serialization, independently of platform ACL enforcement.
        for name in ('app.integrations.private_files.private_acl', 'app.integrations.google_auth.private_acl'):
            blocker = patch(name)
            blocker.start()
            self.addCleanup(blocker.stop)
        return self.path


class GoogleConfigurationTests(GoogleCase):
    def test_metadata_discovery_without_cell_authorization(self):
        raw=declaration(); raw['sheets'].update(ranges=[],discover_structure=True); raw['calendar']=None
        config=parse_google(raw)
        self.assertEqual(config.ranges,()); self.assertEqual(config.scopes,(DRIVE_SCOPE,))
        policy=ReadPolicy(config)
        url,params=policy.request('sheets.structure',config.spreadsheet_id,{})
        self.assertEqual(params['includeGridData'],'false')
        self.assertNotIn('data(',params['fields'])
        self.assertNotIn('values',params['fields'])
        with self.assertRaisesRegex(EngineError,'google_resource_denied'):
            policy.request('sheets.values',config.spreadsheet_id,{'range':"'Operacao'!A1:B2"})
        with self.assertRaisesRegex(EngineError,'google_resource_denied'):
            policy.request('calendar.events','calendar-fictional@group.calendar.google.com',
                           {'start':'2026-11-10T00:00:00-03:00','end':'2026-11-17T00:00:00-03:00'})
        with self.assertRaisesRegex(EngineError,'google_resource_denied'):
            ReadPolicy(self.config).request('sheets.structure',self.config.spreadsheet_id,{})

    def test_i2_unchanged_and_optional_google_immutable(self):
        raw = yaml.safe_load((ROOT/'config.telegram.example.yaml').read_text(encoding='utf-8'))
        self.assertIsNone(_parse_config(raw).google)
        raw['google'] = declaration()
        config = _parse_config(raw)
        self.assertEqual(config.google.scopes, (DRIVE_SCOPE, CALENDAR_SCOPE))
        with self.assertRaises(AttributeError):
            config.google.calendar_id = 'other'

    def test_drive_only_and_owned_scopes_without_redundant_sheets_scope(self):
        raw = declaration()
        raw['calendar'] = raw['sheets'] = None
        self.assertEqual(parse_google(raw).scopes, (DRIVE_SCOPE,))
        raw = declaration()
        raw['calendar']['owned'] = True
        self.assertEqual(parse_google(raw).scopes, (DRIVE_SCOPE, OWNED_SCOPE))

    def test_unsafe_configuration_rejected(self):
        changes = [lambda r:r.update(extra=True), lambda r:r.update(expected_account='invalid'),
            lambda r:r.update(drive_documents=[]), lambda r:r['drive_documents'].append(r['drive_documents'][0]),
            lambda r:r['calendar'].update(id='primary'), lambda r:r['calendar'].update(owned='true'),
            lambda r:r['calendar'].update(id='..'),
            lambda r:r['calendar'].update(window_end='2027-01-01T00:00:00Z'),
            lambda r:r['limits'].update(max_attempts=4), lambda r:r['limits'].update(max_bytes=True),
            lambda r:r['sheets'].update(ranges=['A1:B2']), lambda r:r['sheets'].update(ranges=['Operacao!A:A']),
            lambda r:r['sheets'].update(ranges=["'Operacao'!A1:Z9999"])]
        for change in changes:
            with self.subTest(change=changes.index(change)):
                raw = declaration()
                change(raw)
                with self.assertRaises(EngineError): parse_google(raw)

    def test_range_validation_and_cell_limits(self):
        self.assertEqual(a1_range("'Nome com '' aspas'!A1:B2"), 4)
        for value in ('A:A', 'A1', 'Tab!B2:A1', 'Tab!A0:B2', 'Tab!A1:B2;evil', ['Tab!A1:B2']):
            with self.assertRaises(EngineError): a1_range(value)

    def test_telegram_accepts_valid_google_and_rejects_bad_material(self):
        path = self.write_private()
        self.assertEqual(load_telegram_token(path,9009), secrets()['telegram_bot_token'])
        for bad in ({'token':'bad'}, {'client':{},'token':None}):
            raw=secrets(); raw['google_oauth']=bad
            path.write_text(yaml.safe_dump(raw),encoding='utf-8')
            with self.assertRaisesRegex(EngineError,'google_oauth_schema_invalid'): load_telegram_token(path,9009)

    def test_oauth_rejects_write_scopes_bad_endpoints_and_invalid_expiry(self):
        for change in (lambda r:r['client'].update(token_uri='https://evil.invalid/token'),
                       lambda r:r['token'].update(scopes=[DRIVE_SCOPE,'https://www.googleapis.com/auth/drive']),
                       lambda r:r['token'].update(expiry='bad'), lambda r:r['token'].update(refresh_token=None)):
            raw=secrets()['google_oauth']; change(raw)
            with self.assertRaises(EngineError) as error: validate_oauth(raw)
            self.assertNotIn(MARKER,str(error.exception))


class GoogleTransportTests(GoogleCase):
    def test_server_401_refreshes_once_and_never_loops(self):
        refresh=MagicMock(); self.http.refresh=refresh
        self.session.get.side_effect=[response(status=401),response({'ok':True})]
        self.assertTrue(self.http.read('identity','').json()['ok'])
        refresh.assert_called_once()
        refresh.reset_mock(); self.session.get.side_effect=[response(status=401),response(status=401)]
        with self.assertRaisesRegex(EngineError,'google_reauthorization_required'): self.http.read('identity','')
        refresh.assert_called_once()

    def test_unknown_resource_mutations_and_arbitrary_urls_never_authenticate(self):
        for op, resource, args in [('drive.metadata','other',{}), ('drive.delete','doc-fictional',{}),
            ('POST','doc-fictional',{}), ('drive.metadata','https://evil.invalid',{}),
            ('sheets.values','sheet-fictional',{'range':"'Other'!A1:B2"}),
            ('calendar.events',self.config.calendar_id,{'start':'2026-10-01T00:00:00Z','end':'2026-11-02T00:00:00Z'})]:
            with self.assertRaises(EngineError): self.http.read(op,resource,**args)
        self.bearer.assert_not_called(); self.session.get.assert_not_called()

    def test_live_flag_precedes_authentication_and_network(self):
        self.http.allow_live=False
        with self.assertRaisesRegex(EngineError,'live_google_authorization_required'):
            self.http.read('drive.metadata','doc-fictional')
        self.bearer.assert_not_called()

    def test_get_only_fixed_hosts_no_redirects_logs_no_content(self):
        self.session.get.return_value=response({'id':'doc-fictional'})
        with self.assertLogs('alfredo.google',level='INFO') as capture:
            value=self.http.read('drive.metadata','doc-fictional').json()
        self.assertEqual(value['id'],'doc-fictional')
        args=self.session.get.call_args
        self.assertTrue(args.args[0].startswith('https://www.googleapis.com/drive/'))
        self.assertFalse(args.kwargs['allow_redirects'])
        self.assertNotIn(MARKER,' '.join(capture.output)); self.assertNotIn('doc-fictional',' '.join(capture.output))
        self.assertEqual(self.http.calls[0]['method'],'GET')

    def test_denied_missing_invalid_auth_and_redirect_are_not_retried(self):
        for status,code in [(403,'google_access_denied'),(404,'google_not_found_or_inaccessible'),
                            (401,'google_reauthorization_required'),(302,'google_redirect_denied')]:
            self.session.reset_mock(); self.session.get.return_value=response({'error':{'message':MARKER}},status)
            with self.assertRaisesRegex(EngineError,code) as error: self.http.read('drive.metadata','doc-fictional')
            self.assertEqual(self.session.get.call_count,1)
            self.assertNotIn(MARKER,str(error.exception))

    def test_retry_after_and_transient_retry_limit(self):
        sleeps=[]; self.http.sleep=sleeps.append
        self.session.get.side_effect=[response(status=429,headers={'Retry-After':'2'}),response({'ok':True})]
        self.assertTrue(self.http.read('identity','').json()['ok'])
        self.assertEqual(sleeps,[2.0])
        self.session.get.side_effect=[response(status=503) for _ in range(3)]
        with self.assertRaisesRegex(EngineError,'google_service_unavailable'): self.http.read('identity','')

    def test_forbidden_rate_limit_is_retryable_but_permission_is_not(self):
        self.session.get.side_effect=[response({'error':{'errors':[{'reason':'userRateLimitExceeded'}]}},403),response({'ok':True})]
        self.assertTrue(self.http.read('identity','').json()['ok'])

    def test_network_error_is_sanitized_and_bounded(self):
        import requests
        self.session.get.side_effect=requests.ConnectionError(MARKER)
        with self.assertRaisesRegex(EngineError,'google_transport_error') as error: self.http.read('identity','')
        self.assertEqual(self.session.get.call_count,3); self.assertNotIn(MARKER,str(error.exception))

    def test_response_byte_limit_closes_response(self):
        obj=response(b'x'*(self.config.max_bytes+1)); self.session.get.return_value=obj
        with self.assertRaisesRegex(EngineError,'google_response_limit'): self.http.read('identity','')
        obj.close.assert_called_once()

    def test_global_deadline_and_large_retry_after(self):
        self.http.started=self.http.clock()-100
        with self.assertRaisesRegex(EngineError,'google_deadline_exceeded'): self.http.read('identity','')
        self.bearer.assert_not_called()
        self.http.started=self.http.clock()
        self.session.get.return_value=response(status=429,headers={'Retry-After':'999'})
        with self.assertRaisesRegex(EngineError,'google_deadline_exceeded'): self.http.read('identity','')

    def test_invalid_json_cannot_echo_provider_body(self):
        with self.assertRaises(EngineError) as error: Payload(MARKER.encode()).json()
        self.assertNotIn(MARKER,str(error.exception))


class GoogleAdapterTests(GoogleCase):
    def test_structure_returns_only_tab_properties_not_any_cells(self):
        raw=declaration(); raw['sheets'].update(ranges=[],discover_structure=True)
        config=parse_google(raw)
        http=GoogleHTTP(config,self.bearer,allow_live=True,session=self.session)
        self.session.get.return_value=response({'spreadsheetId':'sheet-fictional','sheets':[{
            'properties':{'sheetId':0,'title':'Operacao','sheetType':'GRID','gridProperties':{'rowCount':1000,'columnCount':26}},
            'data':[{'rowData':[MARKER]}]}]})
        tabs=Sheets(config,http).read_structure(config.spreadsheet_id)
        self.assertEqual(tabs['tabs'][0]['gridProperties']['rowCount'],1000)
        self.assertNotIn(MARKER,json.dumps(tabs)); self.assertNotIn('data',tabs['tabs'][0])

    def test_drive_reads_bytes_and_version_without_cache(self):
        self.session.get.side_effect=[response(metadata()),response(b'hello'),response(metadata())]
        result=Drive(self.config,self.http).read_document('doc-fictional')
        self.assertEqual(result.content,b'hello'); self.assertEqual(result.source_version,'1')
        self.assertNotIn('hello',repr(result)); self.assertEqual(list(self.root.iterdir()),[])

    def test_google_doc_export_uses_declared_format(self):
        data=metadata(mimeType='application/vnd.google-apps.document'); data.pop('size')
        self.session.get.side_effect=[response(data),response(b'hello'),response(data)]
        result=Drive(self.config,self.http).read_document('doc-fictional')
        self.assertEqual(result.mime_type,'text/plain')
        self.assertTrue(self.session.get.call_args_list[1].args[0].endswith('/export'))

    def test_drive_mutation_during_read_denies_current_version_claim(self):
        self.session.get.side_effect=[response(metadata()),response(b'hello'),response(metadata(version='2'))]
        with self.assertRaisesRegex(EngineError,'google_document_changed_during_read'):
            Drive(self.config,self.http).read_document('doc-fictional')

    def test_download_denied_shortcut_unsupported_or_empty(self):
        for data,code in [(metadata(capabilities={'canDownload':False}),'google_download_denied'),
                          (metadata(mimeType='application/vnd.google-apps.shortcut'),'google_document_format_unsupported'),
                          (metadata(trashed=True),'google_document_metadata_invalid')]:
            self.session.get.side_effect=None; self.session.get.return_value=response(data)
            with self.assertRaisesRegex(EngineError,code): Drive(self.config,self.http).read_document('doc-fictional')
        self.session.get.side_effect=[response(metadata()),response(b'')]
        with self.assertRaisesRegex(EngineError,'google_document_empty'): Drive(self.config,self.http).read_document('doc-fictional')

    def test_calendar_complete_pagination_and_empty_success(self):
        event={'id':'event-fictional','start':{'date':'2026-11-10'},'end':{'date':'2026-11-11'},'summary':MARKER}
        self.session.get.side_effect=[response({'accessRole':'reader','items':[event],'nextPageToken':'page2'}),
                                       response({'accessRole':'reader','items':[],'timeZone':'America/Sao_Paulo'})]
        result=Calendar(self.config,self.http).read_events(self.config.calendar_id,self.config.window_start,self.config.window_end)
        self.assertEqual(len(result['events']),1); self.assertNotIn('summary',result['events'][0])
        self.session.get.side_effect=None; self.session.get.return_value=response({'accessRole':'reader','items':[]})
        self.assertEqual(Calendar(self.config,self.http).read_events(self.config.calendar_id,self.config.window_start,self.config.window_end)['events'],[])

    def test_calendar_pagination_overflow_and_loops_are_failures(self):
        self.session.get.return_value=response({'accessRole':'reader','items':[],'nextPageToken':'again'})
        with self.assertRaisesRegex(EngineError,'google_pagination_invalid'):
            Calendar(self.config,self.http).read_events(self.config.calendar_id,self.config.window_start,self.config.window_end)
        self.session.get.side_effect=[response({'accessRole':'reader','items':[],'nextPageToken':str(n)}) for n in range(2)]
        with self.assertRaisesRegex(EngineError,'google_pagination_limit'):
            Calendar(self.config,self.http).read_events(self.config.calendar_id,self.config.window_start,self.config.window_end)

    def test_sheets_metadata_bounded_values_and_empty(self):
        self.session.get.side_effect=[response({'spreadsheetId':'sheet-fictional','sheets':[]}),response({'values':[[1,2],[3,4]]}),response({})]
        adapter=Sheets(self.config,self.http)
        adapter.read_metadata('sheet-fictional')
        self.assertEqual(adapter.read_range('sheet-fictional',self.config.ranges[0]),[[1,2],[3,4]])
        self.assertEqual(adapter.read_range('sheet-fictional',self.config.ranges[0]),[])

    def test_sheets_overflow_is_not_presented_as_complete(self):
        self.session.get.return_value=response({'values':[[1,2,3],[4,5]]})
        with self.assertRaisesRegex(EngineError,'google_response_limit'):
            Sheets(self.config,self.http).read_range('sheet-fictional',self.config.ranges[0])


class GoogleAuthTests(GoogleCase):
    def test_transient_refresh_does_not_request_new_consent(self):
        from google.auth.exceptions import RefreshError, TransportError
        path=self.write_private(); before=path.read_bytes()
        for failure in (RefreshError(MARKER,retryable=True),TransportError(MARKER)):
            with patch('google.oauth2.credentials.Credentials.refresh',side_effect=failure):
                with self.assertRaisesRegex(EngineError,'google_auth_temporary_error'):
                    GoogleAuth(self.config,path,allow_live=True).bearer(force_refresh=True)
        self.assertEqual(path.read_bytes(),before)

    def test_auth_requires_explicit_live_flag(self):
        auth=GoogleAuth(self.config,self.root/'missing')
        with self.assertRaisesRegex(EngineError,'live_google_authorization_required'): auth.bearer()

    def test_valid_credentials_reload_and_i2_coexist(self):
        path=self.write_private(); before=path.read_bytes()
        for _ in range(2): self.assertEqual(GoogleAuth(self.config,path,allow_live=True).bearer(),MARKER)
        self.assertEqual(path.read_bytes(),before)
        self.assertEqual(load_telegram_token(path,9009),secrets()['telegram_bot_token'])

    def test_wrong_account_or_scope_denied_before_refresh(self):
        path=self.write_private()
        for key,value in [('account','other@example.invalid'),('scopes',[DRIVE_SCOPE])]:
            raw=secrets(); raw['google_oauth']['token'][key]=value
            path.write_text(yaml.safe_dump(raw),encoding='utf-8')
            with patch('google.oauth2.credentials.Credentials.refresh') as refresh:
                with self.assertRaises(EngineError): GoogleAuth(self.config,path,allow_live=True).bearer()
                refresh.assert_not_called()

    def test_real_library_refresh_persists_and_preserves_telegram(self):
        path=self.write_private(); before=secrets()['telegram_bot_token']
        def refreshed(credentials, request):
            credentials.token='NEW_ACCESS'; credentials.expiry=datetime(2099,2,1)
        with patch('google.oauth2.credentials.Credentials.refresh',new=refreshed):
            auth=GoogleAuth(self.config,path,allow_live=True)
            self.assertEqual(auth.bearer(force_refresh=True),'NEW_ACCESS')
        self.assertEqual(GoogleAuth(self.config,path,allow_live=True).bearer(),'NEW_ACCESS')
        self.assertEqual(load_telegram_token(path,9009),before)

    def test_invalid_grant_blocks_without_rewriting(self):
        from google.auth.exceptions import RefreshError
        path=self.write_private(); before=path.read_bytes()
        with patch('google.oauth2.credentials.Credentials.refresh',side_effect=RefreshError(MARKER)):
            with self.assertRaisesRegex(EngineError,'google_reauthorization_required') as error:
                GoogleAuth(self.config,path,allow_live=True).bearer(force_refresh=True)
        self.assertEqual(path.read_bytes(),before); self.assertNotIn(MARKER,str(error.exception))

    def test_sdk_generates_pkce_and_rejects_wrong_state_before_network(self):
        from google_auth_oauthlib.flow import InstalledAppFlow
        flow=InstalledAppFlow.from_client_config({'installed':secrets()['google_oauth']['client']},
                    scopes=list(self.config.scopes),redirect_uri='http://127.0.0.1:50000/',autogenerate_code_verifier=True)
        with quiet_oauth_logs(): url,state=flow.authorization_url()
        args=parse_qs(urlsplit(url).query)
        self.assertEqual(args['code_challenge_method'],['S256']); self.assertGreaterEqual(len(flow.code_verifier),43)
        with patch.object(flow.oauth2session,'request') as request:
            with self.assertRaises(Exception):
                flow.fetch_token(authorization_response='https://127.0.0.1:50000/?state=wrong&code=FAKE')
            request.assert_not_called()

    def test_consent_uses_loopback_and_checks_identity_before_saving(self):
        path=self.write_private(); before=path.read_bytes()
        credentials=MagicMock(token='NEW_ACCESS',refresh_token='NEW_REFRESH',expiry=datetime(2099,1,1),
                              scopes=list(self.config.scopes),granted_scopes=list(self.config.scopes))
        identity=MagicMock(); identity.read.return_value.json.return_value={'user':{'emailAddress':'other@example.invalid'}}
        with patch('app.integrations.google_auth.import_desktop_client',return_value=secrets()['google_oauth']['client']), \
             patch('google_auth_oauthlib.flow.InstalledAppFlow.run_local_server',return_value=credentials) as run, \
             patch('app.integrations.google_http.GoogleHTTP',return_value=identity):
            with self.assertRaisesRegex(EngineError,'google_account_mismatch'):
                GoogleAuth(self.config,path,allow_live=True).enroll(self.root/'fake.json')
        self.assertEqual(path.read_bytes(),before)
        self.assertEqual(run.call_args.kwargs['host'],'127.0.0.1')
        self.assertEqual(run.call_args.kwargs['authorization_prompt_message'],'')

    def test_consent_success_and_partial_scope_failure(self):
        path=self.write_private()
        credentials=MagicMock(token='NEW_ACCESS',refresh_token='NEW_REFRESH',expiry=datetime(2099,1,1),
                              scopes=list(self.config.scopes),granted_scopes=list(self.config.scopes))
        identity=MagicMock(); identity.read.return_value.json.return_value={'user':{'emailAddress':self.config.expected_account}}
        with patch('app.integrations.google_auth.import_desktop_client',return_value=secrets()['google_oauth']['client']), \
             patch('google_auth_oauthlib.flow.InstalledAppFlow.run_local_server',return_value=credentials), \
             patch('app.integrations.google_http.GoogleHTTP',return_value=identity):
            GoogleAuth(self.config,path,allow_live=True).enroll(self.root/'fake.json')
        self.assertEqual(load_enrollment_secrets(path)['google_oauth']['token']['access_token'],'NEW_ACCESS')
        credentials.granted_scopes=[DRIVE_SCOPE]
        with self.assertRaisesRegex(EngineError,'google_scope_mismatch'): credential_record(credentials,self.config)


class PrivatePersistenceTests(GoogleCase):
    def test_native_private_acl_atomic_replace_and_fresh_process_reload(self):
        # Real platform ACLs and a fresh Python process, using fictitious tokens only.
        path=self.root/'secrets.yaml'
        path.write_text(yaml.safe_dump(secrets()),encoding='utf-8')
        if os.name=='nt':
            script="""
$ErrorActionPreference='Stop'
$acl=New-Object System.Security.AccessControl.FileSecurity
$acl.SetAccessRuleProtection($true,$false)
$user=[System.Security.Principal.WindowsIdentity]::GetCurrent().User
foreach ($sid in @($user,[System.Security.Principal.SecurityIdentifier]::new('S-1-5-18'))) {
  $rule=[System.Security.AccessControl.FileSystemAccessRule]::new($sid,'FullControl','Allow')
  $acl.AddAccessRule($rule)
}
Set-Acl -LiteralPath $env:ALFREDO_TEST_PRIVATE -AclObject $acl
"""
            env=os.environ.copy(); env['ALFREDO_TEST_PRIVATE']=str(path)
            result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],env=env,capture_output=True,timeout=15,creationflags=subprocess.CREATE_NO_WINDOW)
            self.assertEqual(result.returncode,0,'Failed to prepare private fictitious test file')
        else:
            os.chmod(path,0o600)
        private_acl(path)
        before=path.read_bytes(); raw=secrets(); raw['google_oauth']['token']['access_token']='PERSISTED_FAKE_ACCESS'
        with private_lock(path): atomic_yaml(path,before,raw,lambda r:validate_oauth(r['google_oauth']))
        private_acl(path)
        code="from tests.test_google import declaration; from app.integrations.google_config import parse_google; from app.integrations.google_auth import GoogleAuth; import sys; token=GoogleAuth(parse_google(declaration()),sys.argv[1],allow_live=True).bearer(); print('persisted' if token=='PERSISTED_FAKE_ACCESS' else 'failed')"
        result=subprocess.run([sys.executable,'-B','-c',code,str(path)],cwd=ROOT,capture_output=True,text=True,timeout=40)
        self.assertEqual(result.returncode,0,'Fresh process failed on fictitious credentials: '+result.stderr[-1200:])
        self.assertEqual(result.stdout.strip(),'persisted')
        self.assertNotIn(MARKER,result.stdout+result.stderr)

    def test_atomic_interruption_preserves_old_file_and_removes_temporary(self):
        path=self.write_private(); before=path.read_bytes(); raw=secrets(); raw['google_oauth']['token']['access_token']='NEW_ACCESS'
        with private_lock(path), patch('app.integrations.private_files.os.replace',side_effect=OSError(MARKER)):
            with self.assertRaisesRegex(EngineError,'private_write_unavailable'):
                atomic_yaml(path,before,raw,lambda r:validate_oauth(r['google_oauth']))
        self.assertEqual(path.read_bytes(),before); self.assertEqual(list(self.root.glob('*.tmp')),[])

    def test_compare_and_swap_rejects_concurrent_change(self):
        path=self.write_private(); before=path.read_bytes(); path.write_text('# concurrent\n'+before.decode(),encoding='utf-8')
        with self.assertRaisesRegex(EngineError,'configuration_changed_during_enrollment'):
            atomic_yaml(path,before,secrets(),lambda r:None)
        self.assertTrue(path.read_bytes().startswith(b'# concurrent'))

    def test_second_writer_is_denied(self):
        path=self.write_private()
        with private_lock(path):
            with self.assertRaisesRegex(EngineError,'private_write_unavailable'):
                with private_lock(path): self.fail('Second writer entered')

    def test_unprotected_acl_refused_before_private_write(self):
        path=self.root/'secret.yaml'; path.write_text('fictitious',encoding='utf-8')
        if os.name!='nt': os.chmod(path,0o644)
        with self.assertRaisesRegex(EngineError,'private_acl_unsafe'): private_acl(path)


class GoogleDiagnosticsTests(GoogleCase):
    def test_downloaded_client_selection_is_project_bound_and_original_untouched(self):
        self.write_private()
        downloads=self.root/'Downloads'; downloads.mkdir()
        source=downloads/'client_secret_original.json'
        data=json.dumps({'installed':secrets()['google_oauth']['client']}).encode()
        source.write_bytes(data)
        other=deepcopy(secrets()['google_oauth']['client']); other['project_id']='other-project'
        (downloads/'client_secret_other.json').write_text(json.dumps({'installed':other}),encoding='utf-8')
        with patch('scripts.setup_google_i3.private_acl') as protect:
            target=stage_downloaded_client(downloads,'fictional',self.root)
        self.assertEqual(target.read_bytes(),data); self.assertEqual(source.read_bytes(),data)
        self.assertTrue(protect.called)
        self.assertNotIn(MARKER,str(target))

    def test_different_matching_desktop_clients_require_disambiguation(self):
        self.write_private(); downloads=self.root/'Downloads'; downloads.mkdir()
        for n in range(2):
            client=deepcopy(secrets()['google_oauth']['client']); client['client_id']=str(n)+'.apps.googleusercontent.com'
            (downloads/('client_secret_'+str(n)+'.json')).write_text(json.dumps({'installed':client}),encoding='utf-8')
        with self.assertRaisesRegex(EngineError,'google_desktop_client_not_unique'):
            stage_downloaded_client(downloads,'fictional',self.root)
        self.assertFalse((self.root/'client_secret_i3_desktop.json').exists())

    def test_metadata_only_never_reads_cells_or_approves_complete_i3(self):
        self.write_private()
        raw=yaml.safe_load((ROOT/'config.telegram.example.yaml').read_text(encoding='utf-8'))
        raw['google']=declaration(); raw['google']['sheets'].update(ranges=[],discover_structure=True)
        (self.root/'config.yaml').write_text(yaml.safe_dump(raw),encoding='utf-8')
        fake=MagicMock(); fake.calls=[]
        fake.read.return_value.json.return_value={'user':{'emailAddress':self.config.expected_account}}
        doc=MagicMock(content=b'hello',sha256='a'*64,source_version='1',classification='official',mime_type='text/plain')
        with patch('scripts.check_google_i3.private_acl'),patch('scripts.check_google_i3.GoogleAuth'), \
             patch('scripts.check_google_i3.GoogleHTTP',return_value=fake), \
             patch('scripts.check_google_i3.Drive') as drive,patch('scripts.check_google_i3.Calendar') as calendar, \
             patch('scripts.check_google_i3.Sheets') as sheets:
            drive.return_value.read_document.return_value=doc
            calendar.return_value.read_events.return_value={'events':[],'complete':True}
            sheets.return_value.read_structure.return_value={'tabs':[],'named_ranges':[]}
            report=check(self.root,allow_live=True,verify_refresh=True)
        sheets.return_value.read_range.assert_not_called()
        self.assertEqual(report['sheets']['result'],'metadata_only')
        self.assertEqual(report['acceptance'],'pending')
        self.assertFalse(report['sheets_structure']['cells_read'])

    def test_existing_google_does_not_break_telegram_checker(self):
        from scripts.check_telegram_i2 import check as check_telegram
        self.write_private()
        raw=yaml.safe_load((ROOT/'config.telegram.example.yaml').read_text(encoding='utf-8')); raw['google']=declaration()
        (self.root/'config.yaml').write_text(yaml.safe_dump(raw),encoding='utf-8')
        report=check_telegram(self.root)
        self.assertEqual(report['local_configuration'],'passed')
        self.assertEqual(report['local_token'],'passed')
        self.assertFalse(report['external_api_attempted'])

    def test_missing_config_no_api_and_no_database(self):
        (self.root/'config.yaml').write_bytes((ROOT/'config.telegram.example.yaml').read_bytes())
        with patch('scripts.check_google_i3.GoogleHTTP') as http:
            report=check(self.root,allow_live=True)
        self.assertEqual(report['reason'],'google_not_configured'); http.assert_not_called()
        self.assertFalse(report['database_opened'])

    def test_offline_check_never_opens_transport(self):
        self.write_private()
        raw=yaml.safe_load((ROOT/'config.telegram.example.yaml').read_text(encoding='utf-8')); raw['google']=declaration()
        (self.root/'config.yaml').write_text(yaml.safe_dump(raw),encoding='utf-8')
        with patch('scripts.check_google_i3.private_acl'),patch('scripts.check_google_i3.GoogleHTTP') as http:
            report=check(self.root)
        self.assertEqual(report['local_credentials'],'passed'); http.assert_not_called()
        self.assertEqual(report['acceptance'],'blocked')

    def test_full_fake_read_evidence_is_redacted_and_requires_all_services(self):
        self.write_private()
        raw=yaml.safe_load((ROOT/'config.telegram.example.yaml').read_text(encoding='utf-8')); raw['google']=declaration()
        (self.root/'config.yaml').write_text(yaml.safe_dump(raw),encoding='utf-8')
        fake=MagicMock(); fake.calls=[]
        fake.read.return_value.json.return_value={'user':{'emailAddress':self.config.expected_account}}
        doc=MagicMock(content=b'hello',sha256='a'*64,source_version='1',classification='official',mime_type='text/plain')
        with patch('scripts.check_google_i3.private_acl'), patch('scripts.check_google_i3.GoogleAuth'), \
             patch('scripts.check_google_i3.GoogleHTTP',return_value=fake), \
             patch('scripts.check_google_i3.Drive') as drive,patch('scripts.check_google_i3.Calendar') as calendar, \
             patch('scripts.check_google_i3.Sheets') as sheets:
            drive.return_value.read_document.return_value=doc
            calendar.return_value.read_events.return_value={'events':[],'complete':True}
            sheets.return_value.read_range.return_value=[[MARKER]]
            report=check(self.root,allow_live=True,verify_refresh=True)
        self.assertEqual(report['acceptance'],'passed_google_reads')
        self.assertNotIn(MARKER,json.dumps(report)); self.assertNotIn(self.config.expected_account,json.dumps(report))
        self.assertFalse(report['google_mutations_attempted']); self.assertFalse(report['database_opened'])

    def test_configure_requires_owner_confirmation_and_preserves_i2(self):
        path=self.root/'config.yaml'; path.write_bytes((ROOT/'config.telegram.example.yaml').read_bytes()); before=path.read_bytes()
        answers=['alfredo@example.invalid','doc-fictional','official','text/plain','','','','NO']
        with patch('builtins.input',side_effect=answers),redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(EngineError,'google_resource_authorization_not_confirmed'): configure(self.root)
        self.assertEqual(path.read_bytes(),before)

    def test_authorize_requires_terminal_and_live_flag(self):
        with self.assertRaisesRegex(EngineError,'live_google_authorization_required'): authorize(self.root)


if __name__=='__main__': unittest.main()
