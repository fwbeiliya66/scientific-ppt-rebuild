import hashlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from PIL import Image

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / 'scripts'))
from sources import freeze_inputs, extract_docx, extract_pptx, contain_box, render_paper_pdf, write_json


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        image = io.BytesIO()
        Image.new('RGB', (120, 60), 'white').save(image, format='PNG')
        self.png = image.getvalue()

    def tearDown(self):
        self.tmp.cleanup()

    def test_snapshot_is_stable_and_collision_safe(self):
        a = self.root / 'a'; b = self.root / 'b'
        a.mkdir(); b.mkdir()
        (a / 'same.docx').write_bytes(b'first')
        (b / 'same.docx').write_bytes(b'second')
        rows = freeze_inputs([a / 'same.docx', b / 'same.docx'], self.root / 'snapshots')
        self.assertNotEqual(rows[0]['snapshot'], rows[1]['snapshot'])
        (a / 'same.docx').write_bytes(b'changed')
        self.assertEqual(Path(rows[0]['snapshot']).read_bytes(), b'first')
        self.assertEqual(rows[1]['sha256'], hashlib.sha256(b'second').hexdigest())

    def test_docx_preserves_bytes_without_guessing_figure_number(self):
        path = self.root / 'paper.docx'
        with zipfile.ZipFile(path, 'w') as z:
            z.writestr('word/media/image4.png', self.png)
            z.writestr('word/document.xml', '''<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><w:body><w:p><w:r><w:drawing><a:blip r:embed="rId9"/></w:drawing></w:r></w:p><w:p><w:r><w:t>Unrelated paragraph</w:t></w:r></w:p><w:p><w:r><w:t>Figure 3. Caption collected at the end.</w:t></w:r></w:p></w:body></w:document>''')
            z.writestr('word/_rels/document.xml.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId9" Target="media/image4.png" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"/></Relationships>')
        result = extract_docx(path, self.root / 'media')
        self.assertEqual(Path(result['media'][0]['path']).read_bytes(), self.png)
        self.assertIsNone(result['media'][0]['figure'])
        self.assertEqual(result['blocks'][0]['media_members'], ['word/media/image4.png'])
        self.assertEqual(result['caption_candidates'][0]['text'], 'Figure 3. Caption collected at the end.')

    def test_pptx_uses_relationship_page_order_and_exact_geometry(self):
        path = self.root / 'source.pptx'
        with zipfile.ZipFile(path, 'w') as z:
            z.writestr('ppt/presentation.xml', '<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><p:sldIdLst><p:sldId r:id="rId2"/><p:sldId r:id="rId1"/></p:sldIdLst><p:sldSz cx="12192000" cy="6858000"/></p:presentation>')
            z.writestr('ppt/_rels/presentation.xml.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="slides/slide1.xml"/><Relationship Id="rId2" Target="slides/slide2.xml"/></Relationships>')
            for n in (1, 2):
                z.writestr(f'ppt/slides/slide{n}.xml', f'<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><p:cSld><p:spTree><p:sp><p:nvSpPr><p:cNvPr id="2" name="text{n}"/></p:nvSpPr><p:txBody><a:p><a:r><a:t>Page {n}</a:t></a:r></a:p></p:txBody></p:sp><p:pic><p:nvPicPr><p:cNvPr id="3" name="plot{n}"/></p:nvPicPr><p:blipFill><a:blip r:embed="rId9"/></p:blipFill></p:pic></p:spTree></p:cSld></p:sld>')
                z.writestr(f'ppt/slides/_rels/slide{n}.xml.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId9" Target="../media/image1.png" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"/></Relationships>')
            z.writestr('ppt/media/image1.png', self.png)
        result = extract_pptx(path, self.root / 'ppt_media')
        self.assertEqual(result['slide']['width'], 960 / 72)
        self.assertEqual(result['slides'][0]['part'], 'ppt/slides/slide2.xml')
        self.assertEqual(result['slides'][0]['objects'][0]['text'], 'Page 2')
        self.assertEqual(Path(result['media'][0]['path']).read_bytes(), self.png)

    def test_fit_preserves_crop_aspect(self):
        self.assertEqual(contain_box([0, 0, 100, 100], [0, 0, 120, 60]), [0, 25, 100, 50])
        with self.assertRaises(ValueError):
            contain_box([0, 0, 100, 100], [0, 0, 0, 60])

    def test_pdf_vector_page_render_has_truthful_source_trace(self):
        import fitz
        pdf = self.root / 'paper.pdf'
        with fitz.open() as document:
            page = document.new_page(width=200, height=100)
            page.draw_rect(fitz.Rect(20, 20, 80, 80), color=(1, 0, 0))
            document.save(pdf)
        catalog = {'documents': [{'type': 'pdf', 'input_role': 'papers', 'document': str(pdf),
                                 'original_document': str(pdf), 'media': []}]}
        write_json(self.root / 'source_catalog.json', catalog)
        result = render_paper_pdf(self.root, str(pdf), 1, 144)
        self.assertEqual(result['size_px'], [400, 200])
        self.assertEqual(result['extraction'], 'pdf-render')
        self.assertEqual(result['source_document_sha256'], hashlib.sha256(pdf.read_bytes()).hexdigest())
        self.assertEqual(json.loads((self.root / 'source_catalog.json').read_text(encoding='utf-8'))['documents'][0]['media'][0]['sha256'], result['sha256'])


if __name__ == '__main__':
    unittest.main()
