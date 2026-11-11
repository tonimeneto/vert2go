"""Local estimated budget ledger only. This module has no network client."""
from decimal import Decimal, ROUND_CEILING
from zoneinfo import ZoneInfo
from app.core.contracts import EngineError, canonical, digest, instant, stamp, utcnow
from app.services.operational_memory import identifier


def money(value):
    try:
        if type(value) not in (str,int,Decimal):
            raise ValueError
        amount = Decimal(value)
        if not amount.is_finite() or amount<0:
            raise ValueError
        return amount
    except (ValueError,ArithmeticError):
        raise EngineError('invalid_measurement') from None


class LocalBudget:
    def __init__(self, config, store, clock=utcnow):
        self.config, self.store, self.clock = config, store, clock

    def period(self, at):
        return instant(at).astimezone(ZoneInfo(self.config.timezone)).strftime('%Y-%m')

    def assess(self, estimated_next_brl='0', at=None):
        at = self.clock() if at is None else at
        period = self.period(at)
        rows = self.store.execute("""SELECT measured,cost_brl FROM usage_ledger
            WHERE environment_id=? AND period=?""", (self.config.environment_id,period)).fetchall()
        total = sum((Decimal(r['cost_brl']) for r in rows if r['measured']),Decimal(0))
        missing = any(not r['measured'] for r in rows)
        cfg = self.config.openai
        blocked = missing or total>=cfg['monthly_budget_brl'] or total+money(estimated_next_brl)>cfg['monthly_budget_brl']
        return {'period':period,'estimated_brl':str(total),'alert':total>=cfg['alert_brl'],
                'allowed':not blocked,'reason':'measurement_missing' if missing else ('budget_blocked' if blocked else 'available')}

    def record_simulated(self, usage_id, input_tokens, output_tokens, at=None,
                         searches=0, search_usd='0', storage_usd='0'):
        identifier(usage_id)
        at = instant(self.clock() if at is None else at)
        for value in (input_tokens,output_tokens,searches):
            if value is not None and (type(value) is not int or value<0):
                raise EngineError('invalid_measurement')
        search_cost = money(search_usd) if search_usd is not None else None
        storage_cost = money(storage_usd) if storage_usd is not None else None
        measured = all(v is not None for v in (input_tokens,output_tokens,searches,search_cost,storage_cost))
        # Search cost is a total supplied by a local fixture, never a fetched price.
        cfg = self.config.openai
        cost_usd = (Decimal(input_tokens)*cfg['input_usd_per_million']/1000000
                    + Decimal(output_tokens)*cfg['output_usd_per_million']/1000000
                    + search_cost + storage_cost) if measured else None
        cost_brl = (cost_usd*cfg['usd_brl']).quantize(Decimal('0.000001'),rounding=ROUND_CEILING) if measured else None
        assumption = {key:str(value) for key,value in cfg.items()}
        assumption['simulation'] = True
        content = {'at':stamp(at),'input':input_tokens,'output':output_tokens,'searches':searches,
                   'search_usd':str(search_cost),'storage_usd':str(storage_cost),'assumption':assumption}
        payload_hash = digest(content)
        with self.store.transaction():
            existing = self.store.execute("""SELECT payload_hash FROM usage_ledger WHERE
                environment_id=? AND usage_id=?""", (self.config.environment_id,usage_id)).fetchone()
            if existing:
                if existing['payload_hash'] != payload_hash:
                    raise EngineError('usage_identity_conflict')
            else:
                self.store.execute("""INSERT INTO usage_ledger
                    (environment_id,usage_id,period,occurred_at,model,input_tokens,output_tokens,searches,
                     storage_usd,cost_usd,cost_brl,measured,assumption,payload_hash)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (self.config.environment_id,usage_id,self.period(at),stamp(at),'local-fictional',
                     input_tokens,output_tokens,searches,str(storage_cost) if storage_cost is not None else None,
                     str(cost_usd) if measured else None,str(cost_brl) if measured else None,
                     int(measured),canonical(assumption),payload_hash))
        return self.assess(at=at)
