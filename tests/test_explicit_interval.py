import unittest
from app.channels.explicit_interval import explicit_interval
from app.core.contracts import EngineError


class ExplicitIntervalTests(unittest.TestCase):
    def parse(self,text):
        return explicit_interval(text,'America/Sao_Paulo')

    def test_fully_stated_range_accepts_clock_variants_without_a_model(self):
        for start,end in [('16h','18h'),('16:15','18:45'),('16h15','18h45'),('16 horas','18 horas')]:
            with self.subTest(start=start):
                result=self.parse(f'Vigência de 12/11/2026 às {start} até 12/11/2026 às {end}, horário de Brasília.')
                self.assertTrue(result[0].startswith('2026-11-12T16:'))
                self.assertTrue(result[1].startswith('2026-11-12T18:'))

    def test_explicit_past_year_is_preserved_instead_of_repaired(self):
        result=self.parse('De 12/11/2026 às 16h até 12/11/2016 às 18h, horário de Brasília.')
        self.assertTrue(result[1].startswith('2016-11-12T18:00:00'))

    def test_missing_date_or_year_is_not_inferred(self):
        for value in ['De 12/11 às 16h até 12/11 às 18h', 'De 12/11/2026 às 16h até às 18h']:
            self.assertIsNone(self.parse(value+', horário de Brasília.'))

    def test_multiple_explicit_ranges_are_not_selected_automatically(self):
        self.assertIsNone(self.parse('De 12/11/2026 às 16h até 12/11/2026 às 18h; antes era 11/11/2026. Horário de Brasília.'))

    def test_alternatives_and_conflicting_timezones_are_not_resolved_automatically(self):
        for suffix in [' ou amanhã, horário de Brasília.', ', horário de Brasília ou UTC.']:
            self.assertIsNone(self.parse('De 12/11/2026 às 16h até 12/11/2026 às 18h'+suffix))

    def test_invalid_literal_day_and_clock_are_never_normalized_forward(self):
        for day,hour in [('30/02/2026','16h'),('12/11/2026','25h'),('12/11/2026','16h99')]:
            with self.assertRaisesRegex(EngineError,'invalid_datetime'):
                self.parse(f'De {day} às {hour} até 12/11/2026 às 18h, horário de Brasília.')

    def test_content_before_the_range_does_not_make_explicit_dates_ambiguous(self):
        self.assertIsNotNone(self.parse('Aviso: vistoria ou limpeza fictícia. Vigência de 12/11/2026 às 16h até 12/11/2026 às 18h, horário de Brasília.'))

    def test_timezone_must_be_stated_for_this_narrow_parser(self):
        self.assertIsNone(self.parse('De 12/11/2026 às 16h até 12/11/2026 às 18h.'))
