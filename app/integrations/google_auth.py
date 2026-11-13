"""OAuth Desktop: explicit browser consent, exact scopes, private token persistence."""
from datetime import datetime, timezone
from contextlib import contextmanager
import json
import logging
from pathlib import Path
import time
from app.config.schema import load_enrollment_secrets, read_configuration_bytes
from app.core.contracts import EngineError, stamp
from app.integrations.google_config import TOKEN_URI, validate_oauth, validate_binding
from app.integrations.private_files import private_lock, atomic_yaml, private_acl


@contextmanager
def quiet_oauth_logs():
    # SDK DEBUG logs can contain bearer headers, token responses and callback codes.
    names = [name for name in logging.Logger.manager.loggerDict
             if name.startswith(('google.', 'google_auth_oauthlib.', 'requests_oauthlib.', 'oauthlib.', 'urllib3.'))]
    loggers = [(logging.getLogger(name), logging.getLogger(name).disabled) for name in names]
    try:
        for logger, _ in loggers:
            logger.disabled = True
        yield
    finally:
        for logger, disabled in loggers:
            logger.disabled = disabled


def libraries():
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        return Credentials, InstalledAppFlow, Request
    except ImportError:
        raise EngineError('google_dependencies_missing') from None


def credential_record(credentials, config):
    scopes = credentials.granted_scopes
    if scopes is None:
        scopes = credentials.scopes
    if scopes is None or set(scopes) != set(config.scopes):
        raise EngineError('google_scope_mismatch')
    if not credentials.refresh_token or not credentials.expiry:
        raise EngineError('google_reauthorization_required')
    expiry = credentials.expiry
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    return {'access_token': credentials.token, 'refresh_token': credentials.refresh_token,
            'expiry': stamp(expiry), 'scopes': list(config.scopes), 'account': config.expected_account}


def import_desktop_client(path):
    """Read local downloaded JSON only; caller supplies path in a local hidden prompt."""
    private_acl(path)
    try:
        raw = json.loads(read_configuration_bytes(path))
        if type(raw) is not dict or set(raw) != {'installed'}:
            raise EngineError('google_desktop_client_required')
        client = raw['installed']
        if type(client) is not dict:
            raise EngineError('google_desktop_client_required')
        client = {key: client[key] for key in ('client_id', 'client_secret', 'project_id', 'auth_uri', 'token_uri')}
        validate_oauth({'client': client, 'token': None})
        return client
    except (ValueError, KeyError, TypeError):
        raise EngineError('google_desktop_client_invalid') from None


