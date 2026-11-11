"""Redacted readiness evidence. No polling, messages, databases or Git operations."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.channels.telegram import TelegramAPI
from app.config.schema import (ConfigurationFileError, load_config, load_enrollment_config,
                               load_enrollment_secrets, load_telegram_token, read_yaml, TelegramSecretsError)
from app.core.contracts import EngineError
from scripts.setup_telegram_i2 import verify_bot


def check(root=ROOT, *, allow_live=False, expected_username=None):
    report = {
        'phase': 'I2', 'scope': 'telegram_readiness',
        'updated_at': datetime.now(timezone.utc).isoformat(),
        'local_configuration': 'blocked', 'local_token': 'not_run',
        'config_yaml': 'not_run', 'secrets_yaml': 'not_run',
        'enrollment_structure': 'not_run', 'missing_fields': [],
        'getMe_and_getWebhookInfo': 'not_run',
        'external_api_attempted': False, 'messages_sent': False,
        'database_opened': False, 'live_acceptance': 'blocked',
        'participant_identity': 'not_run', 'unknown_and_group_denial': 'not_run',
        'context_isolation': 'not_run', 'duplicate_real_update': 'not_run',
        'restart_and_resume': 'not_run', 'profile_change_denial': 'not_run',
        'human_delivery_confirmation': 'not_run',
        'I3': 'not_authorized', 'git_operations': False, 'lovable_publication': False,
    }
    try:
        read_yaml(root/'config.yaml')
        report['config_yaml'] = 'passed'
        draft = load_enrollment_config(root/'config.yaml')
        read_yaml(root/'secrets.yaml')
        report['secrets_yaml'] = 'passed'
        secrets = load_enrollment_secrets(root/'secrets.yaml', draft['channels']['telegram']['bot_id'])
        report['enrollment_structure'] = 'passed'
        if draft['channels']['telegram']['bot_id'] is None:
            report['missing_fields'].append('channels.telegram.bot_id')
        for user in draft['users']:
            if user['channel_user_id'] is None:
                report['missing_fields'].append('users.'+user['role']+'.channel_user_id')
        if secrets['telegram_bot_token'] is None:
            report['missing_fields'].append('telegram_bot_token')
        if secrets['telegram_bot_token'] is None or draft['channels']['telegram']['bot_id'] is None:
            report['reason'] = 'telegram_enrollment_incomplete'
            return report
        if not report['missing_fields']:
            load_config(root/'config.yaml')
            report['local_configuration'] = 'passed'
        # A local check explicitly permits validation in memory, never echoing the token.
        token = load_telegram_token(root/'secrets.yaml', draft['channels']['telegram']['bot_id'])
        report['local_token'] = 'passed'
        if allow_live:
            report['external_api_attempted'] = True
            report['getMe_and_getWebhookInfo'] = 'failed'
            verify_bot(TelegramAPI(token, draft['channels']['telegram']['request_seconds']),
                       draft['channels']['telegram']['bot_id'], expected_username)
            report['getMe_and_getWebhookInfo'] = 'passed'
        report['reason'] = 'telegram_enrollment_incomplete' if report['missing_fields'] else 'interactive_message_acceptance_required'
    except EngineError as error:
        # Codes are defined by our parsers/transport; no provider descriptions or input values.
        report['reason'] = error.code
        if isinstance(error, (ConfigurationFileError, TelegramSecretsError)):
            report['diagnostic'] = error.diagnostic
    except (OSError, ValueError, TypeError, KeyError):
        report['reason'] = 'local_check_error'
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description='Checar preparacao I2 sem enviar mensagens')
    parser.add_argument('--allow-live-telegram', action='store_true', help='Consultar getMe e webhook do bot autorizado')
    parser.add_argument('--expected-bot', default='AlfredoVert2GoBot', help='Username esperado; nunca fornecer token neste argumento')
    args = parser.parse_args(argv)
    report = check(allow_live=args.allow_live_telegram, expected_username=args.expected_bot)
    evidence = ROOT/'docs'/'evidencias'/'i2-telegram-check.json'
    evidence.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))
    ready = report['local_configuration'] == report['local_token'] == 'passed'
    if args.allow_live_telegram:
        ready = ready and report['getMe_and_getWebhookInfo'] == 'passed'
    return 0 if ready else 1


if __name__ == '__main__':
    raise SystemExit(main())
