"""Regression checks against the retained, completed synthetic run."""
import importlib.util
import json
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('evidence_checker', ROOT/'scripts/check-evidence.py')
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)

class EvidenceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = pathlib.Path(temporary.name)
        self.report = json.loads((ROOT/'evidence/live-api.json').read_text())
        (self.directory/'daml-test.txt').write_bytes((ROOT/'evidence/daml-test.txt').read_bytes())

    def validate(self):
        (self.directory/'live-api.json').write_text(json.dumps(self.report))
        return checker.validate(self.directory, self.directory/'absent-auth.conf')

    def test_complete_evidence(self):
        self.assertIn('SKIPPED', self.validate())

    def test_duplicate_http_check_cannot_replace_missing_check(self):
        self.report['checks'][0] = self.report['checks'][1]
        with self.assertRaisesRegex(ValueError, 'Duplicate labels in checks'):
            self.validate()

    def test_duplicate_assertion_cannot_replace_missing_assertion(self):
        self.report['assertions'][0] = self.report['assertions'][1]
        with self.assertRaisesRegex(ValueError, 'Duplicate labels in assertions'):
            self.validate()

    def test_missing_party_cannot_skip_rights_validation(self):
        self.report['parties'].pop('outsider')
        with self.assertRaisesRegex(ValueError, 'party roles'):
            self.validate()

    def test_incomplete_run_rejected(self):
        self.report.pop('completedUtc')
        with self.assertRaisesRegex(ValueError, 'Incomplete'):
            self.validate()

    def test_corrupt_assertion_rejected(self):
        self.report['assertions'][0]['actual'] = 'corrupted'
        with self.assertRaisesRegex(ValueError, 'Failed assertion'):
            self.validate()

if __name__ == '__main__':
    unittest.main()
