"""Parse only a fully explicit Brazilian interval; never infer dates or a year."""
from datetime import datetime
import re
from zoneinfo import ZoneInfo
from app.core.contracts import EngineError

DAY=re.compile(r'\b\d{1,2}/\d{1,2}/\d{4}\b')
MOMENT=re.compile(
    r'(?P<date>\b\d{1,2}/\d{1,2}/\d{4})\s+[àa]s\s+(?P<hour>\d{1,2})'
    r'(?:h(?P<hminute>\d{2})?|:(?P<cminute>\d{2})|\s+horas?)\b',re.I)


def explicit_interval(text, timezone):
    """Return the exact stated bounds, or None when this narrow grammar is ambiguous.

    Both dates, both clock times and Brasilia timezone must be explicit. Other
    natural wording remains with the interpreter and cannot be filled here.
    """
    if (len(DAY.findall(text))!=2 or re.search(r'\b(?:UTC|GMT)\b',text,re.I)
            or not re.search(r'hor[aá]rio\s+(?:de\s+)?Bras[ií]lia\b',text,re.I)):
        return None
    matches=list(MOMENT.finditer(text))
    if len(matches)!=2 or not re.fullmatch(r'\s*at[eé]\s*',text[matches[0].end():matches[1].start()],re.I):
        return None
    if re.search(r'\bou\b',text[matches[0].start():],re.I):
        return None
    result=[]
    for match in matches:
        try:
            day,month,year=map(int,match['date'].split('/'))
            minute=int(match['hminute'] or match['cminute'] or 0)
            value=datetime(year,month,day,int(match['hour']),minute,tzinfo=ZoneInfo(timezone))
        except ValueError:
            raise EngineError('invalid_datetime') from None
        result.append(value.isoformat())
    return tuple(result)
