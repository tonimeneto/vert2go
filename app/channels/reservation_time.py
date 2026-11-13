"""Ground reservation date/time fragments in what the person actually said."""
from datetime import datetime,timedelta
import re
import unicodedata
from zoneinfo import ZoneInfo
from app.core.contracts import EngineError,instant


def plain(text):
    return ' '.join(''.join(c for c in unicodedata.normalize('NFD',text.casefold()) if unicodedata.category(c)!='Mn').split())


DATE=re.compile(r'\b(\d{1,2})/(\d{1,2})/(\d{4})\b')
CLOCK=re.compile(r'\b(\d{1,2})(?::(\d{2})|h(\d{2})?\b)(?:\s+da\s+(manha|tarde|noite))?')
SHORT=re.compile(r'\b(?:as|das|ate(?:\s+as)?)\s+(\d{1,2})(?![\d/:h])\b(?:\s+horas?)?(?:\s+da\s+(manha|tarde|noite))?')
BARE_RANGE=re.compile(r'\b(\d{1,2})\s+(?:as|a|ate)\s+(\d{1,2})\b')
NUMBERS={'zero':0,'uma':1,'um':1,'duas':2,'dois':2,'tres':3,'quatro':4,'cinco':5,
         'seis':6,'sete':7,'oito':8,'nove':9,'dez':10,'onze':11,'doze':12,
         'treze':13,'catorze':14,'quatorze':14,'quinze':15,'dezesseis':16,
         'dezessete':17,'dezoito':18,'dezenove':19,'vinte':20,
         'vinte e uma':21,'vinte e um':21,'vinte e duas':22,'vinte e dois':22,'vinte e tres':23,
         'meio-dia':12,'meia-noite':0}
WEEKDAYS={'segunda':0,'terca':1,'quarta':2,'quinta':3,'sexta':4,'sabado':5,'domingo':6}
SPOKEN=re.compile(r'\b(?:as|das|ao|a|ate(?:\s+as)?)\s+('+ '|'.join(sorted(NUMBERS,key=len,reverse=True))+r')\b'
                  r'(\s+e\s+meia)?(?:\s+da\s+(manha|tarde|noite))?')


def fragments(text, received_at, timezone):
    value=plain(text);zone=ZoneInfo(timezone);dates=[]
    date_matches=list(DATE.finditer(value))
    for match in date_matches:
        try:dates.append(datetime(int(match[3]),int(match[2]),int(match[1])).date().isoformat())
        except ValueError:raise EngineError('reservation_date_invalid') from None
    alternatives=(len(date_matches)==2 and re.search(r'\bou\b',value[date_matches[0].end():date_matches[1].start()]))
    if len(dates)>2 or alternatives:
        raise EngineError('reservation_date_ambiguous')
    if not dates:
        if re.search(r'\b(?:hoje|amanha|depois de amanha)\b',value):
            offset=2 if 'depois de amanha' in value else 1 if 'amanha' in value else 0
            dates=[(instant(received_at).astimezone(zone).date()+timedelta(days=offset)).isoformat()]
        else:
            weekdays=[number for name,number in WEEKDAYS.items() if re.search(r'\b'+name+r'(?:-feira)?\b',value)]
            if len(weekdays)>1:raise EngineError('reservation_date_ambiguous')
            if weekdays:
                original=instant(received_at).astimezone(zone).date();offset=(weekdays[0]-original.weekday())%7
                if not offset and 'proxima' in value:offset=7
                dates=[(original+timedelta(days=offset)).isoformat()]
    clocks=[];spans=[]
    for match in CLOCK.finditer(value):
        clocks.append((match.start(),int(match[1]),int(match[2] or match[3] or 0),match[4]))
        spans.append(match.span())
    for match in SHORT.finditer(value):
        if not any(a<=match.start()<b or match.start()<=a<match.end() for a,b in spans):
            clocks.append((match.start(),int(match[1]),0,match[2]))
    for match in SPOKEN.finditer(value):
        clocks.append((match.start(),NUMBERS[match[1]],30 if match[2] else 0,match[3]))
    bare=BARE_RANGE.search(value)
    if bare and len(clocks)<2:
        clocks=[(bare.start(),int(bare[1]),0,None),(bare.start(2),int(bare[2]),0,None)]
    alone=re.fullmatch(r'\s*(\d{1,2})(?:\s+horas?)?\s*',value)
    if not clocks and alone:clocks=[(0,int(alone[1]),0,None)]
    if len(clocks)>2:raise EngineError('reservation_time_ambiguous')
    clocks.sort();periods={period for _,_,_,period in clocks if period}
    if len(clocks)==2 and re.search(r'\bou\b',value[clocks[0][0]:clocks[1][0]]):
        raise EngineError('reservation_time_ambiguous')
    shared=next(iter(periods)) if len(periods)==1 else None
    times=[]
    for _,hour,minute,period in clocks:
        period=period or shared
        if period in ('tarde','noite') and hour<12:hour+=12
        if not 0<=hour<=23 or not 0<=minute<=59:raise EngineError('reservation_time_invalid')
        times.append(f'{hour:02}:{minute:02}')
    end_only=bool(times and len(times)==1 and re.search(r'\b(?:ate|terminar|termina|termino|fim|finalizar)\b',value))
    partial=re.findall(r'\bdia\s+(\d{1,2})(?![\d/])\b',value) if not dates else []
    if len(partial)>1:raise EngineError('reservation_date_ambiguous')
    day_number=int(partial[0]) if partial else None
    if day_number is not None and not 1<=day_number<=31:raise EngineError('reservation_date_invalid')
    return {'dates':dates,'times':times,'end_only':end_only,'day_number':day_number}


def resource_in(text, resources):
    value=plain(text);matches=[key for key in resources if re.search(r'\b'+re.escape(plain(key).replace('_',' '))+r'\b',value)]
    matches.sort(key=len,reverse=True)
    if matches and all(plain(key).replace('_',' ') in plain(matches[0]).replace('_',' ') for key in matches):return matches[0]
    return None
