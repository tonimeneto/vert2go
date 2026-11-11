-- I1 / 001_initial. Nine application tables; PRAGMA user_version tracks migration.
CREATE TABLE conversation_state (
 environment_id TEXT NOT NULL, channel TEXT NOT NULL, channel_user_id INTEGER NOT NULL,
 chat_id INTEGER NOT NULL, state_key TEXT NOT NULL, payload TEXT NOT NULL CHECK(json_valid(payload)),
 updated_at TEXT NOT NULL, expires_at TEXT NOT NULL,
 PRIMARY KEY(environment_id,channel,channel_user_id,chat_id,state_key)
);
CREATE TABLE requests_state (
 environment_id TEXT NOT NULL, operation_id TEXT NOT NULL, idempotency_key TEXT NOT NULL,
 channel TEXT NOT NULL, channel_user_id INTEGER NOT NULL, chat_id INTEGER NOT NULL,
 kind TEXT NOT NULL CHECK(kind IN ('create','correct','cancel')),
 guidance_id TEXT NOT NULL, expected_version INTEGER, proposal_hash TEXT NOT NULL,
 state TEXT NOT NULL CHECK(state IN ('received','awaiting_confirmation','committing','confirmed','conflicted','needs_reconciliation','failed','cancelled')),
 result TEXT CHECK(result IS NULL OR json_valid(result)),
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL, expires_at TEXT NOT NULL, closed_at TEXT,
 incident_open INTEGER NOT NULL DEFAULT 0 CHECK(incident_open IN (0,1)),
 incident_reason TEXT, CHECK(incident_open=0 OR length(incident_reason)>0),
 PRIMARY KEY(environment_id,operation_id), UNIQUE(environment_id,idempotency_key)
);
CREATE TABLE processed_messages (
 environment_id TEXT NOT NULL, channel TEXT NOT NULL, channel_user_id INTEGER NOT NULL,
 chat_id INTEGER NOT NULL, message_id TEXT NOT NULL, update_id TEXT,
 request_hash TEXT NOT NULL, operation_id TEXT, result TEXT NOT NULL CHECK(json_valid(result)),
 created_at TEXT NOT NULL,
 PRIMARY KEY(environment_id,channel,channel_user_id,chat_id,message_id),
 UNIQUE(environment_id,channel,update_id),
 FOREIGN KEY(environment_id,operation_id) REFERENCES requests_state(environment_id,operation_id)
);
CREATE TABLE operational_guidance (
 environment_id TEXT NOT NULL, guidance_id TEXT NOT NULL, current_version INTEGER NOT NULL CHECK(current_version>0),
 status TEXT NOT NULL CHECK(status IN ('active','expired','cancelled')),
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL, retired_at TEXT,
 incident_open INTEGER NOT NULL DEFAULT 0 CHECK(incident_open IN (0,1)), incident_reason TEXT,
 CHECK(incident_open=0 OR length(incident_reason)>0),
 PRIMARY KEY(environment_id,guidance_id),
 FOREIGN KEY(environment_id,guidance_id,current_version)
 REFERENCES operational_guidance_revisions(environment_id,guidance_id,version) DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE operational_guidance_revisions (
 environment_id TEXT NOT NULL, guidance_id TEXT NOT NULL, version INTEGER NOT NULL CHECK(version>0),
 operation_id TEXT NOT NULL, author_channel_user_id INTEGER NOT NULL,
 topic TEXT NOT NULL, content TEXT NOT NULL, audience TEXT NOT NULL CHECK(audience IN ('residents','managers')),
 effective_from TEXT NOT NULL, effective_until TEXT NOT NULL CHECK(effective_until>effective_from),
 timezone TEXT NOT NULL CHECK(timezone='America/Sao_Paulo'),
 status TEXT NOT NULL CHECK(status IN ('active','expired','cancelled')),
 confirmation_at TEXT NOT NULL, confirmation_ref TEXT NOT NULL, proposal_hash TEXT NOT NULL,
 supersedes_version INTEGER, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 CHECK((version=1 AND supersedes_version IS NULL) OR supersedes_version=version-1),
 PRIMARY KEY(environment_id,guidance_id,version), UNIQUE(environment_id,operation_id),
 FOREIGN KEY(environment_id,guidance_id) REFERENCES operational_guidance(environment_id,guidance_id) DEFERRABLE INITIALLY DEFERRED,
 FOREIGN KEY(environment_id,guidance_id,supersedes_version) REFERENCES operational_guidance_revisions(environment_id,guidance_id,version),
 FOREIGN KEY(environment_id,operation_id) REFERENCES requests_state(environment_id,operation_id)
);
CREATE TABLE operation_log (
 audit_id TEXT PRIMARY KEY, environment_id TEXT NOT NULL, at_time TEXT NOT NULL,
 actor_pseudonym TEXT NOT NULL, role TEXT NOT NULL, operation TEXT NOT NULL,
 operation_id TEXT, entity_id TEXT, version INTEGER, previous_state TEXT, next_state TEXT,
 result TEXT NOT NULL, correlation_id TEXT NOT NULL, confirmation_ref TEXT, safe_error TEXT,
 incident_open INTEGER NOT NULL DEFAULT 0 CHECK(incident_open IN (0,1)), incident_reason TEXT,
 CHECK(incident_open=0 OR length(incident_reason)>0)
);
CREATE TABLE sync_outbox (
 environment_id TEXT NOT NULL, outbox_id TEXT NOT NULL, operation_id TEXT NOT NULL,
 target TEXT NOT NULL, state TEXT NOT NULL CHECK(state IN ('pending','needs_reconciliation','synced','failed')),
 attempts INTEGER NOT NULL DEFAULT 0 CHECK(attempts>=0), safe_error TEXT,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 PRIMARY KEY(environment_id,outbox_id), UNIQUE(environment_id,operation_id,target),
 FOREIGN KEY(environment_id,operation_id) REFERENCES requests_state(environment_id,operation_id)
);
CREATE TABLE document_sync_metadata (
 environment_id TEXT NOT NULL, source_id TEXT NOT NULL, source_revision TEXT NOT NULL,
 source_hash TEXT NOT NULL, classification TEXT NOT NULL CHECK(classification IN ('official','authorized_operational','simulation','unverified')),
 indexed_file_id TEXT, vector_store_id TEXT,
 status TEXT NOT NULL CHECK(status IN ('pending','synced','outdated','failed')),
 updated_at TEXT NOT NULL, safe_error TEXT, PRIMARY KEY(environment_id,source_id)
);
CREATE TABLE usage_ledger (
 environment_id TEXT NOT NULL, usage_id TEXT NOT NULL, period TEXT NOT NULL, occurred_at TEXT NOT NULL,
 model TEXT NOT NULL, input_tokens INTEGER CHECK(input_tokens>=0), output_tokens INTEGER CHECK(output_tokens>=0),
 searches INTEGER CHECK(searches>=0), storage_usd TEXT,
 cost_usd TEXT, cost_brl TEXT, measured INTEGER NOT NULL CHECK(measured IN (0,1)),
 assumption TEXT NOT NULL CHECK(json_valid(assumption)), payload_hash TEXT NOT NULL,
 PRIMARY KEY(environment_id,usage_id)
);
CREATE INDEX request_state_idx ON requests_state(environment_id,state,updated_at);
CREATE INDEX message_retention_idx ON processed_messages(environment_id,created_at);
CREATE INDEX guidance_status_idx ON operational_guidance(environment_id,status);
CREATE INDEX guidance_topic_idx ON operational_guidance_revisions(environment_id,topic,audience,effective_from,effective_until);
CREATE INDEX audit_entity_idx ON operation_log(environment_id,entity_id,at_time);
CREATE INDEX usage_period_idx ON usage_ledger(environment_id,period);
CREATE INDEX outbox_state_idx ON sync_outbox(environment_id,state);
