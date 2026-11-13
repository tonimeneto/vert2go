"""Internal structured contracts. Channel identity must come from a trusted adapter."""
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import StrEnum
import hashlib
import json
from zoneinfo import ZoneInfo


class EngineError(Exception):
    """Only fixed safe error codes cross the engine boundary."""
    def __init__(self, code):
        self.code = code
        super().__init__(code)


class GuidanceStatus(StrEnum):
    DRAFT = 'draft'
    ACTIVE = 'active'
    EXPIRED = 'expired'
    CANCELLED = 'cancelled'


class OperationState(StrEnum):
    RECEIVED = 'received'
    AWAITING_CONFIRMATION = 'awaiting_confirmation'
    COMMITTING = 'committing'
    CONFIRMED = 'confirmed'
    CONFLICTED = 'conflicted'
    NEEDS_RECONCILIATION = 'needs_reconciliation'
    FAILED = 'failed'
    CANCELLED = 'cancelled'


def utcnow():
    return datetime.now(timezone.utc)


def instant(value):
    try:
        result = datetime.fromisoformat(value) if isinstance(value, str) else value
        if not isinstance(result, datetime) or result.tzinfo is None or result.utcoffset() is None:
            raise ValueError
        return result.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError):
        raise EngineError('invalid_datetime') from None


def stamp(value):
    return instant(value).isoformat(timespec='microseconds')


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()


def relative_day_interval(received_at, day_offset, start_time, end_time):
    """Explicit clock bounds only; relative date is anchored to original message."""
    from datetime import time
    if type(day_offset) is not int:
        raise EngineError('invalid_datetime')
    try:
        zone = ZoneInfo('America/Sao_Paulo')
        day = instant(received_at).astimezone(zone).date() + timedelta(days=day_offset)
        start = datetime.combine(day, time.fromisoformat(start_time), zone)
        end = datetime.combine(day, time.fromisoformat(end_time), zone)
        if end <= start:
            raise ValueError
        return stamp(start), stamp(end)
    except (ValueError, TypeError):
        raise EngineError('clarification_required') from None


@dataclass(frozen=True)
class Scope:
    environment_id: str
    channel: str
    channel_user_id: int
    chat_id: int
    chat_type: str = 'private'

    def key(self):
        return (self.environment_id, self.channel, self.channel_user_id, self.chat_id)


@dataclass(frozen=True)
class Message:
    scope: Scope
    message_id: str
    received_at: datetime
    correlation_id: str
    text: str = ''
    update_id: str | None = None
    reply_to_message_id: int | None = None


@dataclass(frozen=True)
class Result:
    status: str
    code: str
    data: dict = field(default_factory=dict)

    def as_dict(self):
        return {'status': self.status, 'code': self.code, 'data': self.data}
