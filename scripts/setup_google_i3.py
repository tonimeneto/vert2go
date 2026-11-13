"""Local owner enrollment. Never accepts a token/client secret as a CLI argument."""
import argparse
from copy import deepcopy
import getpass
import json
import os
from fnmatch import fnmatch
from pathlib import Path
import sys
import warnings

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.config.schema import _parse_config, load_config, read_yaml, read_configuration_bytes
from app.core.contracts import EngineError
from app.integrations.google_auth import GoogleAuth
from app.integrations.google_config import parse_google, validate_oauth
from app.integrations.private_files import atomic_yaml, private_lock, private_acl, no_links

DEFAULT_LIMITS = {'timeout_seconds': 20, 'total_seconds': 120, 'max_attempts': 3,
                  'max_pages': 5, 'max_bytes': 10485760, 'max_cells': 1000}


def stage_downloaded_client(downloads, expected_project, root=ROOT):
    """Read only likely OAuth downloads; stage exactly one matching Desktop client privately.

    Original Downloads files are read-only. Never return their contents or values to logs.
    Caller must have the owner's explicit authorization to locate the downloaded client.
    """
    downloads = no_links(downloads)
    matches = []
    for candidate in downloads.iterdir():
        if not candidate.is_file() or not any(fnmatch(candidate.name, pattern) for pattern in
                                              ('client_secret*.json', 'credentials*.json', '*oauth*.json')):
            continue
        no_links(candidate)
        try:
            data = read_configuration_bytes(candidate)
            source = json.loads(data)
            if type(source) is not dict or set(source) != {'installed'} or type(source['installed']) is not dict:
                continue
            client = source['installed']
            if client.get('project_id') != expected_project:
                continue
            validate_oauth({'client': {k: client[k] for k in
                           ('client_id','client_secret','project_id','auth_uri','token_uri')}, 'token': None})
            if data not in matches:
                matches.append(data)
        except (EngineError, ValueError, TypeError, KeyError):
            continue
    if len(matches) != 1:
        raise EngineError('google_desktop_client_not_unique' if matches else 'google_matching_desktop_client_not_found')
    target = no_links(root/'client_secret_i3_desktop.json')
    data = matches[0]
    if target.exists():
        private_acl(root/'secrets.yaml', target)
        if read_configuration_bytes(target) != data:
            raise EngineError('google_existing_client_conflict')
        return target
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'wb') as handle:
            private_acl(root/'secrets.yaml', target)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        private_acl(target)
        return target
    except Exception:
        target.unlink(missing_ok=True)
        raise EngineError('google_client_staging_failed') from None


def configure(root=ROOT):
    path = root/'config.yaml'
    before = read_configuration_bytes(path)
    raw = deepcopy(read_yaml(path))
    _parse_config(raw)
    email = input('Conta Google experimental autorizada (email): ').strip()
    docs = []
    print('Cadastre somente IDs de arquivos expressamente autorizados. Linha vazia encerra.')
    while True:
        file_id = input('ID do documento Drive: ').strip()
        if not file_id:
            break
        classification = input('Classificacao (official/authorized_operational/simulation/unverified): ').strip()
        export_mime = input('Exportacao de Google Docs (text/plain ou application/pdf; vazio para arquivo comum): ').strip() or None
        docs.append({'id': file_id, 'classification': classification, 'export_mime': export_mime})
        if len(docs) >= 20:
            break
    calendar = None
    calendar_id = input('ID da Agenda experimental (vazio adia Calendar): ').strip()
    if calendar_id:
        owned_answer = input('A conta experimental e proprietaria dos dados dessa Agenda? (sim/nao): ').strip().casefold()
        if owned_answer not in ('sim','nao'):
            raise EngineError('google_configuration_invalid')
        calendar = {'id': calendar_id, 'owned': owned_answer == 'sim',
                    'window_start': input('Inicio autorizado ISO 8601 com fuso: ').strip(),
                    'window_end': input('Fim autorizado ISO 8601 com fuso (ate 31 dias): ').strip()}
    sheets = None
    sheet_id = input('ID da planilha experimental (vazio adia Sheets): ').strip()
    if sheet_id:
        ranges = []
        print("Intervalos exatos, com aba e limites, por exemplo 'Operacao'!A1:J20. Vazio encerra.")
        while len(ranges) < 10:
            target = input('Intervalo autorizado: ').strip()
            if not target:
                break
            ranges.append(target)
        sheets = {'id': sheet_id, 'ranges': ranges}
    declaration = {'expected_account': email, 'drive_documents': docs, 'calendar': calendar,
                   'sheets': sheets, 'limits': dict(DEFAULT_LIMITS)}
    config = parse_google(declaration)
    print('Os escopos permitem ler outros recursos acessiveis a conta; o Alfredo limita cada chamada aos IDs cadastrados.')
    print('Escopos solicitados: '+', '.join(config.scopes))
    if input('Confirma estes recursos e operacoes somente leitura? Digite AUTORIZO LEITURA: ') != 'AUTORIZO LEITURA':
        raise EngineError('google_resource_authorization_not_confirmed')
    raw['google'] = declaration
    with private_lock(path):
        atomic_yaml(path, before, raw, _parse_config)
    print('Configuracao Google cadastrada. Nenhuma API foi chamada e nenhum segredo foi alterado.')


