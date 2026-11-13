"""I4 document lifecycle and evidence validation. No Google mutations or local index."""
from datetime import timedelta
import json
import logging
import re
import time
from app.ai.openai_http import remote_id
from app.ai.runtime_budget import RuntimeBudget
from app.core.contracts import EngineError, Result, canonical, digest, instant, stamp, utcnow

LOG = logging.getLogger('alfredo.knowledge')
SAFE = {
    'insufficient': 'Não encontrei evidência documental suficiente para responder com segurança.',
    'conflict': 'As fontes apresentam uma divergência que precisa de esclarecimento pela administração.',
    'unavailable': 'A consulta documental está indisponível. Não foi possível verificar a regra.'}


def unavailable(code='knowledge_unavailable'):
    return Result('blocked',code,{'reply':SAFE['unavailable']})


def invalid_evidence(reason):
    # Only fixed internal reason codes are passed here; never log source or user text.
    LOG.info('knowledge_evidence_rejected reason=%s',reason)
    return Result('blocked','knowledge_evidence_invalid',
                  {'reply':SAFE['unavailable'],'validation_error':reason})


def citation_text(value):
    """Compare visible Markdown text: only whitespace and bounded paired bold markers differ.

    Words, numbers, accents, punctuation and mathematical operators are preserved.
    In particular, markers embedded in expressions such as 2**3**4 are not stripped.
    Collapse whitespace first so paired bold markers can span source line wraps.
    """
    value = ' '.join(value.split())
    return re.sub(r'(?<!\w)(\*\*|__)(?=\S)([^\r\n]+?)(?<=\S)\1(?!\w)',r'\2',value)


