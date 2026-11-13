-- Additive I5 extension: never replace the original reservation or its audit trail.
CREATE TABLE pilot_cancellations (
 environment_id TEXT NOT NULL, operation_id TEXT NOT NULL,
 channel TEXT NOT NULL, channel_user_id INTEGER NOT NULL, chat_id INTEGER NOT NULL,
 reservation_id TEXT NOT NULL, input_hash TEXT NOT NULL,
 proposal TEXT NOT NULL CHECK(json_valid(proposal)), proposal_hash TEXT NOT NULL,
 state TEXT NOT NULL CHECK(state IN ('awaiting_confirmation','committing','needs_reconciliation','confirmed','cancelled','failed')),
 result TEXT CHECK(result IS NULL OR json_valid(result)),
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL, expires_at TEXT NOT NULL, closed_at TEXT,
 PRIMARY KEY(environment_id,operation_id),
 FOREIGN KEY(environment_id,reservation_id) REFERENCES pilot_operations(environment_id,operation_id)
);
CREATE UNIQUE INDEX one_effective_cancellation ON pilot_cancellations(environment_id,reservation_id)
 WHERE state IN ('committing','needs_reconciliation','confirmed');
