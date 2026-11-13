"""Natural cancellation selection using only the caller's Calendar-verified bookings."""
from dataclasses import replace
from datetime import datetime
import re
from zoneinfo import ZoneInfo
from app.core.contracts import EngineError,digest,instant
from app.channels.reservation_time import plain,resource_in


class CancellationConversation:
    def __init__(self,conversation):
        self.conversation=conversation;self.engine=conversation.engine;self.dialog=conversation.dialog

    def route(self,message,context):
        if context and (context['kind']=='request_reply' or context['kind']=='clarification' and context.get('field') in ('response','content')):
            return None
        text=plain(message.text)
        if text.startswith('/'):return None
        if context and context['kind']=='cancellation_retry' and re.search(r'\b(?:tente|tenta|tentar)\b.*\b(?:novamente|novo)\b',text):
            row=self.engine.operations.cancellations.row(message,context['operation_id'])
            result=self.engine.handle(message,'propose_reservation_cancellation',{'reservation_id':row['reservation_id'],'retry':True})
            self.conversation._remember_proposal(message,result)
            return self.present(message,result)
        cancel=bool(re.search(r'\b(?:cancelar|cancele|cancela|desmarcar|desmarque|desmarca|desistir)\b',text))
        if context and context['kind']=='proposal':
            # An answer authorizes/declines that exact proposal; never reinterpret it.
            from app.channels.operation_dialog import authorization_phrase,words
            if authorization_phrase(words(message.text)):return None
        if cancel and re.search(r'\b(?:orientacao|aviso|comunicado)\b',text):return None
        if cancel and not re.search(r'\b(?:reserva|reservas|salao|agendamento)\b',text) and not (context and context['kind']=='cancellation_choice'):
            return None
        if cancel and re.search(r'\b(?:nao|não)\b.*\b(?:cancelar|desmarcar)\b',text):return None
        if not cancel and re.search(r'\b(?:quero|preciso|gostaria)\b.*\b(?:reservar|registrar|consultar|sincronizar|responder)\b',text):return None
        if cancel or context and context['kind']=='cancellation_choice':
            return self.process(message,context)
        return None

    def process(self,message,context=None):
        self.engine.policy.authorize(message.scope,'reservation.cancel')
        query=replace(message,message_id='cancel_lookup_'+digest([message.scope.key(),message.message_id]),update_id=None)
        resource=resource_in(message.text,self.engine.config.operations.resources)
        result=self.engine.handle(query,'my_reservations',{'resource':resource} if resource else {})
        if result.code!='own_reservations':return self.conversation.render(result)
        all_rows=result.data['reservations'];rows=all_rows
        text=plain(message.text).strip(' .!?')
        ordinal={'a primeira':0,'primeira':0,'a segunda':1,'segunda':1,'a terceira':2,'terceira':2}
        choice=ordinal.get(text)
        if re.fullmatch(r'(?:opcao |a |numero )?\d+',text):choice=int(re.search(r'\d+',text)[0])-1
        if choice is not None and context and context['kind']=='cancellation_choice':
            ids=context['candidates']
            if not 0<=choice<len(ids):return self.ask(message,[r for r in all_rows if r['operation_id'] in ids])
            rows=[r for r in all_rows if r['operation_id']==ids[choice]]
        else:
            try:values=self.conversation.reservations.date_fragments(message,{})
            except EngineError:
                return self.ask(message,rows,'Não consegui identificar uma única data/horário. ')
            zone=ZoneInfo(self.engine.config.timezone)
            if values['dates']:rows=[r for r in rows if instant(r['start']).astimezone(zone).date().isoformat()==values['dates'][0]]
            times=values['times']
            if times:
                def clocks(r):return (instant(r['start']).astimezone(zone).strftime('%H:%M'),instant(r['end']).astimezone(zone).strftime('%H:%M'))
                exact=[r for r in rows if clocks(r)==tuple(times)] if len(times)==2 else []
                matching=exact or ([r for r in rows if clocks(r)[0]<times[1] and times[0]<clocks(r)[1]] if len(times)==2 else [r for r in rows if clocks(r)[0]==times[0]])
                if not matching:
                    return self.ask(message,rows,'Não encontrei uma reserva sua com esse horário. ')
                if not exact and len(times)==2:
                    return self.ask(message,matching,'O intervalo informado não coincide com uma reserva inteira. Ele cruza estes registros: ')
                rows=matching
        if not rows:return 'reservation_not_found','Não encontrei uma reserva sua correspondente. Pode informar a data e os horários da reserva que deseja cancelar?'
        if len(rows)>1:return self.ask(message,rows)
        row=rows[0]
        result=self.engine.handle(message,'propose_reservation_cancellation',{'reservation_id':row['operation_id']})
        self.conversation._remember_proposal(message,result)
        return self.present(message,result)

    def present(self,message,result):
        code,reply=self.conversation.render(result)
        if code=='cancellation_reconciliation_required':
            self.dialog.output(message,{'kind':'cancellation_retry','operation_id':result.data['operation_id']})
            reply+=' Se quiser tentar novamente, diga isso por aqui. Vou conferir a Agenda e, se ainda for necessário, apresentar uma nova proposta e pedir outra autorização.'
        return code,reply

    def ask(self,message,rows,lead=''):
        if not rows:return 'reservation_not_found','Não encontrei reservas suas para esse pedido. Informe a data e os horários para eu conferir.'
        zone=ZoneInfo(self.engine.config.timezone);rows=sorted(rows,key=lambda r:r['start'])
        lines=[lead+'Qual destas reservas você quer cancelar integralmente?']
        for i,r in enumerate(rows,1):
            a,b=instant(r['start']).astimezone(zone),instant(r['end']).astimezone(zone)
            lines.append(f'{i}. '+a.strftime('%d/%m/%Y')+' das '+a.strftime('%H:%M')+' às '+b.strftime('%H:%M')+(' (já cancelada)' if r['state']=='cancelled' else ''))
        lines.append('Diga a data e os horários ou escolha uma das opções. Depois mostro os dados e peço sua autorização; ainda não cancelei nada.')
        self.dialog.output(message,{'kind':'cancellation_choice','candidates':[r['operation_id'] for r in rows]})
        return 'cancellation_choice_required','\n'.join(lines)
