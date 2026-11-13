"""Collect a reservation progressively; availability always comes from Calendar."""
from datetime import datetime,timedelta
from dataclasses import replace
import re
from zoneinfo import ZoneInfo
from app.core.contracts import EngineError,instant,digest
from app.channels.reservation_time import fragments,plain,resource_in


class ReservationConversation:
    def __init__(self, conversation):
        self.conversation=conversation;self.engine=conversation.engine;self.dialog=conversation.dialog

    def state(self, message, context=None):
        if context and context.get('kind')=='clarification':
            saved=context.get('intent',{}).get('_reservation')
            if saved:return {key:value for key,value in saved.items() if key!='role'}
        data=self.dialog.get(message.scope,'reservation-fields')
        return {key:value for key,value in data.items() if key!='role'} if data and not data.get('closed') else {}

    def save(self,message,data):
        self.dialog.put(message.scope,'reservation-fields',data,
                        self.engine.clock()+timedelta(days=self.engine.config.retention['conversation_days']))

    def close(self,scope):
        self.dialog.put(scope,'reservation-fields',{'closed':True},self.engine.clock()+timedelta(days=1))

    def day_issues(self,data):
        if not data.get('resource') or not data.get('day'):return []
        zone=ZoneInfo(self.engine.config.timezone);now=instant(self.engine.clock()).astimezone(zone)
        first=datetime.fromisoformat(data['day']).replace(tzinfo=zone);last=first+timedelta(days=1)
        if (last<=now or last<=instant(self.engine.config.google.window_start)
                or first>=instant(self.engine.config.google.window_end)):
            return ['window']
        if first-now>timedelta(days=self.engine.config.operations.resources[data['resource']]['max_advance_days']):
            return ['advance']
        return []

    def date_fragments(self,message,data):
        values=fragments(message.text,message.received_at,self.engine.config.timezone)
        number=values.get('day_number')
        if number is None:return values
        known=data.get('day')
        if known and datetime.fromisoformat(known).day==number:
            return {**values,'dates':[known]}
        zone=ZoneInfo(self.engine.config.timezone)
        first=instant(self.engine.config.google.window_start).astimezone(zone).date()
        end=instant(self.engine.config.google.window_end).astimezone(zone)
        last=end.date() if end.time()!=datetime.min.time() else end.date()-timedelta(days=1)
        # Resolve a day number only when the externally authorized date window
        # identifies one calendar date. Never silently choose another month/year.
        month=first.replace(day=1);matches=[]
        while month<=last and len(matches)<2:
            try:date=month.replace(day=number)
            except ValueError:date=None
            if date and first<=date<=last:matches.append(date.isoformat())
            month=(month.replace(day=28)+timedelta(days=4)).replace(day=1)
        if len(matches)!=1:raise EngineError('reservation_date_ambiguous')
        return {**values,'dates':matches}

    def intent(self,data):
        from app.ai.operation_intent import FIELDS
        def bound(key,day):
            if not data.get(key) or not day:return None
            return datetime.fromisoformat(day+'T'+data[key]).replace(tzinfo=ZoneInfo(self.engine.config.timezone)).isoformat()
        return {**{key:None for key in FIELDS},'action':'reservation','requested_action':'reservation',
            'resource':data.get('resource'),'start':bound('start_time',data.get('day')),
            'end':bound('end_time',data.get('end_day') or data.get('day')),
            'urgent':False,'expected_version':None,'_reservation':dict(data)}

    def hints(self,resource):
        rule=self.engine.config.operations.resources.get(resource)
        if not rule:return ''
        duration=rule['max_duration_minutes'];limit=(str(duration//60)+(' hora' if duration==60 else ' horas') if duration%60==0 else str(duration)+' minutos')
        return f"Pelas condições cadastradas, o horário é das {rule['opens']} às {rule['closes']}, por até {limit} por reserva."

    def ask(self,message,data,field,text):
        data={**data,'awaiting':field};self.save(message,data)
        self.conversation._ask(message,self.intent(data),'resource' if field=='resource' else 'end' if field=='end_time' else 'start')
        return 'clarification_required',text

    def route_fragment(self,message,context):
        # A requested message body is data, even when it mentions booking or dates.
        if context and (context['kind']=='request_reply' or context['kind']=='clarification'
                and context.get('field') in ('response','content')):
            return None
        text=plain(message.text);data=self.state(message,context)
        booking=bool(re.search(r'\b(?:quero|gostaria|preciso)\b.*\breservar\b|^(?:por favor\s+)?(?:reserve|reserva|reservar)\b',text))
        if re.search(r'\bnao\b.*\breserv',text):booking=False
        if booking:self.engine.policy.authorize(message.scope,'reservation.create')
        available=bool(re.search(r'disponiv|disponibilidade|datas? livres?|horarios? livres?|quais(?: os)? horarios|qual data|que data|quais datas|qual dia|que dia|como\b.*\breserv',text))
        resource=resource_in(message.text,self.engine.config.operations.resources)
        if available and (resource or data.get('resource')):
            return self.availability(message,{**data,'resource':resource or data['resource']})
        if context and (context['kind'] in ('request_reply','sync') or context['kind']=='clarification' and
                context.get('intent',{}).get('action')!='reservation') and not booking:
            return None
        if booking and not (resource or data.get('resource')):
            return None
        try:values=self.date_fragments(message,data)
        except EngineError as error:
            if not booking and not data:return None
            return self.bad_fragment(message,{**data,'resource':resource or data.get('resource')},error.code)
        if data.get('goal')=='availability' and values['dates'] and not values['times'] and not booking:
            return self.availability(message,data)
        if booking or (data.get('resource') and (values['dates'] or values['times'])):
            return self.process(message,{'resource':resource or data.get('resource')},context,values,booking)
        if data and data.get('awaiting') and context and context['kind']=='clarification' and text.strip(' .!?') in ('sim','pode','ok','okay'):
            return self.question(message,data)
        return None

    def bad_fragment(self,message,data,code):
        date_error=code in ('reservation_date_invalid','reservation_date_ambiguous')
        if date_error:data={**data,'day':None,'end_day':None}
        else:data={**data,'end_time':None}
        text=('Preciso identificar uma única data. Qual é a data completa, com mês e ano?' if code=='reservation_date_ambiguous' else
              'Essa data está inválida. Qual dia você deseja?' if date_error else
              'Não consegui identificar um único horário válido. Que horas você quer começar e terminar?')
        return self.ask(message,data,'day' if date_error else 'start_time',text)

    def process(self,message,extracted,context=None,values=None,new_booking=False):
        self.engine.policy.authorize(message.scope,'reservation.create')
        data=self.state(message,context)
        if context and context['kind']=='proposal':
            rows=[r for r in self.conversation._pending(message) if r['operation_id']==context['operation_id'] and r['kind']=='reservation']
            if len(rows)==1:
                old=self.conversation._proposal_intent(message,rows[0]);zone=ZoneInfo(self.engine.config.timezone)
                a,b=instant(old['start']).astimezone(zone),instant(old['end']).astimezone(zone)
                data={**data,'resource':old['resource'],'day':a.date().isoformat(),'end_day':b.date().isoformat(),
                      'start_time':a.strftime('%H:%M'),'end_time':b.strftime('%H:%M')}
        if new_booking and (not context or context['kind']!='proposal'):
            data={key:data[key] for key in ('resource',) if key in data}
        resource=extracted.get('resource') or data.get('resource')
        if resource is not None and resource not in self.engine.config.operations.resources:
            resource=None
        data={**data,'resource':resource,'closed':False,'goal':'reservation'}
        if resource:
            rule=self.engine.config.operations.resources[resource]
            if rule['status'] not in ('verified','simulated'):raise EngineError('document_rule_requires_review')
            if not instant(rule['verified_at'])<=instant(self.engine.clock())<instant(rule['valid_until']):
                raise EngineError('document_rule_outdated')
        if values is None:
            try:values=self.date_fragments(message,data)
            except EngineError as error:return self.bad_fragment(message,data,error.code)
        dates,times=values['dates'],values['times']
        day_changed=bool(dates and data.get('day') and dates[0]!=data['day'])
        if dates:
            data['day']=dates[0];data['end_day']=dates[-1]
        if len(times)==2:data.update(start_time=times[0],end_time=times[1])
        elif len(times)==1:
            if values['end_only'] or (not day_changed and data.get('awaiting')=='end_time' and data.get('start_time') and times[0]>data['start_time']):
                data['end_time']=times[0]
            else:data['start_time']=times[0]
        self.save(message,data)
        issues=self.day_issues(data)
        if issues:return self.invalid_interval(message,data,issues)
        if 'dia inteiro' in plain(message.text):
            data['start_time']=None;data['end_time']=None
            return self.ask(message,data,'start_time','Não posso considerar o dia inteiro com as condições cadastradas. '+self.hints(resource)+' Quais horários você prefere?')
        if not resource or not data.get('day') or not data.get('start_time') or not data.get('end_time'):
            return self.question(message,data)
        intent=self.intent(data)
        issues=self.engine.operations.interval_issues(resource,intent['start'],intent['end'])
        if issues:return self.invalid_interval(message,data,issues)
        result=self.engine.handle(message,'propose_reservation',{key:intent[key] for key in ('resource','start','end')})
        if result.code=='pilot_proposal':
            self.conversation._remember_proposal(message,result)
            self.save(message,{**data,'awaiting':None})
            self.conversation._clear_clarification(message)
            if context and context['kind']=='proposal' and not new_booking:
                old=[r for r in self.conversation._pending(message) if r['operation_id']==context['operation_id'] and r['operation_id']!=result.data['operation_id']]
                if len(old)==1:self.dialog.decline(message,old[0])
        if result.code=='reservation_unavailable':
            return self.availability(message,data,lead='Esse intervalo tem conflito na Agenda. Vou consultar as faixas livres para esse dia.',secondary=True)
        return self.conversation.render(result)

    def question(self,message,data):
        if not data.get('resource'):
            return self.ask(message,data,'resource','Qual espaço você quer reservar?')
        if not data.get('day'):
            return self.ask(message,data,'day','Para qual dia você quer reservar esse espaço?')
        day=datetime.fromisoformat(data['day']).strftime('%d/%m/%Y')
        if not data.get('start_time'):
            return self.ask(message,data,'start_time',f'Para {day}, que horas você quer começar e terminar? '+self.hints(data['resource']))
        return self.ask(message,data,'end_time',f"Já tenho o dia {day} e o início às {data['start_time']}. Que horas você quer terminar? "+self.hints(data['resource']))

    def invalid_interval(self,message,data,issues):
        rule=self.engine.config.operations.resources[data['resource']]
        if 'past' in issues and data['day']==instant(self.engine.clock()).astimezone(ZoneInfo(self.engine.config.timezone)).date().isoformat() and not any(code in issues for code in ('advance','window')):
            return self.ask(message,{**data,'start_time':None,'end_time':None},'start_time',
                'Esse horário de início já passou hoje. Qual horário futuro você prefere? '+self.hints(data['resource']))
        if any(code in issues for code in ('past','advance','window','notice')):
            first=instant(self.engine.config.google.window_start).astimezone(ZoneInfo(self.engine.config.timezone)).strftime('%d/%m/%Y')
            last=instant(self.engine.config.google.window_end).astimezone(ZoneInfo(self.engine.config.timezone)).strftime('%d/%m/%Y às %H:%M')
            text=f'Essa data/horário está fora do prazo permitido: a reserva precisa começar no futuro, no período de {first} até {last} (fim exclusivo), com antecedência máxima de {rule["max_advance_days"]} dia(s) e mínima de {rule["min_notice_hours"]} hora(s). Para qual outra data você deseja consultar a Agenda?'
            return self.ask(message,{**data,'day':None,'end_day':None,'start_time':None,'end_time':None},'day',text)
        explanations=[]
        if 'same_day' in issues:explanations.append('O início e o término precisam ser no mesmo dia neste piloto.')
        if 'order' in issues:explanations.append('O término precisa ser depois do início.')
        if 'hours' in issues:explanations.append(f"O intervalo {data['start_time']}–{data['end_time']} ultrapassa o horário cadastrado.")
        if 'duration' in issues:
            a,b=instant(self.intent(data)['start']),instant(self.intent(data)['end']);minutes=int((b-a).total_seconds()/60)
            explanations.append(f'O intervalo informado dura {minutes//60}h{minutes%60:02d}, acima do limite de {rule["max_duration_minutes"]} minutos.')
        if data['start_time']<rule['opens'] or data['start_time']>=rule['closes']:
            return self.ask(message,{**data,'start_time':None,'end_time':None},'start_time',
                ' '.join(explanations)+' '+self.hints(data['resource'])+' Qual novo intervalo você prefere?')
        return self.ask(message,{**data,'end_time':None,'end_day':data['day']},'end_time',
            ' '.join(explanations)+' '+self.hints(data['resource'])+f" Mantive o dia e o início às {data['start_time']}. Que horário de término você prefere? Também posso consultar as faixas livres na Agenda.")

    def availability(self,message,data,lead='',secondary=False):
        self.engine.policy.authorize(message.scope,'reservation.read')
        data={**data,'goal':'availability','closed':False}
        self.save(message,data)
        try:values=self.date_fragments(message,data)
        except EngineError as error:return self.bad_fragment(message,data,error.code)
        if values['dates']:data={**data,'day':values['dates'][0]}
        issues=self.day_issues(data)
        if issues:return self.invalid_interval(message,data,issues)
        payload={'resource':data['resource']}
        if data.get('day'):payload['date']=data['day']
        query=(replace(message,message_id='availability_'+digest([message.scope.key(),message.message_id]),update_id=None)
               if secondary else message)
        result=self.engine.handle(query,'reservation_availability',payload)
        if result.code!='pilot_availability':return self.conversation.render(result)
        zone=ZoneInfo(self.engine.config.timezone);lines=[lead] if lead else []
        if not result.data['days']:
            lines.append('Não encontrei uma faixa livre nessa consulta, dentro do período e das condições cadastradas. Podemos consultar outra data permitida.')
        else:
            lines.append('Consultei a Agenda. Faixas livres encontradas:')
            for day in result.data['days']:
                spans=['das '+instant(f['start']).astimezone(zone).strftime('%H:%M')+' às '+instant(f['end']).astimezone(zone).strftime('%H:%M') for f in day['free']]
                lines.append(datetime.fromisoformat(day['date']).strftime('%d/%m/%Y')+': '+'; '.join(spans)+'.')
        lines.append(self.hints(data['resource']))
        lines.append('Qual intervalo, dentro de uma dessas faixas, você prefere? Essa consulta não cria uma reserva; vou pedir sua autorização antes de registrar.')
        self.ask(message,data,'start_time','')
        return 'pilot_availability','\n'.join(lines)
