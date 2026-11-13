import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from scripts.telegram_i5_tests import run,request_stop,state_path


class I5TelegramSupervisorTests(unittest.TestCase):
    def test_finite_session_uses_explicit_i5_flags_and_closes_without_network(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); observed=[]
            def runner(arguments,*,stop_event,lifecycle_observer):
                observed.extend(arguments); lifecycle_observer('ready'); return 0
            with patch('scripts.telegram_i5_tests.private_acl'):
                self.assertEqual(run(root,seconds=60,runner=runner),0)
            self.assertIn('--operations',observed); self.assertIn('--allow-live-google-writes',observed)
            self.assertEqual(json.loads(state_path(root).read_text())['state'],'closed')
            self.assertEqual(request_stop(root),0)
