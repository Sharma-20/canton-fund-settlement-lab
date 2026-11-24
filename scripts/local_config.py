"""Configuration guard for the synthetic loopback lab, not production IAM."""
import os
import pathlib
import re
import secrets
import stat

TEMPLATE = '''canton.participants.sandbox {
  ledger-api {
    address = "127.0.0.1"
    auth-services = [{ type = unsafe-jwt-hmac-256, secret = "SECRET" }]
  }
  admin-api.address = "127.0.0.1"
  http-ledger-api.address = "127.0.0.1"
}
canton.sequencers.sequencer1 {
  public-api.address = "127.0.0.1"
  admin-api.address = "127.0.0.1"
}
canton.mediators.mediator1.admin-api.address = "127.0.0.1"
'''

def require_private(path, directory=False):
    mode = path.lstat()
    correct_type = stat.S_ISDIR(mode.st_mode) if directory else stat.S_ISREG(mode.st_mode)
    if not correct_type or mode.st_uid != os.getuid() or mode.st_mode & 0o077:
        raise ValueError('Lab configuration must be an owner-only regular file/directory; symlinks are refused.')

def prepare(root):
    runtime = pathlib.Path(root)/'.runtime'
    if not runtime.exists() and not runtime.is_symlink():
        runtime.mkdir(mode=0o700)
    require_private(runtime, directory=True)
    target = runtime/'auth.conf'
    if not target.exists() and not target.is_symlink():
        content = TEMPLATE.replace('SECRET', secrets.token_hex(32))
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as handle:
            handle.write(content)
    require_private(target)
    content = target.read_text()
    match = re.search(r'secret = "([0-9a-f]{64})"', content)
    if match is None or content != TEMPLATE.replace('SECRET', match[1]):
        raise ValueError('Existing configuration is not the approved loopback-only lab template; refusing startup without changing it.')
