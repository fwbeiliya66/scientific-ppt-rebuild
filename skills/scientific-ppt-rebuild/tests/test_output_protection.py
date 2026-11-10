import sys
import tempfile
import unittest
from pathlib import Path
SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / 'runtime'))
from finalize_deck_run import assert_output_safe
from deck_run_state import sha256_file


class ProtectionTests(unittest.TestCase):
    def test_new_file_allowed_but_unowned_existing_file_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            out = run / 'final.pptx'
            assert_output_safe(run, {}, out)
            out.write_bytes(b'user changes')
            with self.assertRaises(SystemExit):
                assert_output_safe(run, {}, out)

    def test_own_unchanged_output_can_rebuild_but_user_modified_cannot(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp); out = run / 'final.pptx'
            out.write_bytes(b'built file')
            deck = {'last_built_sha256': sha256_file(out)}
            assert_output_safe(run, deck, out)
            out.write_bytes(b'edited by user')
            with self.assertRaises(SystemExit):
                assert_output_safe(run, deck, out)

    def test_source_cannot_be_output_even_with_matching_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp); (run / 'input').mkdir()
            source = run / 'input/source.pptx'; source.write_bytes(b'original')
            with self.assertRaises(SystemExit):
                assert_output_safe(run, {'inputs': ['input/source.pptx'], 'last_built_sha256': sha256_file(source)}, source)


if __name__ == '__main__':
    unittest.main()
