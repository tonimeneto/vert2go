"""Finite fictional I4 demonstration; captured provider, no network or real credentials."""
import json
from tests.test_knowledge import KnowledgeTests


def main():
    case = KnowledgeTests('test_sync_then_paraphrase_has_verified_excerpt_and_source')
    case.setUp()
    try:
        synced = case.sync()
        message = case.question()
        answer = case.service.answer(message)
        replay = case.service.answer(message)
        assert answer == replay and case.provider.answer_calls == 1
        print(json.dumps({'phase':'I4','scope':'fictional_offline_demo','sync':synced['status'],
                          'answer':answer.as_dict(),'paid_provider_attempts_captured':case.provider.answer_calls,
                          'external_api_attempted':False,'real_credentials_read':False},ensure_ascii=False))
        return 0
    finally:
        case.doCleanups()


if __name__ == '__main__':
    raise SystemExit(main())
