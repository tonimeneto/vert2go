"""Manual startup: finite local check by default; explicitly gated Telegram polling."""
import argparse
from contextlib import contextmanager
import logging
from pathlib import Path
import os
import sqlite3
from app.config.schema import load_config, load_telegram_token
from app.core.contracts import EngineError
from app.core.orchestrator import Orchestrator
from app.storage.sqlite import Store


@contextmanager
def instance_lock(database_path):
    """OS-held byte lock; released by OS on crash. Never infer ownership from PID."""
    lock_path = Path(str(Path(database_path).resolve())+'.lock')
    lock_path.parent.mkdir(parents=True,exist_ok=True)
    handle = lock_path.open('a+b')
    locked = False
    try:
        if os.name == 'nt':
            import msvcrt
            if lock_path.stat().st_size == 0:
                handle.write(b'0')
                handle.flush()
            handle.seek(0)
            try:
                msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
            except OSError:
                raise EngineError('instance_already_running') from None
        else:
            import fcntl
            try:
                fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except OSError:
                raise EngineError('instance_already_running') from None
        locked = True
        yield
    finally:
        if locked:
            if os.name == 'nt':
                import msvcrt
                handle.seek(0)
                msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
            else:
                import fcntl
                fcntl.flock(handle,fcntl.LOCK_UN)
        handle.close()


def main(argv=None, *, stop_event=None, lifecycle_observer=None):
    parser = argparse.ArgumentParser(description='Alfredo — inicialização local e canal Telegram I2')
    parser.add_argument('--config',default='config.yaml')
    parser.add_argument('--database',default='data/i1.sqlite3')
    parser.add_argument('--telegram', action='store_true', help='Iniciar long polling manual')
    parser.add_argument('--allow-live-telegram', action='store_true', help='Atestar autorização separada de uso real do bot')
    parser.add_argument('--secrets', default='secrets.yaml')
    parser.add_argument('--knowledge', action='store_true', help='Habilitar consultas documentais I4 no Telegram')
    parser.add_argument('--allow-live-openai', action='store_true', help='Atestar G3 e uso OpenAI autorizado')
    parser.add_argument('--i2-replay-evidence', action='store_true',
                        help='Verificar uma mensagem real em copias SQLite em memoria, sem reenvio real')
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO,format='%(levelname)s %(message)s')
    def notify(state, code=None):
        if lifecycle_observer is not None:
            lifecycle_observer(state,code)
    logging.info('process_started pid=%d mode=%s', os.getpid(), 'telegram' if args.telegram else 'local')
    try:
        notify('starting')
        if stop_event is not None and stop_event.is_set():
            return 0
        config = load_config(args.config)
        if args.telegram and (not args.allow_live_telegram or not config.telegram):
            raise EngineError('live_telegram_authorization_required')
        if args.allow_live_telegram and not args.telegram:
            raise EngineError('telegram_mode_required')
        if args.i2_replay_evidence and not args.telegram:
            raise EngineError('telegram_mode_required')
        if args.knowledge:
            if not args.telegram or not args.allow_live_openai:
                raise EngineError('live_openai_authorization_required')
            if config.knowledge is None:
                raise EngineError('knowledge_not_configured')
            config.knowledge.require_consent(telegram=True)
            from app.ai.configuration import load_api_key
            load_api_key(args.secrets)
        elif args.allow_live_openai:
            raise EngineError('knowledge_mode_required')
        token = load_telegram_token(args.secrets, config.telegram['bot_id']) if args.telegram else None
        with instance_lock(args.database):
            logging.info('instance_lock_acquired')
            if args.knowledge:
                from app.storage.backup import before_knowledge_migration
                before_knowledge_migration(args.database,args.config)
            store = Store(args.database,knowledge=args.knowledge)
            try:
                status = Orchestrator(config,store).startup()
                logging.info('local_ready schema=%d simulation=true recovered=%d expired=%d',
                             store.execute('PRAGMA user_version').fetchone()[0],status['recovered'],status['expired'])
                if args.telegram:
                    from app.channels.telegram import TelegramAPI, TelegramChannel
                    observer = None
                    if args.i2_replay_evidence:
                        from app.channels.telegram_replay_probe import ReceiptReplayProbe
                        observer = ReceiptReplayProbe(Path(__file__).resolve().parents[1]/
                                                      'docs/evidencias/i2-real-replay.json')
                    from contextlib import nullcontext
                    from app.ai.runtime import knowledge_runtime
                    runtime = (knowledge_runtime(config,store,args.secrets,allow_live=True,telegram=True)
                               if args.knowledge else nullcontext(None))
                    with runtime as knowledge:
                        channel = TelegramChannel(config, store, Orchestrator(config, store,knowledge=knowledge),
                                                  TelegramAPI(token, config.telegram['request_seconds']),
                                                  receipt_observer=observer)
                        if stop_event is not None:
                            channel.stop = stop_event
                        channel.lifecycle_observer = lifecycle_observer
                        try:
                            channel.run()
                        finally:
                            channel.stop.set()
                            logging.info('telegram_closed')
            finally:
                store.close()
        logging.info('local_closed')
        return 0
    except EngineError as error:
        notify('failed',error.code)
        logging.error('startup_rejected code=%s',error.code)
        return 1
    except (OSError,sqlite3.Error,ValueError,TypeError):
        notify('failed','local_initialization_error')
        logging.error('startup_rejected code=local_initialization_error')
        return 1
    except KeyboardInterrupt:
        logging.info('local_interrupted')
        return 130


if __name__ == '__main__':
    raise SystemExit(main())
