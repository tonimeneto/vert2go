"""Replay actual failed wording, with grounded fields and real Calendar contract mocks."""
from datetime import datetime,timezone
from app.config.schema import _parse_config
from app.channels.reservation_time import fragments
from tests.test_natural_authorization import TelegramConversationCase


class ReservationConversationTests(TelegramConversationCase):
    def setUp(self):
        super().setUp()
        self.clock.now=datetime(2026,11,12,21,0,tzinfo=timezone.utc)
        self.raw['google']['calendar']['window_start']='2026-11-10T00:00:00-03:00'
        self.raw['google']['calendar']['window_end']='2026-11-17T00:00:00-03:00'
        self.raw['operations']['resources'][0]['max_advance_days']=5
        self.raw['operations']['resources'][0]['valid_until']='2026-11-17T00:00:00-03:00'
        self.config=_parse_config(self.raw);self.bind();self.build()
        self.calendar.events['busy-on-sixteenth']={'id':'busy-on-sixteenth','status':'confirmed',
            'start':{'dateTime':'2026-11-16T10:00:00-03:00'},'end':{'dateTime':'2026-11-16T11:00:00-03:00'}}
        self.interpreter.interpret.side_effect=AssertionError('Grounded date fragments must not need a model')

    def latest(self,actor=1001):
        return self.api.sent[self.last_for(actor)-1]['text']

    def start_date_only(self):
        return self.send(1,'Olá quero reservar o salão de festas dia 16/11/2026')

    def test_actual_failed_transcript_is_progressive_and_explains_constraints(self):
        self.assertEqual(self.start_date_only(),'clarification_required')
        self.assertIn('16/11/2026',self.latest());self.assertIn('começar e terminar',self.latest())
        self.assertNotIn('intervalo não atende',self.latest())
        self.assertEqual(self.store.execute('SELECT count(*) FROM pilot_operations').fetchone()[0],0)
        reads=self.calendar.reads
        self.assertEqual(self.send(2,'Qual data disponível?'),'pilot_availability')
        self.assertGreater(self.calendar.reads,reads)
        self.assertIn('08:00 às 10:00',self.latest());self.assertIn('11:00 às 22:00',self.latest())
        self.assertEqual(self.send(3,'16/11/2026 das 08:00 as 23:00'),'clarification_required')
        self.assertIn('15h00',self.latest());self.assertIn('240 minutos',self.latest())
        self.assertIn('08:00 às 22:00',self.latest());self.assertIn('4 hora',self.latest())
        self.send(4,'16/11/2026 as 08:00')
        self.assertIn('Já tenho o dia 16/11/2026 e o início às 08:00',self.latest())
        self.assertIn('terminar',self.latest())
        self.assertEqual(self.send(5,'Caralho que data então PORRA?'),'pilot_availability')
        self.assertIn('16/11/2026',self.latest())
        self.assertEqual(self.calendar.creates,0)
        self.assertEqual(self.send(6,'Das 11h às 13h'),'pilot_proposal')
        self.assertIn('16/11/2026 às 11:00',self.latest())
        self.assertIn('16/11/2026 às 13:00',self.latest())
        self.assertEqual(self.calendar.creates,0)
        self.assertEqual(self.send(7,'Sim, pode reservar',parent=self.last_for(1001)),'reservation_confirmed')
        self.assertEqual(self.calendar.creates,1)
        self.assertEqual(self.interpreter.interpret.call_count,0)

    def test_date_and_one_clock_ask_only_the_missing_end(self):
        self.send(1,'Quero reservar o salão dia 16/11/2026 às 08:00')
        self.assertIn('início às 08:00',self.latest())
        self.assertNotIn('Em que data',self.latest())
        self.assertEqual(self.send(2,'Até às 10h'),'pilot_proposal')
        self.assertIn('16/11/2026 às 10:00',self.latest())

    def test_both_times_can_be_given_after_a_date_only_message(self):
        self.start_date_only()
        self.assertEqual(self.send(2,'das 08:00 às 10:00'),'pilot_proposal')
        self.assertIn('16/11/2026 às 08:00',self.latest())

    def test_short_bare_clock_range_is_understood_in_reservation_context(self):
        self.start_date_only()
        self.assertEqual(self.send(2,'8 às 10'),'pilot_proposal')
        self.assertIn('16/11/2026 às 08:00',self.latest());self.assertIn('16/11/2026 às 10:00',self.latest())

    def test_spoken_clock_times_are_not_defaulted_to_midnight(self):
        self.start_date_only()
        self.assertEqual(self.send(2,'das duas às quatro da tarde'),'pilot_proposal')
        self.assertIn('16/11/2026 às 14:00',self.latest());self.assertIn('16/11/2026 às 16:00',self.latest())

    def test_invalid_end_is_not_reused_on_the_next_reply(self):
        self.start_date_only();self.send(2,'das 08h às 23h')
        self.send(3,'16/11/2026 às 08:00')
        self.assertIn('Que horas você quer terminar',self.latest())
        self.assertEqual(self.send(4,'10h'),'pilot_proposal')
        self.assertNotIn('23:00',self.latest())

    def test_conflicting_requested_interval_triggers_actual_availability_read(self):
        self.assertEqual(self.send(1,'Quero reservar o salão 16/11/2026 das 08h às 12h'),'pilot_availability')
        self.assertIn('conflito',self.latest());self.assertIn('08:00 às 10:00',self.latest())
        self.assertEqual(self.calendar.creates,0)

    def test_second_actual_transcript_keeps_date_and_recovers_from_conflict(self):
        self.assertEqual(self.send(1,'Olá quero reservar o salão de festas para dia 16 das 14 às 20'),'clarification_required')
        self.assertIn('6h00',self.latest());self.assertIn('14:00',self.latest())
        self.assertEqual(self.send(2,'16/11/2026'),'clarification_required')
        self.assertIn('14:00',self.latest());self.assertIn('terminar',self.latest())
        self.assertEqual(self.send(3,'Quais os horários disponíveis nesse dia'),'pilot_availability')
        self.assertEqual(self.send(4,'Pode ser das 8:00 às 12'),'pilot_availability')
        self.assertIn('conflito',self.latest());self.assertNotIn('revalidação',self.latest())
        self.assertEqual(self.send(5,'Puta que pariu como é que eu faço para poder reservar um horário no dia 16'),'pilot_availability')
        self.assertEqual(self.send(6,'Reserva no dia 16 das 8:00 ao meio-dia'),'pilot_availability')
        self.assertIn('conflito',self.latest());self.assertIn('11:00 às 22:00',self.latest())
        self.assertEqual(self.calendar.creates,0)
        self.assertEqual(self.send(7,'Então das 14 às 18'),'pilot_proposal')
        self.assertIn('16/11/2026 às 14:00',self.latest());self.assertIn('16/11/2026 às 18:00',self.latest())
        self.assertEqual(self.calendar.creates,0)
        self.assertEqual(self.send(8,'Sim, pode reservar',parent=self.last_for(1001)),'reservation_confirmed')
        self.assertEqual(self.calendar.creates,1)

    def test_valid_requested_rule_is_not_invalidated_by_an_alternative_after_its_expiry(self):
        result=self.handle('propose_reservation',{'resource':'salao','start':'2026-11-16T08:00:00-03:00','end':'2026-11-16T12:00:00-03:00'})
        self.assertEqual(result.code,'reservation_unavailable')
        self.assertEqual(result.data['alternatives'],[])
        self.assertEqual(self.calendar.creates,0)

    def test_spoken_midday_is_an_end_time_and_still_checks_conflicts(self):
        self.start_date_only()
        self.assertEqual(self.send(2,'Reserva no dia 16 das 8:00 ao meio-dia'),'pilot_availability')
        self.assertIn('conflito',self.latest());self.assertEqual(self.calendar.creates,0)

    def test_genuinely_expired_rule_still_blocks_a_reservation(self):
        self.raw['operations']['resources'][0]['valid_until']='2026-11-12T17:00:00-03:00'
        self.config=_parse_config(self.raw);self.bind();self.build()
        self.assertEqual(self.send(1,'Quero reservar o salão dia 16/11/2026 das 14h às 16h'),'document_rule_outdated')
        self.assertEqual(self.calendar.creates,0)

    def test_partial_day_does_not_silently_choose_a_month_when_two_dates_fit(self):
        self.raw['google']['calendar']['window_start']='2026-11-16T00:00:00-03:00'
        self.raw['google']['calendar']['window_end']='2026-12-17T00:00:00-03:00'
        self.config=_parse_config(self.raw);self.bind();self.build()
        self.assertEqual(self.send(1,'Quero reservar o salão dia 16 das 14 às 18'),'clarification_required')
        self.assertIn('mês e ano',self.latest());self.assertEqual(self.calendar.creates,0)

    def test_availability_question_survives_the_actual_year_correction(self):
        self.assertEqual(self.send(1,'Quais os horários para reserva do salão de festa para o dia 16/11/2016'),'clarification_required')
        self.assertIn('prazo permitido',self.latest());self.assertEqual(self.calendar.reads,0)
        self.assertEqual(self.send(2,'A data correta é 16/11/2026'),'pilot_availability')
        self.assertIn('08:00 às 10:00',self.latest());self.assertIn('11:00 às 22:00',self.latest())
        self.assertEqual(self.store.execute('SELECT count(*) FROM pilot_operations').fetchone()[0],0)
        self.assertEqual(self.send(3,'Das 16 as 19'),'pilot_proposal')
        self.assertEqual(self.calendar.creates,0)
        self.assertEqual(self.send(4,'Pode confirmar',parent=self.last_for(1001)),'reservation_confirmed')
        self.assertEqual(self.calendar.creates,1)

    def test_availability_goal_survives_invalid_literal_date_and_restart(self):
        self.assertEqual(self.send(1,'Quais horários disponíveis para o salão dia 30/02/2026?'),'clarification_required')
        self.reopen();self.build()
        self.assertEqual(self.send(2,'A data é 16/11/2026'),'pilot_availability')
        self.assertIn('11:00 às 22:00',self.latest());self.assertEqual(self.calendar.creates,0)

    def test_correcting_an_availability_date_does_not_need_creation_permission(self):
        self.raw['permissions']['resident'].remove('reservation.create')
        self.config=_parse_config(self.raw);self.bind();self.build()
        self.assertEqual(self.send(1,'Quais horários para reserva do salão dia 16/11/2016?'),'clarification_required')
        self.assertEqual(self.send(2,'16/11/2026'),'pilot_availability')
        self.assertIn('11:00 às 22:00',self.latest());self.assertEqual(self.calendar.creates,0)

    def test_only_date_never_becomes_an_all_day_proposal(self):
        self.start_date_only()
        self.assertEqual(self.calendar.reads,0);self.assertEqual(self.calendar.creates,0)
        self.assertEqual(self.store.execute('SELECT count(*) FROM pilot_operations').fetchone()[0],0)
        self.send(2,'Sim')
        self.assertIn('começar e terminar',self.latest());self.assertEqual(self.calendar.creates,0)

    def test_availability_without_prior_date_reads_the_calendar_without_booking(self):
        self.assertEqual(self.send(1,'Quais horários livres para o salão?'),'pilot_availability')
        self.assertGreater(self.calendar.reads,0);self.assertEqual(self.calendar.creates,0)
        self.assertIn('Consultei a Agenda',self.latest())

    def test_all_day_event_blocks_the_whole_day_in_availability(self):
        self.calendar.events={'whole-day':{'id':'whole-day','start':{'date':'2026-11-16'},'end':{'date':'2026-11-17'}}}
        self.start_date_only();self.send(2,'Qual disponibilidade?')
        self.assertIn('Não encontrei',self.latest());self.assertNotIn('08:00 às 10:00',self.latest())

    def test_incomplete_calendar_read_never_claims_free_slots(self):
        self.start_date_only()
        self.calendar.read_events=lambda *args:{'events':[],'complete':False}
        code=self.send(2,'Qual data disponível?')
        self.assertEqual(code,'calendar_read_incomplete')
        self.assertNotIn('Faixas livres encontradas',self.latest());self.assertEqual(self.calendar.creates,0)

    def test_reservation_context_survives_restart_and_collection_delay(self):
        self.start_date_only();self.clock.advance(minutes=20)
        self.reopen();self.build()
        self.assertEqual(self.send(2,'das 08h às 10h'),'pilot_proposal')
        self.assertIn('16/11/2026',self.latest())

    def test_outside_start_hour_does_not_keep_an_impossible_start(self):
        self.send(1,'Quero reservar o salão 16/11/2026 das 07h às 09h')
        self.assertIn('Qual novo intervalo',self.latest())
        self.assertEqual(self.send(2,'das 08h às 10h'),'pilot_proposal')

    def test_past_year_is_not_silently_changed(self):
        self.send(1,'Quero reservar o salão 16/11/2016 das 08h às 10h')
        self.assertIn('prazo permitido',self.latest())
        self.assertEqual(self.calendar.creates,0)

    def test_invalid_literal_date_and_clock_are_clarified(self):
        self.send(1,'Quero reservar o salão 30/02/2026 das 08h às 10h')
        self.assertIn('data está inválida',self.latest())
        self.send(2,'Quero reservar o salão 16/11/2026 das 25h às 26h')
        self.assertIn('horário válido',self.latest());self.assertEqual(self.calendar.creates,0)

    def test_another_profile_does_not_borrow_resident_reservation_context(self):
        self.start_date_only()
        self.assertEqual(self.channel.conversation.reservations.state(self.msg(self.manager)),{})
        self.assertEqual(self.send(2,'Quero reservar o salão dia 16/11/2026',2002),'unauthorized')
        self.assertEqual(self.calendar.creates,0)

    def test_transparent_and_cancelled_events_do_not_block_availability(self):
        self.calendar.events['busy-on-sixteenth']['transparency']='transparent'
        self.calendar.events['cancelled']={'id':'cancelled','status':'cancelled','start':{'date':'2026-11-16'},'end':{'date':'2026-11-17'}}
        self.start_date_only();self.send(2,'Que data disponível?')
        self.assertIn('08:00 às 22:00',self.latest())

    def test_relative_day_is_anchored_to_the_original_message_time(self):
        parsed=fragments('amanhã das oito às dez',datetime(2026,11,12,23,59,tzinfo=timezone.utc),'America/Sao_Paulo')
        self.assertEqual(parsed['dates'],['2026-11-13']);self.assertEqual(parsed['times'],['08:00','10:00'])

    def test_weekday_is_anchored_and_accepts_spoken_afternoon_times(self):
        self.assertEqual(self.send(1,'Quero reservar o salão segunda-feira das duas às quatro da tarde'),'pilot_proposal')
        self.assertIn('16/11/2026 às 14:00',self.latest())

    def test_invalid_date_does_not_forget_the_resource(self):
        self.send(1,'Quero reservar o salão 30/02/2026')
        self.send(2,'16/11/2026')
        self.assertIn('começar e terminar',self.latest())
        self.assertNotIn('Qual espaço',self.latest())
        self.assertEqual(self.send(3,'das 08h às 10h'),'pilot_proposal')

    def test_date_outside_pilot_window_is_explained_before_asking_for_hours(self):
        self.send(1,'Quero reservar o salão dia 18/11/2026')
        self.assertIn('prazo permitido',self.latest());self.assertIn('17/11/2026',self.latest())
        self.assertEqual(self.calendar.reads,0);self.assertEqual(self.calendar.creates,0)

    def test_closed_pilot_window_is_not_reported_as_an_occupied_calendar(self):
        self.clock.now=datetime(2026,11,17,5,0,tzinfo=timezone.utc)
        self.assertEqual(self.send(1,'Quais datas disponíveis para o salão?'),'reservation_window_closed')
        self.assertIn('janela autorizada',self.latest());self.assertEqual(self.calendar.reads,0)

    def test_alternative_event_purpose_does_not_make_an_explicit_date_ambiguous(self):
        self.send(1,'Quero reservar o salão para reunião ou encontro dia 16/11/2026')
        self.assertIn('16/11/2026',self.latest());self.assertIn('começar e terminar',self.latest())

    def test_alternative_clock_choices_are_not_turned_into_a_reservation_interval(self):
        self.start_date_only()
        self.assertEqual(self.send(2,'08h ou 10h'),'clarification_required')
        self.assertEqual(self.store.execute('SELECT count(*) FROM pilot_operations').fetchone()[0],0)
