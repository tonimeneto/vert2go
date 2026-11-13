"""External I5 parameters. No condominium conditions are inferred or defaulted."""
from dataclasses import dataclass
from datetime import time
from decimal import Decimal
import re
from types import MappingProxyType
from app.core.contracts import EngineError, instant


def exact(value, names):
    if type(value) is not dict or set(value) != set(names):
        raise EngineError('operations_configuration_invalid')


@dataclass(frozen=True)
class OperationsConfig:
    live_authorized: bool
    calendar_id: str
    spreadsheet_id: str
    sheet_range: str
    units: object
    resources: object
    request_categories: object
    report_limit: int
    alternative_offsets_days: tuple
    reservation_exception_category: str
    calendar_cancel: bool = False
    legacy_units: object = None

    def require_live(self):
        if not self.live_authorized:
            raise EngineError('experimental_writes_authorization_required')


def parse_operations(raw, google):
    if raw is None:
        return None
    legacy=raw.get('legacy_units',{}) if type(raw) is dict else {}
    raw={k:v for k,v in raw.items() if k!='legacy_units'} if type(raw) is dict else raw
    exact(raw, ('authorization', 'units', 'resources', 'request_categories', 'report_limit','alternative_offsets_days',
                'reservation_exception_category'))
    if google is None or not google.calendar_id or not google.spreadsheet_id:
        raise EngineError('operations_google_resources_required')
    auth = raw['authorization']
    cancel=auth.get('calendar_cancel',False) if type(auth) is dict else False
    if type(cancel) is not bool:raise EngineError('operations_configuration_invalid')
    auth={k:v for k,v in auth.items() if k!='calendar_cancel'} if type(auth) is dict else auth
    exact(auth, ('calendar_id', 'spreadsheet_id', 'sheet_range', 'exclusive_pilot_resources',
                 'calendar_insert', 'sheets_update'))
    if (auth['calendar_id'] != google.calendar_id or auth['spreadsheet_id'] != google.spreadsheet_id
            or auth['sheet_range'] not in google.ranges):
        raise EngineError('operations_resource_mismatch')
    # A dedicated, finite A:J region is a journal, not an arbitrary append destination.
    if not re.fullmatch(r".+!A[1-9][0-9]*:J[1-9][0-9]*", auth['sheet_range']):
        raise EngineError('operations_sheet_range_invalid')
    for key in ('exclusive_pilot_resources', 'calendar_insert', 'sheets_update'):
        if type(auth[key]) is not bool:
            raise EngineError('operations_configuration_invalid')
    authorized = all(auth[k] for k in ('exclusive_pilot_resources', 'calendar_insert', 'sheets_update'))
    if cancel and not authorized:raise EngineError('operations_authorization_incomplete')
    if any(auth[k] for k in ('calendar_insert', 'sheets_update')) and not authorized:
        raise EngineError('operations_authorization_incomplete')
    units = raw['units']
    if (type(units) is not dict or not units or any(not re.fullmatch(r'[1-9][0-9]*', k)
            or type(v) is not str or not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', v) for k,v in units.items())):
        raise EngineError('operations_units_invalid')
    if (type(legacy) is not dict or not set(legacy)<=set(units) or any(type(v) is not list or not v
            or any(type(n) is not str or not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}',n) for n in v)
            for v in legacy.values())):
        raise EngineError('operations_units_invalid')
    resources = raw['resources']
    if type(resources) is not list or not 1 <= len(resources) <= 10:
        raise EngineError('operations_rules_invalid')
    parsed = {}
    for item in resources:
        exact(item, ('id', 'rule_id', 'status', 'source_document_id', 'source_title', 'section',
                     'source_revision', 'source_hash', 'verified_at', 'valid_until', 'opens', 'closes',
                     'max_duration_minutes', 'min_notice_hours', 'max_advance_days', 'fee_brl'))
        for key in ('id', 'rule_id'):
            if type(item[key]) is not str or not re.fullmatch(r'[a-z0-9_-]{1,64}', item[key]):
                raise EngineError('operations_rules_invalid')
        if item['id'] in parsed or item['status'] not in ('verified','simulated','unverified','conflicting'):
            raise EngineError('operations_rules_invalid')
        for key in ('source_document_id','source_title','section','source_revision','source_hash'):
            if type(item[key]) is not str or not 1 <= len(item[key]) <= 300:
                raise EngineError('operations_rules_invalid')
        if item['status'] == 'verified' and (item['source_document_id'] not in {d.id for d in google.documents if d.classification in ('official','authorized_operational')}
                or not re.fullmatch('[0-9a-f]{64}',item['source_hash'])):
            raise EngineError('operations_rules_invalid')
        if instant(item['valid_until']) <= instant(item['verified_at']):
            raise EngineError('operations_rules_invalid')
        try:
            if not (re.fullmatch(r'[0-2][0-9]:[0-5][0-9]',item['opens'])
                    and re.fullmatch(r'[0-2][0-9]:[0-5][0-9]',item['closes'])
                    and time.fromisoformat(item['opens']) < time.fromisoformat(item['closes'])):
                raise ValueError
            fee = Decimal(item['fee_brl']) if type(item['fee_brl']) is str else Decimal('NaN')
            if not fee.is_finite() or fee < 0 or fee.as_tuple().exponent < -2:
                raise ValueError
        except (ValueError, TypeError, ArithmeticError):
            raise EngineError('operations_rules_invalid') from None
        for key, low, high in (('max_duration_minutes',1,1440),('min_notice_hours',0,8760),('max_advance_days',1,366)):
            if type(item[key]) is not int or not low <= item[key] <= high:
                raise EngineError('operations_rules_invalid')
        parsed[item['id']] = MappingProxyType(dict(item))
    categories = raw['request_categories']
    if (type(categories) is not dict or not categories or any(type(k) is not str
            or not re.fullmatch(r'[a-z0-9_-]{1,64}',k) or v not in ('manager','unassigned') for k,v in categories.items())):
        raise EngineError('operations_configuration_invalid')
    exception_category = raw['reservation_exception_category']
    if type(exception_category) is not str or categories.get(exception_category) != 'manager':
        raise EngineError('operations_configuration_invalid')
    if type(raw['report_limit']) is not int or not 1 <= raw['report_limit'] <= 100:
        raise EngineError('operations_configuration_invalid')
    alternatives = raw['alternative_offsets_days']
    if (type(alternatives) is not list or not 1 <= len(alternatives) <= 5
            or any(type(v) is not int or not 1 <= v <= 14 for v in alternatives)
            or len(set(alternatives)) != len(alternatives)):
        raise EngineError('operations_configuration_invalid')
    return OperationsConfig(authorized,google.calendar_id,google.spreadsheet_id,auth['sheet_range'],
                            MappingProxyType(units),MappingProxyType(parsed),MappingProxyType(categories),raw['report_limit'],
                            tuple(alternatives),exception_category,cancel,MappingProxyType({k:tuple(v) for k,v in legacy.items()}))