def authorize(root=ROOT, *, allow_live=False, allow_writes=False):
    if not allow_live:
        raise EngineError('live_google_authorization_required')
    config = load_config(root/'config.yaml')
    if config.google is None:
        raise EngineError('google_not_configured')
    if config.google.write_access and not allow_writes:
        raise EngineError('live_google_writes_authorization_required')
    if not sys.stdin.isatty():
        raise EngineError('google_interactive_terminal_required')
    print('Use somente o cliente Desktop do projeto experimental. Nenhum segredo deve ser enviado ao chat.')
    with warnings.catch_warnings():
        warnings.simplefilter('error', getpass.GetPassWarning)
        try:
            client_path = Path(getpass.getpass('Caminho local do JSON Desktop dentro do Vert2Go (entrada oculta): ').strip('"')).absolute()
        except getpass.GetPassWarning:
            raise EngineError('google_hidden_prompt_unavailable') from None
    no_links(client_path)
    if not client_path.is_relative_to(root.absolute()) or not client_path.is_file() or client_path.suffix.casefold() != '.json':
        raise EngineError('google_client_must_be_inside_project')
    relative = client_path.relative_to(root.absolute())
    if relative.parts[0] != 'private' and not any(fnmatch(client_path.name, pattern) for pattern in ('*oauth*.json','client_secret*.json','credentials*.json')):
        raise EngineError('google_client_path_not_ignored')
    # Protect the selected local credential file before reading its bytes.
    private_acl(root/'secrets.yaml', client_path)
    GoogleAuth(config.google, root/'secrets.yaml', allow_live=True).enroll(client_path)
    print('Conta e escopos conferidos; OAuth salvo localmente. Telegram preservado.')


def main(argv=None):
    parser = argparse.ArgumentParser(description='Cadastro Google Desktop I3, somente leitura')
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--configure', action='store_true', help='Cadastrar conta, IDs e intervalos com confirmacao local')
    action.add_argument('--authorize', action='store_true', help='Proprietario seleciona JSON local e consente no navegador')
    parser.add_argument('--allow-live-google', action='store_true')
    parser.add_argument('--allow-live-google-writes',action='store_true',help='Consentir escopos I5 somente para os recursos experimentais autorizados')
    args = parser.parse_args(argv)
    try:
        if args.configure:
            if args.allow_live_google or args.allow_live_google_writes:
                raise EngineError('google_configure_is_offline')
            configure()
        else:
            authorize(allow_live=args.allow_live_google,allow_writes=args.allow_live_google_writes)
        return 0
    except EngineError as error:
        print('Cadastro interrompido: '+error.code)
        return 1
    except KeyboardInterrupt:
        print('Cadastro interrompido pelo operador.')
        return 130
    except Exception:
        print('Cadastro interrompido: google_local_setup_error')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
