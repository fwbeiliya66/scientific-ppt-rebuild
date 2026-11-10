import json
import sys
import tempfile
import unittest
from pathlib import Path
from PIL import Image

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / 'scripts'))
from page_builder import Page
from sources import write_json
from audit import audit_page


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.page = self.root / 'deck/pages/page_001'
        self.page.mkdir(parents=True)
        write_json(self.page / 'page_request.json', {'source_size_px': {'width': 1600, 'height': 900},
                  'slide': {'width': 13.333333333333334, 'height': 7.5}, 'content_box': {'left': 0, 'top': 0, 'width': 13.333333333333334, 'height': 7.5}, 'page_index': 1})
        self.picture = self.root / 'plot.png'
        Image.new('RGB', (120, 60), 'white').save(self.picture)
        p = Page(self.page)
        p.text('title', 'Results', [10, 10, 300, 60], 20)
        p.shape('frame', [40, 150, 550, 300], stroke='#12377D')
        p.image('plot', self.picture, [50, 160, 500, 250], scientific_source={'status': 'source-preserved', 'evidence': 'Source verified'})
        p.save()
        self.manifest = p.manifest
        self.inventory = {'reviewed_against_source': True, 'items': [
            {'id': 'title', 'kind': 'native_text', 'text': 'Results', 'source_box_px': [10, 10, 300, 60], 'object_ids': ['title']},
            {'id': 'frame', 'kind': 'native_shape', 'source_box_px': [40, 150, 550, 300], 'object_ids': ['frame']},
            {'id': 'plot', 'kind': 'scientific_image', 'source_box_px': [50, 160, 500, 250], 'object_ids': ['plot']}]}
        write_json(self.page / 'inventory.json', self.inventory)

    def tearDown(self):
        self.tmp.cleanup()

    def run_audit(self):
        write_json(self.page / 'manifest.json', self.manifest)
        return audit_page(self.page)

    def test_both_original_and_paper_modes(self):
        self.assertTrue(self.run_audit()['passed'])
        self.manifest['images'][0]['scientific_source'] = {'status': 'matched-paper', 'document': 'paper.docx', 'figure': 'Figure 3', 'panel': 'a', 'media_member': 'word/media/image4.png', 'evidence': 'Actual figure and data visually verified'}
        self.manifest['asset_provenance'][0]['authorized_role'] = 'word_original'
        write_json(self.root / 'source_catalog.json', {'documents': [{'input_role': 'papers',
            'document': 'paper.docx', 'original_document': 'paper.docx', 'media': [
                {'member': 'word/media/image4.png', 'sha256': self.manifest['asset_provenance'][0]['sha256']}]}]})
        self.assertTrue(self.run_audit()['passed'])

    def test_rejects_missing_object_and_stretched_image(self):
        self.manifest['images'][0]['box_px'][3] = 400
        self.manifest['text_boxes'] = []
        result = self.run_audit()
        self.assertFalse(result['passed'])
        self.assertTrue(any('aspect' in e for e in result['errors']))
        self.assertTrue(any('missing' in e for e in result['errors']))

    def test_rejects_unverified_assignment_and_changed_media(self):
        self.manifest['images'][0]['scientific_source'] = {'status': 'matched-paper', 'evidence': 'Guess'}
        Image.new('RGB', (120, 60), 'red').save(self.picture)
        result = self.run_audit()
        self.assertFalse(result['passed'])
        self.assertTrue(any('Figure' in e for e in result['errors']))
        self.assertTrue(any('source hash' in e for e in result['errors']))

    def test_paper_claim_must_match_actual_catalog_member_and_hash(self):
        self.manifest['images'][0]['scientific_source'] = {'status': 'matched-paper', 'document': 'paper.docx',
            'figure': 'Figure 3', 'media_member': 'word/media/image4.png', 'evidence': 'Verified'}
        self.manifest['asset_provenance'][0]['authorized_role'] = 'word_original'
        sha = self.manifest['asset_provenance'][0]['sha256']
        write_json(self.root / 'source_catalog.json', {'documents': [{'input_role': 'papers',
            'document': 'paper.docx', 'original_document': 'paper.docx',
            'media': [{'member': 'word/media/image9.png', 'sha256': sha}]}]})
        self.assertFalse(self.run_audit()['passed'])
        catalog = json.loads((self.root / 'source_catalog.json').read_text(encoding='utf-8'))
        catalog['documents'][0]['media'][0]['member'] = 'word/media/image4.png'
        write_json(self.root / 'source_catalog.json', catalog)
        self.assertTrue(self.run_audit()['passed'])

    def test_unmatched_preservation_is_not_synthetic_replacement(self):
        self.manifest['images'][0]['scientific_source'] = {'status': 'unmatched-preserved', 'evidence': 'No exact microscope field in supplied paper'}
        self.manifest['asset_provenance'][0]['authorized_role'] = 'preserve_missing_research_region'
        self.assertTrue(self.run_audit()['passed'])

    def test_no_hidden_native_text_or_false_inventory_review(self):
        self.manifest['text_boxes'][0]['opacity'] = 0
        self.inventory['reviewed_against_source'] = False
        write_json(self.page / 'inventory.json', self.inventory)
        self.assertFalse(self.run_audit()['passed'])


if __name__ == '__main__':
    unittest.main()
