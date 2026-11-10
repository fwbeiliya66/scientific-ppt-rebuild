import contextlib
import binascii
import io
import struct
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from PIL import Image
from PIL.PngImagePlugin import PngInfo

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
from check_release import inspect_file, public_files, text_issues
import build_release
from build_release import write_zip


class ReleaseTests(unittest.TestCase):
    def test_credential_and_user_path_are_rejected(self):
        token = 'gh' + 'p_' + 'A' * 35
        private_path = '\\'.join(('C:', 'Users', 'ExampleUser', 'private.txt'))
        self.assertTrue(text_issues(token))
        self.assertTrue(text_issues(private_path))
        self.assertFalse(text_issues('SYNTHETIC DEMO; x=0 to 40; source-figure.png'))

    def test_archive_xml_metadata_is_scanned(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'sample.pptx'
            private_path = '/'.join(('', 'home', 'ExampleUser', 'source'))
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr('docProps/core.xml', '<source>' + private_path + '</source>')
            self.assertTrue(inspect_file(path))

    def test_local_runtime_configuration_and_credentials_are_rejected(self):
        for relative in ('runtime/config.yaml', 'runtime/config.local.yml',
                         'runtime/local_config.yaml', 'runtime/credentials.txt',
                         'runtime/config/local.yaml'):
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                path = root / 'skills/scientific-ppt-rebuild' / relative
                path.parent.mkdir(parents=True)
                path.write_text('PADDLE_OCR_TOKEN: SYNTHETIC_PRIVATE_VALUE\n', encoding='utf-8')
                with self.assertRaises(ValueError):
                    public_files(root)

    def test_reusable_yaml_and_configuration_code_remain_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            entries = {'runtime/config.py': "value = config.get('OPENAI_API_KEY')\n",
                       'agents/openai.yaml': 'name: synthetic\n'}
            for relative, content in entries.items():
                path = root / 'skills/scientific-ppt-rebuild' / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding='utf-8')
                self.assertEqual(inspect_file(path), [])
            self.assertEqual({p.relative_to(root / 'skills/scientific-ppt-rebuild').as_posix()
                              for p in public_files(root)}, set(entries))

    def test_xml_entities_in_pptx_text_and_attributes_are_scanned(self):
        private_path = '/'.join(('', 'home', 'ExampleUser', 'source'))
        encoded = private_path.replace('/', '&#47;')
        for member in ('docProps/core.xml', 'docProps/core.XML'):
            for xml in ('<source>' + encoded + '</source>', '<source original="' + encoded + '"/>'):
                with self.subTest(member=member, xml=xml), tempfile.TemporaryDirectory() as tmp:
                    path = Path(tmp) / 'sample.pptx'
                    with zipfile.ZipFile(path, 'w') as archive:
                        archive.writestr(member, xml)
                    self.assertIn(member + ': local user path', inspect_file(path))

    def test_external_pptx_relationships_are_detected_with_either_quote_style(self):
        for quote in ("'", '"'):
            with self.subTest(quote=quote), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / 'sample.pptx'
                member = 'ppt/slides/_rels/slide1.xml.rels'
                xml = ('<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                       '<Relationship Id="rId1" Type="example" Target="https://example.invalid/file" '
                       'TargetMode=' + quote + 'External' + quote + '/></Relationships>')
                with zipfile.ZipFile(path, 'w') as archive:
                    archive.writestr(member, xml)
                self.assertIn(member + ': external relationship', inspect_file(path))

    def test_embedded_png_metadata_and_exif_are_scanned(self):
        metadata = PngInfo()
        metadata.add_text('source', '/'.join(('', 'home', 'ExampleUser', 'source')))
        exif = Image.Exif()
        exif[315] = 'Synthetic creator'
        for options, expected in (({'pnginfo': metadata}, 'local user path'),
                                  ({'exif': exif}, 'Unexpected EXIF metadata')):
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as tmp:
                image = io.BytesIO()
                Image.new('RGB', (2, 2), 'white').save(image, format='PNG', **options)
                path = Path(tmp) / 'sample.pptx'
                member = 'ppt/media/image1.png'
                with zipfile.ZipFile(path, 'w') as archive:
                    archive.writestr(member, image.getvalue())
                self.assertIn(member + ': ' + expected, inspect_file(path))

    def test_png_metadata_after_image_data_is_scanned(self):
        stream = io.BytesIO()
        Image.new('RGB', (2, 2), 'white').save(stream, format='PNG')
        payload = b'source\x00' + '/'.join(('', 'home', 'ExampleUser', 'source')).encode('ascii')
        chunk = (struct.pack('>I', len(payload)) + b'tEXt' + payload +
                 struct.pack('>I', binascii.crc32(b'tEXt' + payload) & 0xffffffff))
        raw = stream.getvalue()
        png = raw[:-12] + chunk + raw[-12:]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            standalone, embedded = root / 'sample.png', root / 'sample.pptx'
            standalone.write_bytes(png)
            with zipfile.ZipFile(embedded, 'w') as archive:
                archive.writestr('ppt/media/image1.png', png)
            for path in (standalone, embedded):
                with self.subTest(suffix=path.suffix):
                    self.assertTrue(any('local user path' in issue for issue in inspect_file(path)))

    def test_only_approved_public_paths_are_selected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'README.md').write_text('Public example.', encoding='utf-8')
            (root / '.env').write_text('LOCAL_ONLY=1', encoding='utf-8')
            (root / 'dist').mkdir()
            (root / 'dist' / 'local.txt').write_text('not a source file')
            self.assertEqual([p.name for p in public_files(root)], ['README.md'])
            (root / 'private-notes.docx').write_bytes(b'not public')
            with self.assertRaises(ValueError):
                public_files(root)

    def test_zip_is_deterministic_and_rejects_unsafe_members(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'a.txt'; source.write_text('SYNTHETIC DEMO', encoding='utf-8')
            first, second = root / 'one.zip', root / 'two.zip'
            write_zip(first, [(source, 'skill/a.txt')])
            write_zip(second, [(source, 'skill/a.txt')])
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with self.assertRaises(ValueError):
                write_zip(root / 'unsafe.zip', [(source, '../private.txt')])

    def test_zip_rejects_windows_and_posix_unsafe_member_names(self):
        members = ('/absolute.txt', '../private.txt', 'skill/../private.txt',
                   'C:/private.txt', 'C:private.txt', 'skill/name:stream.txt',
                   'skill\\private.txt', '.', 'skill/file.txt\x00suffix')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'source.txt'
            source.write_text('SYNTHETIC DEMO', encoding='utf-8')
            for index, member in enumerate(members):
                with self.subTest(member=member):
                    destination = root / f'unsafe-{index}.zip'
                    with self.assertRaises(ValueError):
                        write_zip(destination, [(source, member)])
                    self.assertFalse(destination.exists())

    def test_zip_order_and_platform_metadata_are_normalized(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first, second = root / 'a.txt', root / 'b.txt'
            first.write_text('Synthetic A', encoding='utf-8')
            second.write_text('Synthetic B', encoding='utf-8')
            destination = root / 'release.zip'
            write_zip(destination, [(first, 'skill/z.txt'), (second, 'skill/a.txt')])
            with zipfile.ZipFile(destination) as archive:
                with self.subTest(property='member order'):
                    self.assertEqual(archive.namelist(), ['skill/a.txt', 'skill/z.txt'])
                with self.subTest(property='platform metadata'):
                    self.assertEqual({info.create_system for info in archive.infolist()}, {3})

    def test_build_refuses_nonempty_output_without_overwriting_checksums(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            checksum = output / 'SHA256SUMS.txt'
            checksum.write_bytes(b'Synthetic existing file')
            with mock.patch.object(build_release, 'check_repo', return_value=[]), \
                    mock.patch.object(build_release, 'public_files', return_value=[]), \
                    contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
                build_release.main(['--output', str(output)])
            self.assertEqual(checksum.read_bytes(), b'Synthetic existing file')
            self.assertEqual(list(output.iterdir()), [checksum])


if __name__ == '__main__':
    unittest.main()
