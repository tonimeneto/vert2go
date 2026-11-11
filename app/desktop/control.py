"""One supervised bot thread; status follows the canonical Telegram lifecycle."""
from pathlib import Path
from queue import Empty, Queue
import re
from threading import Event, Thread

from app.core.contracts import EngineError
from app.main import instance_lock


def database_busy(path):
    try:
        with instance_lock(path):
            return False
    except EngineError as error:
        if error.code == 'instance_already_running':
            return True
        raise


def run_bot(arguments, **kwargs):
    from app.main import main
    return main(arguments,**kwargs)


class BotControl:
    def __init__(self, root, *, runner=run_bot, probe=database_busy):
        self.root = Path(root).resolve()
        self.database = self.root/'data/i2.sqlite3'
        self.runner, self.probe = runner, probe
        self.state, self.code = 'inactive', None
        self.thread = None
        self.stop_event = Event()
        self.events = Queue()
        self.exit_code = None

    def _observe(self, state, code=None):
        # Only status and fixed codes cross into the UI, never provider payloads or secrets.
        safe_code = code if type(code) is str and re.fullmatch(r'[a-z][a-z0-9_]{0,79}',code) else None
        self.events.put((state,safe_code))

    def _run(self):
        arguments = ['--config',str(self.root/'config.yaml'),'--database',str(self.database),
                     '--secrets',str(self.root/'secrets.yaml'),'--telegram','--allow-live-telegram',
                     '--knowledge','--allow-live-openai']
        try:
            result = self.runner(arguments,stop_event=self.stop_event,lifecycle_observer=self._observe)
        except BaseException:
            self._observe('failed','bot_control_error')
            result = 1
        self.events.put(('finished',result))

    def start(self):
        self.poll()
        if self.thread is not None or self.state in ('external','unknown'):
            return False
        self.stop_event = Event()
        self.state, self.code, self.exit_code = 'starting', None, None
        self.thread = Thread(target=self._run,name='Alfredo',daemon=False)
        try:
            self.thread.start()
        except RuntimeError:
            self.thread = None
            self.state, self.code = 'failed','bot_control_error'
            return False
        return True

    def stop(self):
        if self.thread is None:
            return False
        self.state = 'stopping'
        self.stop_event.set()
        return True

    def poll(self):
        while True:
            try:
                state, value = self.events.get_nowait()
            except Empty:
                break
            if state == 'finished':
                self.exit_code = value
            elif state == 'failed':
                self.code = value or 'bot_control_error'
                if self.state != 'stopping':
                    self.state = 'failed'
            elif self.state != 'stopping' and state in ('starting','ready','unavailable'):
                self.state = {'starting':'starting','ready':'active','unavailable':'unavailable'}[state]
                if state == 'unavailable':
                    self.code = value
        if self.thread is not None and not self.thread.is_alive():
            self.thread.join()
            self.thread = None
            self.state = 'inactive' if self.exit_code in (0,130) else 'failed'
            if self.state == 'failed' and self.code is None:
                self.code = 'bot_control_error'
        if self.thread is None:
            try:
                busy = self.probe(self.database)
            except (EngineError,OSError):
                self.state, self.code = 'unknown','control_status_unavailable'
            else:
                if busy:
                    self.state = 'external'
                elif self.state in ('external','unknown'):
                    self.state, self.code = 'inactive', None
        return self.state
