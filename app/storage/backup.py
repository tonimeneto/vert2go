"""Private SQLite snapshot before opting an existing operational database into I4."""
from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3
from uuid import uuid4
from app.core.contracts import EngineError
from app.integrations.private_files import no_links, private_acl
from app.storage.sqlite import APPLICATION_ID


def before_knowledge_migration(database, acl_reference):
    return before_migration(database,acl_reference,3,'i4')


def before_operations_migration(database, acl_reference):
    return before_migration(database,acl_reference,5,'i5')


def before_migration(database, acl_reference, target_version, phase):
    """Caller holds instance_lock. Snapshot before writes; private ACL before database bytes."""
    path = no_links(database)
    if not path.exists():
        return None
    source = sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)
    destination = None
    try:
        if source.execute('PRAGMA application_id').fetchone()[0] != APPLICATION_ID:
            raise EngineError('unrecognized_database')
        version = source.execute('PRAGMA user_version').fetchone()[0]
        if version not in (1,2,3,4,5):
            raise EngineError('unrecognized_database')
        if version >= target_version:
            return None
        if source.execute('PRAGMA user_version').fetchone()[0] not in (1,2,3,4):
            raise EngineError('unrecognized_database')
        private_acl(acl_reference)
        folder = path.parent/'backups'
        no_links(folder)
        folder.mkdir(exist_ok=True)
        target = folder/('before-'+phase+'-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid4().hex+'.sqlite3')
        fd = os.open(target,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        os.close(fd)
        private_acl(acl_reference,target)
        destination = sqlite3.connect(target)
        source.backup(destination)
        if destination.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise EngineError('knowledge_backup_failed')
        destination.close(); destination = None
        private_acl(target)
        return target
    except EngineError:
        raise
    except (OSError,sqlite3.Error):
        raise EngineError('knowledge_backup_failed') from None
    finally:
        if destination is not None:
            destination.close()
        source.close()
