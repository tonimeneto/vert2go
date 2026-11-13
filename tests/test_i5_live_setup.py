from copy import deepcopy
from datetime import datetime, timezone
import unittest
from scripts.setup_operations_i5 import candidate
from app.config.schema import _parse_config
from app.core.contracts import EngineError
from tests.test_operations import configuration
from unittest.mock import patch
from app.integrations.google_auth import GoogleAuth


class I5LiveSetupTests(unittest.TestCase):
    def test_candidate_preserves_existing_configuration_and_uses_existing_destinations(self):
        raw = configuration(telegram=True); del raw['operations']
        before = deepcopy(raw)
        new = candidate(raw,{'1001':'101A'},datetime(2026,11,12,tzinfo=timezone.utc))
        self.assertEqual(raw,before)
        for key in raw:
            if key != 'permissions': self.assertEqual(new[key],raw[key])
        c = _parse_config(new)
        self.assertEqual(c.operations.calendar_id,c.google.calendar_id)
        self.assertEqual(c.operations.sheet_range,c.google.ranges[0])
        self.assertTrue(c.google.write_access)
        self.assertEqual(c.operations.resources['salao']['status'],'simulated')
        self.assertEqual(c.operations.units['1001'],'101A')

    def test_existing_i5_configuration_is_not_silently_replaced(self):
        with self.assertRaisesRegex(EngineError,'operations_already_configured'):
            candidate(configuration(telegram=True),{'1001':'101A'},datetime(2026,11,12,tzinfo=timezone.utc))

    def test_invalid_consent_wait_rejected_before_private_io(self):
        config=_parse_config(configuration(telegram=True))
        auth=GoogleAuth(config.google,'not-read.yaml',allow_live=True)
        with patch('app.integrations.google_auth.import_desktop_client') as read:
            for value in (True,0,29,1801,'600'):
                with self.assertRaisesRegex(EngineError,'google_consent_timeout_invalid'):
                    auth.enroll('not-read.json',consent_timeout_seconds=value)
        read.assert_not_called()
