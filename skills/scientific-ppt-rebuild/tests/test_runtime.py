import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from pptx import Presentation

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / 'runtime'))
from build_pptx_from_manifest import write_pptx, deck_slide_size


class RuntimeTests(unittest.TestCase):
    def test_single_page_build_preserves_notes_and_geometry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = {'source': {'width_px': 1000, 'height_px': 750},
                        'slide': {'width': 10, 'height': 7.5},
                        'notes': 'Preserve this note.', 'text_boxes': [], 'shapes': [], 'images': []}
            path = root / 'manifest.json'; path.write_text(json.dumps(manifest), encoding='utf-8')
            output = root / 'page.pptx'
            write_pptx(manifest, output, path)
            presentation = Presentation(output)
            self.assertEqual(presentation.slides[0].notes_slide.notes_text_frame.text, 'Preserve this note.')
            self.assertEqual(presentation.slide_width, 9144000)

    def test_completed_run_does_not_request_refinalization(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, payload in {
                'deck_manifest.json': {'image_backend': {'backend_id': 'editppt-image-cli'}, 'output': 'final.pptx'},
                'page_jobs.json': {'max_concurrent_pages': 6, 'pages': [{'page_id': 'page_001', 'status': 'accepted'}]},
                'run_state.json': {'status': 'complete'}}.items():
                (root / name).write_text(json.dumps(payload), encoding='utf-8')
            (root / 'final.pptx').write_bytes(b'owned output')
            result = subprocess.run([sys.executable, '-X', 'utf8', str(SKILL / 'runtime/main.py'),
                                     'run', 'next', str(root), '--json'], capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['stage'], 'complete')


if __name__ == '__main__':
    unittest.main()
