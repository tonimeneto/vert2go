-- Durable channel receipts and delivery state; no secrets or raw updates.
CREATE TABLE telegram_poll_state (
 environment_id TEXT NOT NULL, bot_id INTEGER NOT NULL,
 next_offset INTEGER NOT NULL CHECK(next_offset>=0), updated_at TEXT NOT NULL,
 PRIMARY KEY(environment_id,bot_id)
);
CREATE TABLE telegram_updates (
 environment_id TEXT NOT NULL, bot_id INTEGER NOT NULL, update_id INTEGER NOT NULL,
 channel_user_id INTEGER NOT NULL, chat_id INTEGER NOT NULL, message_id INTEGER NOT NULL,
 request_hash TEXT NOT NULL, code TEXT NOT NULL,
 reply TEXT, state TEXT NOT NULL CHECK(state IN ('pending','sending','sent','uncertain','discarded','failed')),
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL, next_attempt_at TEXT NOT NULL,
 PRIMARY KEY(environment_id,bot_id,update_id),
 UNIQUE(environment_id,bot_id,chat_id,message_id)
);
CREATE INDEX telegram_delivery_idx ON telegram_updates(environment_id,bot_id,state,next_attempt_at);
