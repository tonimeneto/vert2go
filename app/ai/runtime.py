"""Explicitly gated composition of the existing Google reader and I4 OpenAI adapter."""
from contextlib import contextmanager
from app.core.contracts import EngineError


class FreshDrive:
    def __init__(self, config, secrets_path):
        self.config, self.secrets_path = config, secrets_path
        self.request_count = 0

    def read_document(self, source_id):
        from app.integrations.drive import Drive
        from app.integrations.google_auth import GoogleAuth
        from app.integrations.google_http import GoogleHTTP
        auth = GoogleAuth(self.config.google,self.secrets_path,allow_live=True)
        http = GoogleHTTP(self.config.google,auth.bearer,allow_live=True,
                          refresh=lambda:auth.bearer(force_refresh=True))
        try:
            return Drive(self.config.google,http).read_document(source_id)
        finally:
            self.request_count += len(http.calls)
            http.close()


@contextmanager
def knowledge_runtime(config, store, secrets_path, *, allow_live=False, telegram=False):
    if config.knowledge is None:
        raise EngineError('knowledge_not_configured')
    config.knowledge.require_consent(telegram=telegram)
    if allow_live is not True:
        raise EngineError('live_openai_authorization_required')
    from app.ai.configuration import load_api_key
    from app.ai.openai_http import OpenAIHTTP
    from app.services.knowledge import Knowledge
    provider = OpenAIHTTP(config.knowledge,load_api_key(secrets_path),allow_live=True)
    try:
        service = Knowledge(config,store,FreshDrive(config,secrets_path),provider)
        service.startup()
        yield service
    finally:
        provider.close()