class GoogleAuth:
    def __init__(self, config, secrets_path, *, allow_live=False):
        if config is None:
            raise EngineError('google_not_configured')
        self.config, self.path = config, Path(secrets_path)
        self.allow_live = allow_live
        self.refresh_count = 0

    def require_live(self):
        if self.allow_live is not True:
            raise EngineError('live_google_authorization_required')

    def bearer(self, *, force_refresh=False):
        """Refresh under lock and persist BEFORE returning a bearer to a data request."""
        self.require_live()
        Credentials, _, Request = libraries()
        from google.auth.exceptions import GoogleAuthError, TransportError, RefreshError
        import requests
        with private_lock(self.path):
            before = read_configuration_bytes(self.path)
            raw = load_enrollment_secrets(self.path)
            oauth = raw['google_oauth']
            validate_binding(oauth, self.config)
            client, token = oauth['client'], oauth['token']
            expiry = datetime.fromisoformat(token['expiry']).astimezone(timezone.utc).replace(tzinfo=None)
            credentials = Credentials(token=token['access_token'], refresh_token=token['refresh_token'],
                                      token_uri=TOKEN_URI, client_id=client['client_id'],
                                      client_secret=client['client_secret'], scopes=list(self.config.scopes), expiry=expiry)
            if force_refresh or not credentials.valid:
                session = requests.Session()
                session.trust_env = False
                deadline = time.monotonic() + self.config.total_seconds
                request = Request(session=session)
                attempts = 0
                def bounded_request(*args, **kwargs):
                    nonlocal attempts
                    attempts += 1
                    if attempts > self.config.max_attempts:
                        raise EngineError('google_auth_temporary_error')
                    remaining = deadline-time.monotonic()
                    if remaining <= 0:
                        raise EngineError('google_deadline_exceeded')
                    if kwargs.get('url', args[0] if args else None) != TOKEN_URI:
                        raise EngineError('google_endpoint_denied')
                    kwargs['timeout'] = min(self.config.timeout_seconds, remaining)
                    kwargs['allow_redirects'] = False
                    return request(*args, **kwargs)
                try:
                    with quiet_oauth_logs():
                        credentials.refresh(bounded_request)
                    oauth['token'] = credential_record(credentials, self.config)
                    atomic_yaml(self.path, before, raw, validate_secret_document)
                    self.refresh_count += 1
                except EngineError:
                    raise
                except TransportError:
                    raise EngineError('google_auth_temporary_error') from None
                except RefreshError as error:
                    raise EngineError('google_auth_temporary_error' if error.retryable else 'google_reauthorization_required') from None
                except GoogleAuthError:
                    raise EngineError('google_reauthorization_required') from None
                except requests.RequestException:
                    raise EngineError('google_auth_temporary_error') from None
                except (ValueError, KeyError, TypeError):
                    raise EngineError('google_auth_response_invalid') from None
                finally:
                    session.close()
            return credentials.token

    def enroll(self, client_path, *, consent_timeout_seconds=180):
        """No account password, code, URL or token is printed by this application."""
        self.require_live()
        if type(consent_timeout_seconds) is not int or not 30 <= consent_timeout_seconds <= 1800:
            raise EngineError('google_consent_timeout_invalid')
        _, InstalledAppFlow, _ = libraries()
        client = import_desktop_client(client_path)
        # Snapshot before browser interaction; concurrent changes are never overwritten.
        private_acl(self.path)
        before = read_configuration_bytes(self.path)
        raw = load_enrollment_secrets(self.path)
        with quiet_oauth_logs():
            flow = InstalledAppFlow.from_client_config(
                {'installed': {**client, 'redirect_uris': ['http://127.0.0.1']}},
                scopes=list(self.config.scopes), autogenerate_code_verifier=True)
        flow.oauth2session.trust_env = False
        original_request = flow.oauth2session.request
        def consent_request(method, url, **kwargs):
            if method.upper() != 'POST' or url != TOKEN_URI:
                raise EngineError('google_endpoint_denied')
            kwargs['timeout'] = self.config.timeout_seconds
            kwargs['allow_redirects'] = False
            return original_request(method, url, **kwargs)
        flow.oauth2session.request = consent_request
        stage = 'browser_consent'
        try:
            with quiet_oauth_logs():
                credentials = flow.run_local_server(
                    host='127.0.0.1', bind_addr='127.0.0.1', port=0, open_browser=True,
                    timeout_seconds=consent_timeout_seconds, authorization_prompt_message='',
                    success_message='Autorizacao recebida. Feche esta janela e volte ao terminal do Alfredo.',
                    access_type='offline', prompt='consent select_account',
                    login_hint=self.config.expected_account)
            stage = 'credential_validation'
            record = credential_record(credentials, self.config)
            # Verify actual identity with the newly issued token BEFORE persistence.
            from app.integrations.google_http import GoogleHTTP
            stage = 'identity_verification'
            http = GoogleHTTP(self.config, lambda: credentials.token, allow_live=True)
            try:
                identity = http.read('identity', '').json()
            finally:
                http.close()
            if identity.get('user', {}).get('emailAddress', '').casefold() != self.config.expected_account:
                raise EngineError('google_account_mismatch')
            raw['google_oauth'] = {'client': client, 'token': record}
            stage = 'private_persistence'
            with private_lock(self.path):
                atomic_yaml(self.path, before, raw, validate_secret_document)
        except EngineError as error:
            error.diagnostic = {'stage':stage}
            raise
        except Exception as error:
            # SDK exceptions may include codes/URLs; none may cross our boundary.
            failure = EngineError('google_oauth_consent_failed')
            safe_types = {'AttributeError','TimeoutError','OSError','Warning','ValueError','ConnectionError'}
            failure.diagnostic = {'stage':stage,'exception_type':type(error).__name__
                                  if type(error).__name__ in safe_types else 'provider_exception'}
            raise failure from None
        finally:
            flow.oauth2session.close()


def validate_secret_document(raw):
    from app.config.schema import keys, validate_telegram_token
    keys(raw, ('telegram_bot_token', 'openai_api_key', 'google_oauth'))
    from app.ai.configuration import validate_api_key
    validate_api_key(raw['openai_api_key'])
    if raw['telegram_bot_token'] is not None:
        validate_telegram_token(raw['telegram_bot_token'])
    validate_oauth(raw['google_oauth'])
