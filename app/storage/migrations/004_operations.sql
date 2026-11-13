-- I5 opt-in. Agenda remains the only source of reservation existence/availability.
CREATE TABLE pilot_operations (
 environment_id TEXT NOT NULL, operation_id TEXT NOT NULL,
 channel TEXT NOT NULL, channel_user_id INTEGER NOT NULL, chat_id INTEGER NOT NULL,
 kind TEXT NOT NULL CHECK(kind IN ('reservation','request','response')),
 input_hash TEXT NOT NULL, proposal TEXT NOT NULL CHECK(json_valid(proposal)), proposal_hash TEXT NOT NULL,
 state TEXT NOT NULL CHECK(state IN ('awaiting_confirmation','committing','confirmed','conflicted','needs_reconciliation','failed','cancelled')),
 external_reference TEXT, result TEXT CHECK(result IS NULL OR json_valid(result)),
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL, expires_at TEXT NOT NULL, closed_at TEXT,
 PRIMARY KEY(environment_id,operation_id)
);
CREATE TABLE pilot_receipts (
 environment_id TEXT NOT NULL, channel TEXT NOT NULL, channel_user_id INTEGER NOT NULL,
 chat_id INTEGER NOT NULL, message_id TEXT NOT NULL, update_id TEXT, request_hash TEXT NOT NULL,
 operation_id TEXT, result TEXT NOT NULL CHECK(json_valid(result)), created_at TEXT NOT NULL,
 PRIMARY KEY(environment_id,channel,channel_user_id,chat_id,message_id),
 UNIQUE(environment_id,channel,update_id)
);
CREATE TABLE pilot_requests (
 environment_id TEXT NOT NULL, request_id TEXT NOT NULL,
 channel TEXT NOT NULL, channel_user_id INTEGER NOT NULL, chat_id INTEGER NOT NULL,
 unit_reference TEXT NOT NULL, category TEXT NOT NULL, content TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('received','pending','forwarded','resolved','closed','failed')),
 assigned_to TEXT NOT NULL CHECK(assigned_to IN ('manager','unassigned')),
 urgent INTEGER NOT NULL CHECK(urgent IN (0,1)), version INTEGER NOT NULL,
 response TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, closed_at TEXT,
 PRIMARY KEY(environment_id,request_id)
);
CREATE TABLE pilot_outbox (
 environment_id TEXT NOT NULL, outbox_id TEXT NOT NULL, operation_id TEXT NOT NULL,
 target_id TEXT NOT NULL, target_range TEXT NOT NULL,
 row_number INTEGER, payload TEXT NOT NULL CHECK(json_valid(payload)),
 state TEXT NOT NULL CHECK(state IN ('pending','needs_reconciliation','synced','failed')),
 attempts INTEGER NOT NULL DEFAULT 0, safe_error TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 PRIMARY KEY(environment_id,outbox_id), UNIQUE(environment_id,row_number)
);
CREATE TABLE pilot_notifications (
 environment_id TEXT NOT NULL, notification_id TEXT NOT NULL,
 channel TEXT NOT NULL, channel_user_id INTEGER NOT NULL, chat_id INTEGER NOT NULL,
 request_id TEXT NOT NULL, response_version INTEGER NOT NULL, reply TEXT NOT NULL,
 state TEXT NOT NULL CHECK(state IN ('pending','queued','uncertain')),
 created_at TEXT NOT NULL, PRIMARY KEY(environment_id,notification_id),
 UNIQUE(environment_id,request_id,response_version)
);
CREATE INDEX pilot_state_idx ON pilot_operations(environment_id,state);
CREATE INDEX pilot_outbox_idx ON pilot_outbox(environment_id,state);
