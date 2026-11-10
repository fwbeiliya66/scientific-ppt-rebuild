import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image
from pptx import Presentation

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / 'runtime'))
from build_pptx_from_manifest import write_deck, write_pptx
from deck_run_state import write_json


class RuntimeRegressionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.page = self.root / 'pages/page_001'
        self.page.mkdir(parents=True)
        self.manifest = {
            'source': {'width_px': 1600, 'height_px': 900},
            'slide': {'width': 13.333333333333334, 'height': 7.5},
            'notes': '', 'text_boxes': [], 'shapes': [], 'images': [],
            'visual_inventory': [], 'background_strategy': {'mode': 'native'},
            'quality_checks': {
                'font_size_calibrated': True, 'visual_inventory_matched': True,
                'background_strategy_checked': True, 'shape_corner_geometry_checked': True,
            },
        }
        self.deck = {
            'page_count': 1, 'output': 'final/deck.pptx',
            'image_backend': {'backend_id': 'editppt-image-cli'},
            'pages': [{'page_id': 'page_001', 'page_dir': 'pages/page_001',
                       'manifest': 'pages/page_001/manifest.json',
                       'validation': 'pages/page_001/validation.json'}],
        }
        write_json(self.root / 'deck_manifest.json', self.deck)
        write_json(self.page / 'validation.json', {'passed': True})

    def cli(self, script, *args, env=None):
        return subprocess.run(
            [sys.executable, '-B', '-X', 'utf8', str(SKILL / 'runtime' / script),
             *[str(arg) for arg in args]],
            capture_output=True, text=True, encoding='utf-8', env=env,
        )

    def assert_success(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def build_page(self, text='Initial text'):
        self.manifest['text_boxes'] = [
            {'id': 'title', 'text': text, 'box_px': [40, 40, 1000, 100], 'font_size': 24},
        ]
        self.manifest['text_inventory'] = [{'text': text, 'decision': 'native-text'}]
        write_json(self.page / 'manifest.json', self.manifest)
        write_pptx(self.manifest, self.page / 'page.pptx', self.page / 'manifest.json')
        self.assert_success(self.cli('validate_pptx.py', self.page / 'page.pptx',
                                     '--manifest', self.page / 'manifest.json',
                                     '--report', self.page / 'validation.json'))

    def validate_notes(self, expected, actual):
        write_json(self.page / 'manifest.json', self.manifest)
        self.deck['notes_manifest'] = 'notes_manifest.json'
        write_json(self.root / 'deck_manifest.json', self.deck)
        write_json(self.root / 'notes_manifest.json', {'notes': [
            {'page_index': 1, 'text': expected,
             'text_sha256': hashlib.sha256(expected.encode('utf-8')).hexdigest()},
        ]})
        output = self.root / 'deck.pptx'
        write_deck(self.deck, [{'manifest': self.manifest,
                               'manifest_path': self.page / 'manifest.json'}],
                   output, [{'page_index': 1, 'text': actual}])
        result = self.cli('validate_pptx.py', output,
                          '--deck-manifest', self.root / 'deck_manifest.json')
        return result, json.loads(result.stdout)

    def test_missing_notes_part_matches_empty_expected_text(self):
        result, report = self.validate_notes('', '')
        self.assert_success(result)
        self.assertTrue(report['passed'])
        self.assertEqual(report['notes_found'], 0)
        self.assertEqual(report['notes_hash_mismatches'], [])

    def test_nonempty_notes_still_require_matching_text(self):
        for actual, reason in [('', 'missing notes slide'), ('Changed note', 'text hash mismatch')]:
            with self.subTest(actual=actual):
                result, report = self.validate_notes('Expected note', actual)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(report['notes_hash_mismatches'], [
                    {'page_index': 1, 'reason': reason},
                ])

    def test_empty_expected_notes_reject_unexpected_text(self):
        result, report = self.validate_notes('', 'Unexpected note')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(report['notes_hash_mismatches'], [
            {'page_index': 1, 'reason': 'text hash mismatch'},
        ])

    def dispatched_run(self, text='Initial text'):
        write_json(self.root / 'page_jobs.json', {'pages': [
            {'page_id': 'page_001', 'page_dir': 'pages/page_001',
             'page_request': 'pages/page_001/page_request.json', 'status': 'pending',
             'accepted': False},
        ]})
        write_json(self.page / 'page_request.json', {'page_index': 1})
        (self.page / 'worker-prompt.md').write_text('Rebuild the synthetic page.', encoding='utf-8')
        self.assert_success(self.cli('record_page_dispatch.py', self.root, '--page', 1,
                                     '--agent-id', 'worker-a', '--prompt-file', 'worker-prompt.md'))
        self.build_page(text)
        write_json(self.page / 'imagegen-jobs.json', {'jobs': []})
        write_json(self.page / 'page_result.json', {})
        for name in ('preview.png', 'split_assets_contact.png'):
            Image.new('RGB', (16, 9), 'white').save(self.page / name)

    def record(self, agent='worker-a', env=None):
        return self.cli('record_page_result.py', self.root, '--page', 1,
                        '--agent-id', agent, env=env)

    def accepted_run(self):
        self.dispatched_run()
        self.assert_success(self.record())
        self.assert_success(self.cli('finalize_deck_run.py', self.root))

    def test_original_agent_can_refresh_accepted_page_and_refinalize(self):
        self.accepted_run()
        self.build_page('Revised text')
        self.assert_success(self.record())
        jobs = json.loads((self.root / 'page_jobs.json').read_text(encoding='utf-8'))
        page = jobs['pages'][0]
        self.assertEqual(page['status'], 'recorded')
        self.assertFalse(page['accepted'])
        self.assertNotIn('accepted_at', page)
        self.assertEqual(jobs['run_status'], 'pages_recorded')
        self.assertEqual(page['result']['agent_id'], 'worker-a')
        self.assertTrue(page['result']['validation_passed'])
        self.assertEqual(set(page['result']['outputs']), {
            'page_manifest', 'imagegen_jobs', 'page_pptx', 'preview',
            'contact_sheet', 'validation', 'page_result',
        })
        for key, output in page['result']['outputs'].items():
            self.assertEqual(page['result']['hashes'][key],
                             hashlib.sha256((self.root / output).read_bytes()).hexdigest())
        next_result = self.cli('main.py', 'run', 'next', self.root, '--json')
        self.assert_success(next_result)
        self.assertEqual(json.loads(next_result.stdout)['stage'], 'finalize')
        self.assert_success(self.cli('finalize_deck_run.py', self.root))
        presentation = Presentation(self.root / 'final/deck.pptx')
        self.assertIn('Revised text', [shape.text for shape in presentation.slides[0].shapes
                                      if shape.has_text_frame])

    def test_accepted_page_refresh_rejects_a_different_agent(self):
        self.accepted_run()
        previous_jobs = (self.root / 'page_jobs.json').read_bytes()
        result = self.record('worker-b')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Agent id mismatch', result.stderr)
        self.assertEqual((self.root / 'page_jobs.json').read_bytes(), previous_jobs)

    def test_accepted_page_refresh_revalidates_actual_page(self):
        self.accepted_run()
        previous_jobs = (self.root / 'page_jobs.json').read_bytes()
        self.manifest['text_inventory'] = [{'text': 'Unbuilt change'}]
        write_json(self.page / 'manifest.json', self.manifest)
        result = self.record()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Page manifest contract validation failed', result.stderr)
        self.assertEqual((self.root / 'page_jobs.json').read_bytes(), previous_jobs)

    def test_accepted_page_refresh_requires_all_artifacts(self):
        self.accepted_run()
        previous_jobs = (self.root / 'page_jobs.json').read_bytes()
        (self.page / 'split_assets_contact.png').unlink()
        result = self.record()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('split_assets_contact.png', result.stderr)
        self.assertEqual((self.root / 'page_jobs.json').read_bytes(), previous_jobs)

    @unittest.skipUnless(os.name == 'nt', 'Windows legacy child-process encoding regression')
    def test_direct_record_uses_utf8_for_validator_child_output(self):
        self.dispatched_run('Synthetic text: \u03a9 \U0001f680')
        environment = dict(os.environ, PYTHONUTF8='0')
        environment.pop('PYTHONIOENCODING', None)
        self.assert_success(self.record(env=environment))


if __name__ == '__main__':
    unittest.main()
