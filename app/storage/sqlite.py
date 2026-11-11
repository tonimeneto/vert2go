"""Transactional storage; migrate verified schemas, never adopt an unknown file."""
from contextlib import contextmanager
from datetime import timedelta
import hashlib
import json
from pathlib import Path
import sqlite3
from uuid import uuid4
from app.core.contracts import EngineError, stamp, instant, canonical

APPLICATION_ID = 1446135601
MIGRATION = Path(__file__).parent / 'migrations' / '001_initial.sql'
TELEGRAM_MIGRATION = MIGRATION.with_name('002_telegram.sql')
KNOWLEDGE_MIGRATION = MIGRATION.with_name('003_knowledge.sql')
OPEN_STATES = ('received','awaiting_confirmation','committing','needs_reconciliation')
TERMINAL_STATES = ('confirmed','failed','cancelled','conflicted')


def schema_snapshot(connection):
    return [tuple(row) for row in connection.execute("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type,name")]


class Store:
    def __init__(self, path, *, knowledge=False):
        self.path = Path(path)
        self.connection = None
        existed = self.path.exists()
        if existed:
            # Read-only inspection before any pragmas which could modify a preexisting file.
            try:
                probe = sqlite3.connect(self.path.resolve().as_uri() + '?mode=ro', uri=True)
                try:
                    if (probe.execute('PRAGMA application_id').fetchone()[0] != APPLICATION_ID
                            or probe.execute('PRAGMA user_version').fetchone()[0] not in (1, 2, 3)):
                        raise EngineError('unrecognized_database')
                finally:
                    probe.close()
            except sqlite3.DatabaseError:
                raise EngineError('invalid_database') from None
        else:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.connection = sqlite3.connect(self.path, timeout=5, isolation_level=None)
            self.connection.execute('PRAGMA foreign_keys=ON')
            self.connection.execute('PRAGMA busy_timeout=5000')
            if not existed:
                sql = MIGRATION.read_text(encoding='utf-8')
                self.connection.executescript('BEGIN IMMEDIATE;\n' + sql +
                    f'\nPRAGMA application_id={APPLICATION_ID}; PRAGMA user_version=1; COMMIT;')
            self.verify()
            if self.connection.execute('PRAGMA user_version').fetchone()[0] == 1:
                self.connection.executescript('BEGIN IMMEDIATE;\n' + TELEGRAM_MIGRATION.read_text(encoding='utf-8') +
                                              '\nPRAGMA user_version=2; COMMIT;')
                self.verify()
            if knowledge and self.connection.execute('PRAGMA user_version').fetchone()[0] == 2:
                self.connection.executescript('BEGIN IMMEDIATE;\n' + KNOWLEDGE_MIGRATION.read_text(encoding='utf-8') +
                                              '\nPRAGMA user_version=3; COMMIT;')
                self.verify()
            self.connection.execute('PRAGMA journal_mode=WAL')
            self.connection.execute('PRAGMA synchronous=FULL')
            self.connection.row_factory = sqlite3.Row
        except BaseException:
            if self.connection is not None:
                if self.connection.in_transaction:
                    self.connection.rollback()
                self.connection.close()
            raise

    def verify(self):
        expected = sqlite3.connect(':memory:')
        try:
            expected.executescript(MIGRATION.read_text(encoding='utf-8'))
            version = self.connection.execute('PRAGMA user_version').fetchone()[0]
            if version >= 2:
                expected.executescript(TELEGRAM_MIGRATION.read_text(encoding='utf-8'))
            if version >= 3:
                expected.executescript(KNOWLEDGE_MIGRATION.read_text(encoding='utf-8'))
            if schema_snapshot(expected) != schema_snapshot(self.connection):
                raise EngineError('schema_mismatch')
        finally:
            expected.close()
        if self.connection.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise EngineError('integrity_failure')
        if self.connection.execute('PRAGMA foreign_key_check').fetchall():
            raise EngineError('foreign_key_failure')

    @contextmanager
    def transaction(self):
        if self.connection.in_transaction:
            raise EngineError('nested_transaction')
        self.connection.execute('BEGIN IMMEDIATE')
        try:
            yield
            self.connection.commit()
        except BaseException:
            self.connection.rollback()
            raise

    def execute(self, sql, parameters=()):
        return self.connection.execute(sql, parameters)

    def close(self):
        if self.connection is not None:
            if self.connection.in_transaction:
                self.connection.rollback()
            self.connection.close()
            self.connection = None

    def audit(self, message, role, operation, result, now, operation_id=None,
              entity_id=None, version=None, previous=None, next_state=None,
              confirmation_ref=None, safe_error=None):
        # Caller-controlled text/identifiers are represented by hashes in audit.
        pseudo = hashlib.sha256(canonical(message.scope.key()[:3]).encode()).hexdigest()[:24]
        correlation = hashlib.sha256(str(message.correlation_id).encode()).hexdigest()[:24]
        self.execute("""INSERT INTO operation_log
            (audit_id,environment_id,at_time,actor_pseudonym,role,operation,operation_id,
             entity_id,version,previous_state,next_state,result,correlation_id,confirmation_ref,safe_error)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (str(uuid4()), message.scope.environment_id, stamp(now), pseudo, role, operation,
             operation_id, entity_id, version, previous, next_state, result, correlation,
             confirmation_ref, safe_error))

    def recover(self, environment_id, now):
        """No administrative effect is replayed; uncertain operations remain blocked."""
        recovered = 0
        with self.transaction():
            rows = self.execute("SELECT * FROM requests_state WHERE environment_id=? AND state='committing'",
                                (environment_id,)).fetchall()
            for row in rows:
                revision = self.execute("""SELECT guidance_id,version,status FROM operational_guidance_revisions
                    WHERE environment_id=? AND operation_id=?""", (environment_id,row['operation_id'])).fetchone()
                state = 'confirmed' if revision else 'needs_reconciliation'
                result = canonical({**dict(revision),'operation_id':row['operation_id']}) if revision else None
                self.execute("""UPDATE requests_state SET state=?,result=?,updated_at=?,closed_at=?
                    WHERE environment_id=? AND operation_id=?""",
                    (state,result,stamp(now),stamp(now) if revision else None,environment_id,row['operation_id']))
                self._recovery_audit(environment_id,row,now,state)
                recovered += 1
            expired = self.execute("""SELECT * FROM requests_state WHERE environment_id=?
                AND state='awaiting_confirmation' AND expires_at<=?""", (environment_id,stamp(now))).fetchall()
            for row in expired:
                self.execute("""UPDATE requests_state SET state='cancelled',closed_at=?,updated_at=?
                    WHERE environment_id=? AND operation_id=?""",
                    (stamp(now),stamp(now),environment_id,row['operation_id']))
                self._recovery_audit(environment_id,row,now,'cancelled')
        return recovered

    def _recovery_audit(self, env, row, now, state):
        from app.core.contracts import Scope, Message
        message = Message(Scope(env,row['channel'],row['channel_user_id'],row['chat_id']),
                          'recovery',now,row['operation_id'])
        self.audit(message,'system','recovery','success',now,row['operation_id'],row['guidance_id'],
                   previous=row['state'],next_state=state)

    def retention_candidates(self, config, now):
        """Read-only eligibility report. No DELETE implementation or automatic cleanup."""
        env = config.environment_id
        cutoff = lambda days: stamp(instant(now)-timedelta(days=days))
        pending = """SELECT 1 FROM requests_state r WHERE r.environment_id=c.environment_id
            AND r.channel=c.channel AND r.channel_user_id=c.channel_user_id AND r.chat_id=c.chat_id
            AND (r.closed_at IS NULL OR r.incident_open=1)"""
        result = {}
        # Preserve uncertain/pending replies and any participant with an unresolved operation/incident.
        result['telegram_updates'] = [dict(r) for r in self.execute("""SELECT t.bot_id,t.update_id
            FROM telegram_updates t WHERE t.environment_id=? AND t.created_at<?
            AND t.state IN ('sent','discarded','failed')
            AND NOT EXISTS (SELECT 1 FROM requests_state r WHERE r.environment_id=t.environment_id
                AND r.channel='telegram' AND r.channel_user_id=t.channel_user_id AND r.chat_id=t.chat_id
                AND (r.closed_at IS NULL OR r.incident_open=1))
            AND NOT EXISTS (SELECT 1 FROM operational_guidance g WHERE g.environment_id=t.environment_id
                AND g.incident_open=1)""", (env,cutoff(config.retention['deduplication_days'])))]
        result['conversation_state'] = [dict(r) for r in self.execute(f"""SELECT c.environment_id,c.channel,c.channel_user_id,
            c.chat_id,c.state_key FROM conversation_state c WHERE c.environment_id=? AND c.updated_at<?
            AND NOT EXISTS ({pending})""", (env,cutoff(config.retention['conversation_days'])))]
        result['processed_messages'] = [dict(r) for r in self.execute("""SELECT p.message_id,p.channel,p.channel_user_id,p.chat_id
            FROM processed_messages p LEFT JOIN requests_state r
            ON r.environment_id=p.environment_id AND r.operation_id=p.operation_id
            WHERE p.environment_id=? AND p.created_at<? AND
            (r.operation_id IS NULL OR (r.closed_at IS NOT NULL AND r.incident_open=0))
            AND NOT EXISTS (SELECT 1 FROM operational_guidance g WHERE
                g.environment_id=r.environment_id AND g.guidance_id=r.guidance_id AND g.incident_open=1)""",
            (env,cutoff(config.retention['deduplication_days'])))]
        result['requests_state'] = [r['operation_id'] for r in self.execute("""SELECT r.operation_id FROM requests_state r
            WHERE r.environment_id=? AND r.closed_at<? AND r.incident_open=0
            AND NOT EXISTS (SELECT 1 FROM operational_guidance_revisions v
                WHERE v.environment_id=r.environment_id AND v.operation_id=r.operation_id)
            AND NOT EXISTS (SELECT 1 FROM sync_outbox o WHERE o.environment_id=r.environment_id
                AND o.operation_id=r.operation_id AND o.state!='synced')""",
            (env,cutoff(config.retention['closed_request_days'])))]
        result['operational_guidance'] = [r['guidance_id'] for r in self.execute("""SELECT g.guidance_id
            FROM operational_guidance g JOIN operational_guidance_revisions v ON
            v.environment_id=g.environment_id AND v.guidance_id=g.guidance_id AND v.version=g.current_version
            WHERE g.environment_id=? AND g.incident_open=0
            AND ((g.status IN ('expired','cancelled') AND g.retired_at<?)
                 OR (g.status='active' AND v.effective_until<?))
            AND NOT EXISTS (SELECT 1 FROM requests_state r WHERE r.environment_id=g.environment_id
                AND r.guidance_id=g.guidance_id AND (r.closed_at IS NULL OR r.incident_open=1))""",
            (env,cutoff(config.retention['guidance_audit_days']),cutoff(config.retention['guidance_audit_days'])))]
        result['operation_log'] = [r['audit_id'] for r in self.execute("""SELECT a.audit_id FROM operation_log a
            WHERE a.environment_id=? AND a.at_time<? AND a.incident_open=0
            AND NOT EXISTS (SELECT 1 FROM requests_state r WHERE r.environment_id=a.environment_id
                AND r.operation_id=a.operation_id AND (r.closed_at IS NULL OR r.incident_open=1))
            AND NOT EXISTS (SELECT 1 FROM operational_guidance g WHERE g.environment_id=a.environment_id
                AND g.guidance_id=a.entity_id AND (g.incident_open=1 OR g.status='active'
                    OR g.retired_at IS NULL OR g.retired_at>=?))""",
            (env,cutoff(config.retention['audit_days']),cutoff(config.retention['guidance_audit_days'])))]
        if self.execute('PRAGMA user_version').fetchone()[0] >= 3:
            result['knowledge_calls'] = [r['call_id'] for r in self.execute('''SELECT call_id FROM knowledge_calls
                WHERE environment_id=? AND kind='answer' AND state='completed' AND expires_at<=?
                AND NOT EXISTS (SELECT 1 FROM knowledge_calls k WHERE k.environment_id=? AND k.state IN ('running','uncertain'))
                AND NOT EXISTS (SELECT 1 FROM requests_state r WHERE r.environment_id=? AND (r.closed_at IS NULL OR r.incident_open=1))''',
                (env,stamp(now),env,env))]
        return result
