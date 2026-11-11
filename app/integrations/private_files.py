"""Private, serialized compare-and-swap writes. No secret is passed to a shell."""
from contextlib import contextmanager
import os
from pathlib import Path
import subprocess
import uuid
import yaml
from app.config.schema import read_configuration_bytes, StrictLoader
from app.core.contracts import EngineError

# Paths travel through environment variables, never interpolated as PowerShell code.
# Empty temporary files receive the source's protected ACL BEFORE any private bytes.
ACL_SCRIPT = r"""
$ErrorActionPreference='Stop'
$src=Get-Acl -LiteralPath $env:ALFREDO_ACL_SOURCE
if (-not $src.AreAccessRulesProtected) { throw 'unsafe' }
foreach ($rule in $src.Access) {
  $sid=$rule.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value
  if ($rule.AccessControlType -eq 'Allow' -and
      ($sid -in @('S-1-1-0','S-1-5-11','S-1-5-32-545','S-1-5-32-544') -or
       $rule.IdentityReference.Value -match '\\CodexSandboxUsers$')) { throw 'unsafe' }
}
if ($env:ALFREDO_ACL_TARGET) {
  $section=[System.Security.AccessControl.AccessControlSections]::Access
  $access=$src.GetSecurityDescriptorSddlForm($section)
  $existing=Get-Acl -LiteralPath $env:ALFREDO_ACL_TARGET
  if ($existing.GetSecurityDescriptorSddlForm($section) -eq $access) { exit 0 }
  $target=New-Object System.Security.AccessControl.FileSecurity
  $target.SetSecurityDescriptorSddlForm($access,$section)
  Set-Acl -LiteralPath $env:ALFREDO_ACL_TARGET -AclObject $target
  $dst=Get-Acl -LiteralPath $env:ALFREDO_ACL_TARGET
  if ($access -ne $dst.GetSecurityDescriptorSddlForm($section)) { throw 'mismatch' }
}
"""


def no_links(path):
    path = Path(path).absolute()
    for part in (path, *path.parents):
        if part.is_symlink() or (part.exists() and getattr(part.stat(), 'st_file_attributes', 0) & 0x400):
            raise EngineError('private_path_unsafe')
    return path


def private_acl(source, target=None):
    source = no_links(source)
    if target is not None:
        target = no_links(target)
    if os.name == 'nt':
        env = os.environ.copy()
        env['ALFREDO_ACL_SOURCE'] = str(source)
        env['ALFREDO_ACL_TARGET'] = str(target) if target is not None else ''
        try:
            result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', ACL_SCRIPT],
                                    env=env, capture_output=True, timeout=15,
                                    creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode:
                raise EngineError('private_acl_unsafe')
        except (OSError, subprocess.SubprocessError):
            raise EngineError('private_acl_unavailable') from None
    else:
        if source.stat().st_mode & 0o077:
            raise EngineError('private_acl_unsafe')
        if target is not None:
            os.chmod(target, 0o600)


@contextmanager
def private_lock(path):
    path = no_links(path)
    private_acl(path)
    lock = path.with_name(path.name+'.lock')
    no_links(lock)
    fd = os.open(lock, os.O_CREAT | os.O_RDWR, 0o600)
    with os.fdopen(fd, 'r+b') as handle:
        private_acl(path, lock)
        locked = False
        try:
            if lock.stat().st_size == 0:
                handle.write(b'0')
                handle.flush()
            handle.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            locked = True
            yield
        except OSError:
            raise EngineError('private_write_unavailable') from None
        finally:
            if locked:
                handle.seek(0)
                if os.name == 'nt':
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def atomic_yaml(path, expected_bytes, raw, validator):
    """Caller holds private_lock. Only publish a fully validated complete document."""
    path = no_links(path)
    validator(raw)
    data = yaml.safe_dump(raw, allow_unicode=True, sort_keys=False).encode('utf-8')
    if len(data) > 65536:
        raise EngineError('invalid_yaml_size')
    if read_configuration_bytes(path) != expected_bytes:
        raise EngineError('configuration_changed_during_enrollment')
    temp = path.with_name('.'+path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as handle:
            private_acl(path, temp)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        validator(yaml.load(temp.read_text(encoding='utf-8'), Loader=StrictLoader))
        if read_configuration_bytes(path) != expected_bytes:
            raise EngineError('configuration_changed_during_enrollment')
        os.replace(temp, path)
        private_acl(path)
        return data
    except OSError:
        raise EngineError('private_write_unavailable') from None
    finally:
        if temp.exists():
            temp.unlink()
