from pathlib import Path
import tempfile
from threading import Event
import time
import unittest
from types import SimpleNamespace
import json

from app.core.contracts import EngineError
from app.desktop.control import BotControl, database_busy
from app.main import instance_lock, main


class DesktopControlTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='vert2go-control-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.release = Event()
        self.addCleanup(self.release.set)
        self.ready = Event()
        self.controls = []
        self.addCleanup(self.finish_workers)

    def finish_workers(self):
        self.release.set()
        for control in self.controls:
            control.stop()
            if control.thread is not None:
                control.thread.join(3)
                self.assertFalse(control.thread.is_alive())

    def control(self, runner=None, probe=lambda _:False, config_loader=lambda _:SimpleNamespace(operations=None)):
        if runner is None:
            def runner(arguments, *, stop_event, lifecycle_observer):
                lifecycle_observer('ready')
                self.ready.set()
                stop_event.wait(3)
                return 0
        control = BotControl(self.root,runner=runner,probe=probe,config_loader=config_loader)
        self.controls.append(control)
        return control

    def pump(self, control, wanted):
        deadline = time.monotonic()+3
        while time.monotonic()<deadline:
            if control.poll()==wanted:
                return
            Event().wait(.01)
        self.fail('Control did not reach '+wanted)

    def test_database_probe_observes_real_os_lock_without_opening_database(self):
        path = self.root/'bot.sqlite3'
        self.assertFalse(database_busy(path))
        with instance_lock(path):
            self.assertTrue(database_busy(path))
        self.assertFalse(database_busy(path))
        self.assertFalse(path.exists())

    def test_running_thread_is_not_active_before_telegram_ready(self):
        def runner(arguments, *, stop_event, lifecycle_observer):
            self.ready.set()
            self.release.wait(3)
            lifecycle_observer('ready')
            stop_event.wait(3)
            return 0
        control = self.control(runner)
        self.assertTrue(control.start())
        self.assertTrue(self.ready.wait(2))
        self.assertEqual(control.poll(),'starting')
        self.release.set()
        self.pump(control,'active')

    def test_duplicate_start_is_blocked_and_arguments_use_only_canonical_I4(self):
        seen=[]
        def runner(arguments, *, stop_event, lifecycle_observer):
            seen.append(arguments);lifecycle_observer('ready');self.ready.set();stop_event.wait(3)
            return 0
        control=self.control(runner);control.start();self.assertTrue(self.ready.wait(2));self.pump(control,'active')
        self.assertFalse(control.start());self.assertEqual(len(seen),1)
        self.assertEqual(seen[0],['--config',str(self.root/'config.yaml'),'--database',str(self.root/'data/i2.sqlite3'),
            '--secrets',str(self.root/'secrets.yaml'),'--telegram','--allow-live-telegram','--knowledge','--allow-live-openai'])

    def test_stop_waits_for_inflight_operation_and_late_ready_cannot_reactivate(self):
        observed=Event()
        def runner(arguments, *, stop_event, lifecycle_observer):
            lifecycle_observer('ready');self.ready.set();stop_event.wait(3)
            lifecycle_observer('ready');observed.set();self.release.wait(3)
            return 0
        control=self.control(runner);control.start();self.assertTrue(self.ready.wait(2));self.pump(control,'active')
        self.assertTrue(control.stop());self.assertTrue(observed.wait(2))
        self.assertEqual(control.poll(),'stopping');self.assertIsNotNone(control.thread)
        self.assertFalse(control.start());self.release.set();self.pump(control,'inactive')

    def test_disconnect_and_recovery_follow_real_lifecycle_notifications(self):
        control=self.control();control.start();self.assertTrue(self.ready.wait(2));self.pump(control,'active')
        control._observe('unavailable','telegram_transport_error');self.assertEqual(control.poll(),'unavailable')
        control._observe('ready');self.assertEqual(control.poll(),'active')

    def test_failure_preserves_fixed_code_without_raw_exception_text(self):
        def runner(*args,**kwargs):raise RuntimeError('PRIVATE_SENTINEL_MUST_NOT_REACH_UI')
        control=self.control(runner);control.start();self.pump(control,'failed')
        self.assertEqual(control.code,'bot_control_error')
        self.assertNotIn('PRIVATE_SENTINEL',str(vars(control)))

    def test_startup_rejection_is_red_failure_not_active(self):
        def runner(arguments, *, stop_event, lifecycle_observer):
            lifecycle_observer('failed','configuration_read_denied')
            return 1
        control=self.control(runner);control.start();self.pump(control,'failed')
        self.assertEqual(control.code,'configuration_read_denied')

    def test_external_instance_is_never_stopped_or_reported_as_controlled(self):
        control=self.control(probe=lambda _:True)
        self.assertEqual(control.poll(),'external');self.assertFalse(control.start());self.assertFalse(control.stop())
        self.assertIsNone(control.thread)

    def test_unreadable_lock_is_unknown_instead_of_false_inactive(self):
        def probe(_):raise OSError('private path details')
        control=self.control(probe=probe)
        self.assertEqual(control.poll(),'unknown');self.assertFalse(control.start())
        self.assertEqual(control.code,'control_status_unavailable')

    def test_restart_gets_a_fresh_stop_event(self):
        control=self.control();control.start();self.assertTrue(self.ready.wait(2));self.pump(control,'active')
        old=control.stop_event;control.stop();self.pump(control,'inactive');self.ready.clear()
        self.assertTrue(control.start());self.assertTrue(self.ready.wait(2));self.pump(control,'active')
        self.assertIsNot(control.stop_event,old);self.assertFalse(control.stop_event.is_set())

    def test_stop_before_main_start_does_not_read_config_or_secrets(self):
        stop=Event();stop.set();states=[]
        result=main(['--config',str(self.root/'absent.yaml')],stop_event=stop,
                    lifecycle_observer=lambda state,code:states.append((state,code)))
        self.assertEqual(result,0);self.assertEqual(states,[('starting',None)])
        self.assertEqual(list(self.root.iterdir()),[])

    def test_preconfigured_authorized_operations_are_used_by_same_panel(self):
        seen=[]
        def runner(arguments, *, stop_event, lifecycle_observer):
            seen.extend(arguments);lifecycle_observer('ready');self.ready.set();stop_event.wait(3);return 0
        loader=lambda _:SimpleNamespace(operations=SimpleNamespace(live_authorized=True))
        control=self.control(runner,config_loader=loader);control.start();self.assertTrue(self.ready.wait(2))
        self.assertIn('--operations',seen);self.assertIn('--allow-live-google-writes',seen)

    def test_draft_operations_do_not_grant_live_writes(self):
        seen=[]
        def runner(arguments, **kwargs):seen.extend(arguments);self.ready.set();return 0
        control=self.control(runner,config_loader=lambda _:SimpleNamespace(operations=SimpleNamespace(live_authorized=False)))
        control.start();self.assertTrue(self.ready.wait(2));self.assertNotIn('--operations',seen)

    def test_config_error_preserves_specific_safe_code(self):
        def loader(_):raise EngineError('configuration_read_denied')
        control=self.control(config_loader=loader);control.start();self.pump(control,'failed')
        self.assertEqual(control.code,'configuration_read_denied')

    def test_safe_status_tracks_real_readiness_and_reconnection_without_private_data(self):
        control=self.control();control.start();self.assertTrue(self.ready.wait(2));self.pump(control,'active')
        status=json.loads((self.root/'data/alfredo-control-status.json').read_text())
        self.assertEqual(status['state'],'active');self.assertEqual(status['ready_count'],1)
        control._observe('unavailable','telegram_transport_error');control.poll()
        status=json.loads((self.root/'data/alfredo-control-status.json').read_text())
        self.assertEqual(status['state'],'unavailable');self.assertEqual(status['connection_failures'],1)
        self.assertNotIn('token',status)

    def test_manual_launcher_start_flag_preserves_canonical_panel_entry(self):
        from scripts.alfredo_control import main
        from unittest.mock import patch
        with patch('scripts.alfredo_control.panel_main',return_value=0) as run:
            self.assertEqual(main(['--start']),0);run.assert_called_once_with(start=True)