class Knowledge:
    def __init__(self, config, store, drive, provider, *, clock=utcnow, sleep=time.sleep):
        if config.knowledge is None:
            raise EngineError('knowledge_not_configured')
        config.knowledge.require_consent()
        if store.execute('PRAGMA user_version').fetchone()[0] not in (3,4):
            raise EngineError('knowledge_migration_required')
        self.config, self.store, self.drive, self.provider = config, store, drive, provider
        self.k, self.clock, self.sleep = config.knowledge, clock, sleep
        self.budget = RuntimeBudget(config,store,clock)
        self.generation = digest([(d.id,d.sha256) for d in self.k.documents])
        self.pilot = digest([config.environment_id,self.k.project_id])

    def startup(self):
        self.budget.recover()

    def operational_context(self, message, topic, *, document_status='not_checked'):
        """Preparation for I5; not sent to OpenAI or exposed by the live I4 route."""
        if document_status != 'compatible':
            return {'status':'blocked','reason':'document_conflict_requires_review','guidance':[]}
        from app.core.policy import Policy
        from app.services.operational_memory import OperationalMemory
        memory = OperationalMemory(self.store,Policy(self.config),self.config)
        result = memory.find(message,{'topic':topic},instant(self.clock()))
        return {'status':'ready','source':'administration','guidance':[
            {key:r[key] for key in ('guidance_id','version','content','effective_from','effective_until')}
            for r in result.data['guidance']]}

    def validate_delivery(self, scope, message_id, reply, *, has_evidence):
        from app.core.policy import Policy
        Policy(self.config).authorize(scope,'knowledge.read')
        self.k.require_consent(telegram=True)
        if not has_evidence:
            return
        row = self.store.execute('SELECT * FROM knowledge_calls WHERE environment_id=? AND call_id=?',
                                 (self.config.environment_id,digest([scope.key(),message_id]))).fetchone()
        if row is None or row['scope_hash'] != digest(scope.key()):
            raise EngineError('knowledge_delivery_invalidated')
        cached = self._cached(row)
        if cached.get('data',{}).get('reply') != reply:
            raise EngineError('knowledge_delivery_invalidated')
        manifest = self._manifest(self.store_id())
        approved_hashes = {d.sha256 for d in manifest.values()}
        if any(r.get('source_hash') not in approved_hashes for r in cached['data'].get('references',[])):
            raise EngineError('knowledge_delivery_invalidated')

    def _cached(self, row):
        if row['state'] != 'completed':
            raise EngineError('openai_usage_uncertain')
        if instant(row['expires_at']) <= instant(self.clock()):
            raise EngineError('knowledge_cached_result_expired')
        return json.loads(row['result'])

    def _call(self, kind, identity, payload, operation):
        cid = digest([self.config.environment_id,kind,identity])
        old = self.budget.begin(cid,kind,self.pilot,digest(payload))
        if old:
            return self._cached(old)
        try:
            value = operation(cid)
            prefix = 'vs_' if kind == 'store' else 'file-'
            rid = remote_id(value.get('id'),prefix)
            if kind == 'store' and value.get('metadata',{}).get('pilot_ref') != self.pilot:
                raise EngineError('knowledge_store_mismatch')
            result = {'id':rid}
            self.budget.complete(cid,result,rid)
            return result
        except BaseException:
            self.budget.uncertain(cid)
            raise

    def store_id(self, *, create=False):
        if self.k.vector_store_id:
            return self.k.vector_store_id
        # The durable job is the authority until the operator persists this non-secret ID.
        identity = ['pilot_store',self.k.project_id]
        cid = digest([self.config.environment_id,'store',identity])
        row = self.store.execute('SELECT * FROM knowledge_calls WHERE environment_id=? AND call_id=?',
                                 (self.config.environment_id,cid)).fetchone()
        if row and not (create and row['state'] == 'failed'):
            return self._cached(row)['id']
        if not create:
            raise EngineError('knowledge_not_synced')
        return self._call('store',identity,{'pilot':self.pilot},lambda _: self.provider.create_store(self.pilot))['id']

    def measure_storage(self, store_id):
        value = self.provider.store(store_id)
        if value.get('id') != store_id or value.get('metadata',{}).get('pilot_ref') != self.pilot:
            raise EngineError('knowledge_store_mismatch')
        self.budget.storage(store_id,value.get('usage_bytes'))
        return value

    def _read(self, doc):
        value = self.drive.read_document(doc.id)
        if value.sha256 != doc.sha256:
            with self.store.transaction():
                self.store.execute("UPDATE document_sync_metadata SET status='outdated',updated_at=? WHERE environment_id=? AND source_id=?",
                                   (stamp(self.clock()),self.config.environment_id,doc.id))
                self.store.execute("UPDATE knowledge_versions SET status='outdated',updated_at=? WHERE environment_id=? AND source_id=?",
                                   (stamp(self.clock()),self.config.environment_id,doc.id))
            raise EngineError('knowledge_source_changed')
        if value.classification == 'unverified' or value.mime_type not in ('text/markdown','text/plain'):
            raise EngineError('knowledge_document_not_readable')
        try:
            text = value.content.decode('utf-8-sig')
        except UnicodeError:
            raise EngineError('knowledge_document_not_readable') from None
        if not text.strip() or '\ufffd' in text or '\x00' in text:
            raise EngineError('knowledge_document_not_readable')
        return value

    def _attributes(self, doc):
        return {'generation':self.generation, 'source_ref':digest(doc.id), 'source_hash':doc.sha256, 'pilot_ref':self.pilot}

    def sync(self):
        self.k.require_consent()
        # Validate all sources before creating the first paid resource or uploading anything.
        values = [(doc,self._read(doc)) for doc in self.k.documents]
        sid = self.store_id(create=True)
        self.measure_storage(sid)
        env = self.config.environment_id
        for doc,value in values:
            old = self.store.execute('''SELECT * FROM knowledge_versions WHERE environment_id=?
                AND source_id=? AND source_hash=? AND vector_store_id=?''', (env,doc.id,doc.sha256,sid)).fetchone()
            if old and old['status'] == 'synced':
                file_id = old['indexed_file_id']
            else:
                file_id = self._call('upload',[doc.id,doc.sha256],{'hash':doc.sha256,'mime':value.mime_type},
                                     lambda cid: self.provider.upload(cid,value.content,value.mime_type))['id']
                with self.store.transaction():
                    self.store.execute('''INSERT INTO knowledge_versions VALUES (?,?,?,?,?,?,?,?)
                        ON CONFLICT(environment_id,source_id,source_hash,vector_store_id) DO UPDATE SET
                        indexed_file_id=excluded.indexed_file_id,updated_at=excluded.updated_at''',
                        (env,doc.id,doc.sha256,value.source_version,sid,file_id,'pending',stamp(self.clock())))
            attributes = self._attributes(doc)
            def attach(_):
                # Reserve storage conservatively before an asynchronous write can be accepted.
                self.budget.storage(sid,self.k.limits['max_storage_bytes'])
                if old and old['status'] == 'synced':
                    return self.provider.tag_file(sid,file_id,attributes)
                return self.provider.attach(sid,file_id,attributes)
            self._call('attach',[sid,file_id,self.generation],attributes,attach)
            indexed = None
            for attempt in range(self.k.limits['max_poll_attempts']):
                indexed = self.provider.indexed_file(sid,file_id)
                if indexed.get('status') != 'in_progress':
                    break
                if attempt+1 < self.k.limits['max_poll_attempts']:
                    self.sleep(self.k.limits['poll_seconds'])
            if (indexed.get('id') != file_id or indexed.get('vector_store_id') != sid or
                    indexed.get('status') != 'completed' or indexed.get('attributes') != attributes):
                self.measure_storage(sid)
                raise EngineError('knowledge_index_not_ready')
            # Re-read the source after indexing; changes invalidate publication.
            latest = self._read(doc)
            if latest.source_version != value.source_version:
                raise EngineError('knowledge_source_changed')
            with self.store.transaction():
                self.store.execute("UPDATE knowledge_versions SET status='outdated' WHERE environment_id=? AND source_id=? AND (source_hash<>? OR vector_store_id<>?)",
                                   (env,doc.id,doc.sha256,sid))
                self.store.execute("UPDATE knowledge_versions SET status='synced',source_revision=?,updated_at=? WHERE environment_id=? AND source_id=? AND source_hash=? AND vector_store_id=?",
                                   (value.source_version,stamp(self.clock()),env,doc.id,doc.sha256,sid))
                self.store.execute('''INSERT INTO document_sync_metadata VALUES (?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(environment_id,source_id) DO UPDATE SET source_revision=excluded.source_revision,
                    source_hash=excluded.source_hash,classification=excluded.classification,indexed_file_id=excluded.indexed_file_id,
                    vector_store_id=excluded.vector_store_id,status=excluded.status,updated_at=excluded.updated_at,safe_error=NULL''',
                    (env,doc.id,value.source_version,doc.sha256,value.classification,file_id,sid,'synced',stamp(self.clock()),None))
            self.measure_storage(sid)
        return {'vector_store_id':sid,'document_count':len(values),'generation':self.generation,'status':'synced'}

    def _manifest(self, sid):
        manifest = {}
        for doc in self.k.documents:
            value = self._read(doc)
            row = self.store.execute('SELECT * FROM document_sync_metadata WHERE environment_id=? AND source_id=?',
                                     (self.config.environment_id,doc.id)).fetchone()
            if (not row or row['status'] != 'synced' or row['source_hash'] != doc.sha256 or
                    row['source_revision'] != value.source_version or row['vector_store_id'] != sid):
                raise EngineError('knowledge_not_synced')
            manifest[row['indexed_file_id']] = doc
        return manifest

    def _validate_response(self, response, manifest):
        usage = response.get('usage')
        if type(usage) is not dict or any(type(usage.get(k)) is not int or usage[k] < 0 for k in ('input_tokens','output_tokens')):
            raise EngineError('openai_usage_missing')
        output = response.get('output')
        if type(output) is not list:
            raise EngineError('openai_response_invalid')
        searches = [x for x in output if type(x) is dict and x.get('type') == 'file_search_call']
        if (response.get('status') != 'completed' or response.get('model') != self.k.model or
                len(searches) != 1 or searches[0].get('status') != 'completed'):
            return unavailable('knowledge_incomplete_response'), usage, len(searches)
        results = searches[0].get('results')
        if type(results) is not list or len(results) > self.k.limits['max_results']:
            return invalid_evidence('search_results_invalid'), usage, 1
        chunks = {}
        for item in results:
            if type(item) is not dict or item.get('file_id') not in manifest or type(item.get('text')) is not str:
                return invalid_evidence('retrieved_file_invalid'), usage, 1
            attrs = item.get('attributes')
            # Attributes are checked when returned; file ID always checked against the current manifest.
            if attrs is not None and attrs != self._attributes(manifest[item['file_id']]):
                return invalid_evidence('retrieved_attributes_invalid'), usage, 1
            chunks.setdefault(item['file_id'],[]).append(item['text'])
        messages = [x for x in output if type(x) is dict and x.get('type') == 'message' and x.get('role') == 'assistant']
        texts = [c.get('text') for m in messages for c in m.get('content',[]) if type(c) is dict and c.get('type') == 'output_text']
        reason = 'answer_format_invalid'
        try:
            if len(texts) != 1 or type(texts[0]) is not str:
                raise ValueError
            answer = json.loads(texts[0])
            if type(answer) is not dict or set(answer) != {'status','claims'} or type(answer['claims']) is not list:
                raise ValueError
            if answer['status'] in ('insufficient','conflict'):
                return Result('success','knowledge_'+answer['status'],{'reply':SAFE[answer['status']]}), usage, 1
            if answer['status'] != 'answered' or not 1 <= len(answer['claims']) <= 4:
                raise ValueError
            lines, refs = [], []
            for claim in answer['claims']:
                reason = 'claim_fields_invalid'
                if type(claim) is not dict or set(claim) != {'text','file_id','quote','section'}:
                    raise ValueError
                fid, quote, section, text = (claim[k] for k in ('file_id','quote','section','text'))
                if (type(fid) is not str or fid not in manifest or type(quote) is not str or not 8 <= len(quote) <= 1000 or
                        type(text) is not str or not 1 <= len(text) <= 600):
                    raise ValueError
                normalized_quote = citation_text(quote)
                reason = 'quote_invalid'
                if len(normalized_quote) < 8 or not any(character.isalnum() for character in normalized_quote):
                    raise ValueError
                exact_quote = any(quote in chunk for chunk in chunks.get(fid,[]))
                reason = 'quote_not_found'
                if not exact_quote and not any(normalized_quote in citation_text(chunk) for chunk in chunks.get(fid,[])):
                    raise ValueError
                reason = 'section_not_found'
                if section is not None and (type(section) is not str or not 1 <= len(section) <= 100 or
                                            not any(re.search(r'(?m)^#{1,6}\s+'+re.escape(section)+r'\s*$',chunk) for chunk in chunks[fid])):
                    raise ValueError
                doc = manifest[fid]
                classification = next(d.classification for d in self.config.google.documents if d.id == doc.id)
                label = doc.title+(' (simulação)' if classification == 'simulation' else '')+(' — '+section if section else '')
                lines.append(text+'\nFonte: '+label+'\nTrecho: “'+quote+'”')
                refs.append({'source_ref':digest(doc.id),'source_hash':doc.sha256,'file_id':fid,'quote_hash':digest(quote),
                             'quote_match':'exact' if exact_quote else 'layout_normalized'})
            rendered = 'Alfredo experimental\n\n'+'\n\n'.join(lines)
            reason = 'reply_limit'
            if len(rendered.encode('utf-16-le'))//2 > 4096:
                raise ValueError
            return Result('success','knowledge_answer',{'reply':rendered,'references':refs}), usage, 1
        except (ValueError, TypeError, KeyError, UnicodeError):
            return invalid_evidence(reason), usage, 1

    def answer(self, message, *, operator=False):
        from app.core.policy import Policy
        Policy(self.config).authorize(message.scope,'knowledge.read')
        self.k.require_consent(telegram=message.scope.channel == 'telegram' and not operator)
        question = message.text.strip()
        if not question or len(question) > self.k.limits['max_question_chars']:
            return unavailable('knowledge_input_limit')
        cid = digest([message.scope.key(),message.message_id])
        request_hash = digest([message.scope.key(),message.message_id,message.update_id,stamp(message.received_at),message.text,self.generation])
        scope_hash = digest(message.scope.key())
        row = self.store.execute('SELECT * FROM knowledge_calls WHERE environment_id=? AND call_id=?',
                                 (self.config.environment_id,cid)).fetchone()
        if row:
            if row['request_hash'] != request_hash or row['scope_hash'] != scope_hash:
                raise EngineError('message_identity_conflict')
            # Revalidate the current source before showing a previously generated answer.
            self._manifest(self.store_id())
            return Result(**self._cached(row))
        sid = self.store_id()
        manifest = self._manifest(sid)
        self.measure_storage(sid)
        old = self.budget.begin(cid,'answer',scope_hash,request_hash)
        if old:
            return Result(**self._cached(old))
        try:
            response = self.provider.answer(question,sid,self.generation,tuple(manifest))
            result, usage, searches = self._validate_response(response,manifest)
            try:
                self._manifest(sid)
            except EngineError:
                result = unavailable('knowledge_source_revalidation_failed')
            # Usage is recorded even if evidence is invalid or the model refuses.
            self.budget.complete(cid,result.as_dict(),response.get('id'),inputs=usage['input_tokens'],
                                 outputs=usage['output_tokens'],searches=searches)
            LOG.info('knowledge_answer_finished code=%s alert=%s',result.code,self.budget.assess()['alert'])
            return result
        except BaseException:
            self.budget.uncertain(cid)
            raise

    def reconcile(self, call_id, *, remote=None, inputs=None, outputs=None, searches=None, verified_not_created=False):
        """Explicit owner action; never resubmit the original external operation."""
        row = self.store.execute('SELECT * FROM knowledge_calls WHERE environment_id=? AND call_id=?',
                                 (self.config.environment_id,call_id)).fetchone()
        if not row or row['state'] != 'uncertain':
            raise EngineError('knowledge_call_state_invalid')
        if verified_not_created:
            if remote is not None or any(v is not None for v in (inputs,outputs,searches)):
                raise EngineError('knowledge_reconciliation_mismatch')
            self.budget.verified_not_created(call_id)
            return
        if row['kind'] == 'answer':
            if remote is not None or any(type(v) is not int or v < 0 for v in (inputs,outputs,searches)):
                raise EngineError('openai_usage_missing')
            # A store=false response cannot necessarily be recovered. Record measured usage and
            # cache a safe terminal answer; an uncertain message is never automatically regenerated.
            self.budget.complete(call_id,unavailable('knowledge_reconciled_without_answer').as_dict(),
                                 inputs=inputs,outputs=outputs,searches=searches)
        elif row['kind'] == 'store':
            value = self.provider.store(remote)
            if value.get('id') != remote or value.get('metadata',{}).get('pilot_ref') != self.pilot:
                raise EngineError('knowledge_store_mismatch')
            self.budget.complete(call_id,{'id':remote},remote)
            self.budget.storage(remote,value.get('usage_bytes'))
        elif row['kind'] == 'upload':
            value = self.provider.file(remote)
            if value.get('id') != remote or value.get('filename') not in ('alfredo-'+call_id+'.md','alfredo-'+call_id+'.txt'):
                raise EngineError('knowledge_reconciliation_mismatch')
            self.budget.complete(call_id,{'id':remote},remote)
        else:
            sid = self.store_id()
            value = self.provider.indexed_file(sid,remote)
            doc = next((d for d in self.k.documents if value.get('attributes') == self._attributes(d)),None)
            expected = digest([self.config.environment_id,'attach',[sid,remote,self.generation]])
            if (expected != call_id or doc is None or value.get('id') != remote or
                    value.get('vector_store_id') != sid or value.get('status') != 'completed'):
                raise EngineError('knowledge_reconciliation_mismatch')
            self.budget.complete(call_id,{'id':remote},remote)
            self.measure_storage(sid)
