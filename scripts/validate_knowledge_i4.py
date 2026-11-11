"""Finite G3-authorized real cases. Persist only redacted evidence, never raw provider payloads."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.ai.runtime import knowledge_runtime
from app.config.schema import load_config
from app.core.contracts import EngineError, Message, Scope, digest, utcnow
from app.main import instance_lock
from app.storage.sqlite import Store
from app.services.knowledge import citation_text

CASES = {
    'bicycle_parking': ('resident','Posso estacionar bicicleta na minha vaga de garagem?','knowledge_answer'),
    'bicycle_parking_plain': ('resident','Posso estacionar bicicleta na minha vaga de garagem','knowledge_answer'),
    'apartment_62_spaces': ('resident','Quantas vagas tem o apartamento 62?','knowledge_answer'),
    'pool_paraphrase': ('resident','Posso dar um mergulho às onze da noite?','knowledge_answer'),
    'pool_hours': ('resident','Qual é o horário de funcionamento da piscina?','knowledge_answer'),
    'missing_rule': ('resident','Qual é a cor obrigatória das pulseiras de identificação para usar a piscina?','knowledge_insufficient'),
    'convention_term': ('manager','Segundo a Convenção, por quanto tempo a pessoa eleita para síndico fica no cargo?','knowledge_answer'),
    'visitor_scope': ('manager','Compare a regra de visitantes na seção Piscinas com a regra para convidados do Salão de festas e churrasqueiras. Apresente os contextos separadamente, com os trechos de apoio.','knowledge_answer'),
    'visitor_conflict': ('manager','O Regulamento Interno permite levar convidados à piscina? Verifique também se há orientações contraditórias no próprio documento.','knowledge_conflict')}


def trace_response(response):
    searches = [x for x in response.get('output',[]) if x.get('type') == 'file_search_call']
    results = [r for x in searches for r in (x.get('results') or [])]
    text = '\n'.join(r.get('text','') for r in results)
    messages = [c.get('text','') for x in response.get('output',[]) if x.get('type') == 'message'
                for c in x.get('content',[]) if c.get('type') == 'output_text']
    status, claim_checks = None, []
    try:
        parsed = json.loads(messages[0]) if len(messages) == 1 else {}
        status = parsed.get('status')
        for claim in parsed.get('claims',[]):
            chunks = [r.get('text','') for r in results if r.get('file_id') == claim.get('file_id')]
            quote,section = claim.get('quote',''),claim.get('section')
            claim_checks.append({'section':section,'quote':quote,
                'claim_file_ref':digest(claim.get('file_id','')),
                'quote_matching_file_refs':sorted({digest(r.get('file_id','')) for r in results
                    if quote and citation_text(quote) in citation_text(r.get('text',''))}),
                'exact_quote_in_result':any(quote in chunk for chunk in chunks),
                'whitespace_normalized_quote_in_result':any(' '.join(quote.split()) in ' '.join(chunk.split()) for chunk in chunks),
                'layout_normalized_quote_in_result':any(citation_text(quote) in citation_text(chunk) for chunk in chunks),
                'section_heading_in_result':section is None or any(re.search(r'(?m)^#{1,6}\s+'+re.escape(section)+r'\s*$',chunk) for chunk in chunks)})
    except (ValueError,TypeError):
        pass
    return {'provider_status':response.get('status'),'model':response.get('model'),
            'response_ref':digest(response.get('id','')),'search_count':len(searches),
            'search_statuses':[x.get('status') for x in searches],
            'result_count':len(results),'model_evidence_status':status,
            'search_queries':[q for x in searches for q in x.get('queries',[])],
            'claim_checks':claim_checks,
            'retrieved_pool_hours':('08:00' in text and '22:00' in text),
            'retrieved_convention_term':('bienal' in text.casefold() or '2 anos' in text),
            'usage':response.get('usage'),
            'retrieved_file_refs':sorted({digest(r.get('file_id','')) for r in results})}


def main(argv=None):
    parser = argparse.ArgumentParser(description='Casos reais finitos I4, sem envio Telegram ou escrita Google')
    parser.add_argument('--case',choices=CASES,required=True)
    parser.add_argument('--database',required=True)
    parser.add_argument('--allow-live-openai',action='store_true')
    args = parser.parse_args(argv)
    report = {'phase':'I4','scope':'real_local_document_query','case':args.case,'updated_at':utcnow().isoformat(),
              'result':'blocked','external_api_attempted':False,'google_mutations_attempted':False,
              'telegram_messages_sent':False,'response':{},'http':[]}
    try:
        if not args.allow_live_openai:
            raise EngineError('live_openai_authorization_required')
        config = load_config(ROOT/'config.yaml')
        config.knowledge.require_consent()
        role,question,expected = CASES[args.case]
        user = next(u for u in config.users if u.enabled and u.role == role)
        with instance_lock(args.database):
            store = Store(args.database,knowledge=True)
            try:
                with knowledge_runtime(config,store,ROOT/'secrets.yaml',allow_live=True) as service:
                    original_answer = service.provider.answer
                    original_request = service.provider._session.request
                    def observed_request(method,url,**kwargs):
                        report['external_api_attempted'] = True
                        response = original_request(method,url,**kwargs)
                        record = {'method':method,'status':response.status_code}
                        if response.status_code >= 400:
                            bounded = bytearray()
                            for block in response.iter_content(chunk_size=4096):
                                bounded.extend(block)
                                if len(bounded)>65536:
                                    break
                            try:
                                error = json.loads(bounded).get('error',{})
                                for key in ('code','type','param'):
                                    value = error.get(key)
                                    if type(value) is str and re.fullmatch(r'[A-Za-z0-9_.\[\]-]{1,120}',value):
                                        record[key] = value
                            except (ValueError,AttributeError):
                                pass
                        report['http'].append(record)
                        return response
                    def observed_answer(*values):
                        response = original_answer(*values)
                        report['response'] = trace_response(response)
                        return response
                    service.provider._session.request = observed_request
                    service.provider.answer = observed_answer
                    message = Message(Scope(config.environment_id,user.channel,user.channel_user_id,user.chat_ids[0]),
                                      'i4_live_'+args.case+'_'+uuid4().hex[:12],utcnow(),'i4_live_'+args.case,question)
                    result = service.answer(message,operator=True)
                    references = result.data.get('references',[])
                    report.update(role=role,result_code=result.code,expected_code=expected,
                                  result='passed' if result.code == expected else 'failed',references=references,
                                  reply=result.data.get('reply'),budget=service.budget.assess(),
                                  validation_error=result.data.get('validation_error'),
                                  openai_request_count=service.provider.request_count,
                                  google_data_request_count=service.drive.request_count)
            finally:
                store.close()
    except EngineError as error:
        report.update(result='blocked',reason=error.code)
    except Exception:
        report.update(result='blocked',reason='knowledge_live_validation_failed')
    # Case questions are fixed and contain no participant data. The verified reply is deliberately
    # retained as test evidence; arbitrary incoming Telegram text and provider results are not logged.
    filename = 'i4-live-'+args.case+'-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json'
    (ROOT/'docs/evidencias'/filename).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True))
    return 0 if report['result'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
