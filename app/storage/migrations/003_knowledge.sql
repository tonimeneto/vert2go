-- Opt-in I4 migration. I1/I2/I3 callers stay on schema 2 until explicitly enabled.
CREATE TABLE knowledge_calls (
 environment_id TEXT NOT NULL, call_id TEXT NOT NULL, request_hash TEXT NOT NULL,
 kind TEXT NOT NULL CHECK(kind IN ('answer','store','upload','attach')),
 state TEXT NOT NULL CHECK(state IN ('running','completed','uncertain','failed')),
 scope_hash TEXT NOT NULL, remote_id TEXT,
 result TEXT CHECK(result IS NULL OR json_valid(result)),
 reserved_brl TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, expires_at TEXT NOT NULL,
 PRIMARY KEY(environment_id,call_id)
);
CREATE TABLE knowledge_versions (
 environment_id TEXT NOT NULL, source_id TEXT NOT NULL, source_hash TEXT NOT NULL,
 source_revision TEXT NOT NULL, vector_store_id TEXT NOT NULL, indexed_file_id TEXT,
 status TEXT NOT NULL CHECK(status IN ('pending','synced','outdated','failed')),
 updated_at TEXT NOT NULL,
 PRIMARY KEY(environment_id,source_id,source_hash,vector_store_id)
);
CREATE TABLE knowledge_storage (
 environment_id TEXT NOT NULL, vector_store_id TEXT NOT NULL, usage_bytes INTEGER NOT NULL CHECK(usage_bytes>=0),
 accounted_at TEXT NOT NULL, checked_at TEXT NOT NULL,
 PRIMARY KEY(environment_id,vector_store_id)
);
CREATE INDEX knowledge_uncertain_idx ON knowledge_calls(environment_id,state);
