import pathlib
import sys
import tempfile
import unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from local_config import prepare

class LocalConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=pathlib.Path(self.tmp.name)
    def config(self):
        prepare(self.root)
        return self.root/'.runtime/auth.conf'
    def test_create_private_config(self):
        p=self.config()
        self.assertEqual(p.stat().st_mode & 0o777,0o600)
        self.assertEqual(p.parent.stat().st_mode & 0o777,0o700)
    def test_reuse_keeps_key(self):
        p=self.config();old=p.read_bytes();prepare(self.root)
        self.assertEqual(p.read_bytes(),old)
    def test_public_binding_refused_without_overwrite(self):
        p=self.config();p.write_text(p.read_text().replace('127.0.0.1','0.0.0.0'))
        old=p.read_bytes()
        with self.assertRaises(ValueError): prepare(self.root)
        self.assertEqual(p.read_bytes(),old)
    def test_extra_auth_override_refused(self):
        p=self.config();p.write_text(p.read_text()+'\ncanton.participants.sandbox.ledger-api.auth-services = []\n')
        with self.assertRaises(ValueError): prepare(self.root)
    def test_world_readable_key_refused(self):
        p=self.config();p.chmod(0o644)
        with self.assertRaises(ValueError): prepare(self.root)
    def test_world_readable_runtime_refused(self):
        p=self.config();p.parent.chmod(0o755)
        with self.assertRaises(ValueError): prepare(self.root)
    def test_config_symlink_refused(self):
        p=self.config();saved=p.with_name('saved.conf');p.rename(saved);p.symlink_to(saved)
        with self.assertRaises(ValueError): prepare(self.root)
    def test_runtime_symlink_refused(self):
        d=self.root/'elsewhere';d.mkdir(mode=0o700);(self.root/'.runtime').symlink_to(d)
        with self.assertRaises(ValueError): prepare(self.root)

if __name__=='__main__': unittest.main()
