import unittest
from unittest.mock import MagicMock
from app.core.contracts import EngineError
from scripts.validate_operations_i5 import FaultCalendar,FaultSheets,SimulatedInterruption


class I5FaultProofTests(unittest.TestCase):
    def test_calendar_injection_happens_only_after_one_actual_adapter_call(self):
        actual=MagicMock(); adapter=FaultCalendar(actual)
        with self.assertRaisesRegex(EngineError,'injected_timeout_after_real_calendar_write'):
            adapter.create_event('calendar',{'id':'fictitious'})
        actual.create_event.assert_called_once_with('calendar',{'id':'fictitious'})
        self.assertEqual(adapter.creates,1)
        adapter=FaultCalendar(actual,crash=True)
        with self.assertRaises(SimulatedInterruption): adapter.create_event('calendar',{})

    def test_sheets_prewrite_failure_never_calls_mutation_and_postwrite_is_once(self):
        actual=MagicMock(); adapter=FaultSheets(actual)
        with self.assertRaises(EngineError): adapter.read_range('spreadsheet','range')
        actual.write_row.assert_not_called()
        adapter=FaultSheets(actual,after_write=True)
        with self.assertRaisesRegex(EngineError,'injected_timeout_after_real_sheets_write'):
            adapter.write_row('spreadsheet','range',['fictitious'])
        actual.write_row.assert_called_once_with('spreadsheet','range',['fictitious'])
