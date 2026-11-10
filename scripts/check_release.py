#!/usr/bin/env python3
"""Check the intentionally small public source tree and synthetic artifacts."""
import argparse
import csv
import hashlib
import io
import json
import math
import re
import stat
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
SKILL = Path('skills/scientific-ppt-rebuild')
ROOT_FILES = {'.gitignore', '.gitattributes', 'VERSION', 'LICENSE', 'NOTICE',
              'README.md', 'README.zh-CN.md', 'CONTRIBUTING.md', 'install.py', 'Install.ps1'}
IGNORE_DIRS = {'.git', '.venv', '__pycache__', '.pytest_cache', 'dist', 'build',
               'runs', 'work', 'outputs', 'inputs', 'artifacts'}
DEMO_FILES = {'README.md', 'generate.py', 'data.csv', 'source-figure.png',
              'synthetic-paper.pdf', 'editable-demo.pptx', 'flattened-input.pptx',
              'before.png', 'after.png', 'draft-figure.png', 'draft-demo.pptx',
              'figure-mapping.csv'}
TEXT_SUFFIXES = {'.py', '.ps1', '.md', '.yaml', '.yml', '.txt', '.svg', '.csv'}
LOCAL_DATA_DIRS = {'config', 'configs', 'generated', 'run', 'runs', 'jobs', 'output',
                   'outputs', 'work', 'input', 'inputs', 'data', 'artifacts', 'temp', 'tmp'}
PRIVATE_DATA_STEMS = {'config', 'auth', 'credentials', 'secrets', 'token', 'tokens'}
PATTERNS = {
    'credential-like token': re.compile(r'\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{20,})'),
    'private key': re.compile(r'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----'),
    'local user path': re.compile(r'(?i)(?:\b[A-Z]:[\\/]+Users[\\/]+[^\\/\s<>"\r\n]+|/(?:home|Users)/[A-Za-z0-9._-]+/)'),
}


def text_issues(text):
    return [name for name, pattern in PATTERNS.items() if pattern.search(text)]


def public_files(root=ROOT):
    """Reject unexpected material rather than recursively publishing a workspace."""
    result = []
    for path in sorted(Path(root).rglob('*')):
        rel = path.relative_to(root)
        if any(part in IGNORE_DIRS for part in rel.parts) or path.name.startswith('.env'):
            continue
        if path.is_symlink() or bool(getattr(path.lstat(), 'st_file_attributes', 0)
                                     & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0)):
            raise ValueError(f'Symbolic link is not a release source: {rel.as_posix()}')
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        if rel.is_relative_to(SKILL) and (
            any(part.lower() in LOCAL_DATA_DIRS for part in rel.relative_to(SKILL).parts[:-1]) or
            (suffix in {'.yaml', '.yml', '.txt'} and PRIVATE_DATA_STEMS.intersection(
                path.stem.lower().replace('_', '.').replace('-', '.').split('.')))
        ):
            raise ValueError(f'Local configuration or task data is not a release source: {rel.as_posix()}')
        allowed = (len(rel.parts) == 1 and path.name in ROOT_FILES)
        allowed |= rel.is_relative_to(SKILL) and (suffix in TEXT_SUFFIXES - {'.svg', '.csv'} or path.name in {'LICENSE', 'NOTICE'})
        allowed |= rel.parts[0] == 'docs' and suffix in {'.md', '.svg', '.png'}
        allowed |= rel.parent == Path('examples/synthetic-signal') and path.name in DEMO_FILES
        allowed |= rel.parts[0] == '.github' and suffix in {'.yml', '.yaml'}
        allowed |= rel.parts[0] in {'scripts', 'tests'} and suffix == '.py'
        if not allowed:
            raise ValueError(f'Unexpected public-source path: {rel.as_posix()}')
        result.append(path)
    return result


def png_issues(source):
    from PIL import Image
    with Image.open(source) as image:
        image.load()
        errors = text_issues(str(image.info))
        if image.getexif():
            errors.append('Unexpected EXIF metadata')
    return errors


def inspect_file(path):
    path = Path(path)
    errors = []
    suffix = path.suffix.lower()
    if suffix in TEXT_SUFFIXES or path.name in {'LICENSE', 'NOTICE', 'VERSION', '.gitignore', '.gitattributes'}:
        text = path.read_text(encoding='utf-8-sig')
        errors.extend(text_issues(text))
        if suffix == '.svg':
            tree = ET.fromstring(text)
            for element in tree.iter():
                if element.tag.rsplit('}', 1)[-1] in {'script', 'foreignObject'}:
                    errors.append('Active SVG content')
                if any(key.rsplit('}', 1)[-1] == 'href' and not value.startswith('#')
                       for key, value in element.attrib.items()):
                    errors.append('External SVG resource')
    elif suffix == '.pptx':
        with zipfile.ZipFile(path) as archive:
            for name in archive.namelist():
                lower_name = name.lower()
                if lower_name.endswith(('.xml', '.rels')):
                    text = archive.read(name).decode('utf-8-sig')
                    tree = ET.fromstring(text)
                    decoded = ''.join(tree.itertext()) + '\n' + '\n'.join(
                        value for element in tree.iter() for value in element.attrib.values())
                    issues = dict.fromkeys(text_issues(text) + text_issues(decoded))
                    errors.extend(f'{name}: {issue}' for issue in issues)
                    if lower_name.endswith('.rels') and any(
                        element.tag.rsplit('}', 1)[-1] == 'Relationship' and
                        element.get('TargetMode', '').lower() == 'external' for element in tree.iter()
                    ):
                        errors.append(f'{name}: external relationship')
                elif lower_name.startswith('ppt/media/') and lower_name.endswith('.png'):
                    errors.extend(f'{name}: {issue}' for issue in png_issues(io.BytesIO(archive.read(name))))
    elif suffix == '.pdf':
        import pymupdf
        with pymupdf.open(path) as document:
            text = json.dumps(document.metadata) + '\n'.join(page.get_text() for page in document)
            errors.extend(text_issues(text))
    elif suffix == '.png':
        errors.extend(png_issues(path))
    return errors


def check_repo(root=ROOT):
    root = Path(root)
    errors = []
    try:
        files = public_files(root)
    except ValueError as error:
        return [str(error)]
    required = ['LICENSE', 'NOTICE', 'VERSION', 'README.md', 'README.zh-CN.md',
                'install.py', 'Install.ps1', str(SKILL / 'SKILL.md'), str(SKILL / 'LICENSE'),
                str(SKILL / 'runtime/LICENSE'), 'docs/assets/hero.svg',
                'docs/assets/before-after.png', 'docs/assets/workflow.svg',
                'examples/synthetic-signal/editable-demo.pptx', 'examples/synthetic-signal/synthetic-paper.pdf']
    errors.extend(f'Missing required file: {name}' for name in required if not (root / name).is_file())
    for path in files:
        try:
            errors.extend(f'{path.relative_to(root).as_posix()}: {issue}' for issue in inspect_file(path))
        except (ValueError, OSError, ET.ParseError, zipfile.BadZipFile) as error:
            errors.append(f'{path.relative_to(root).as_posix()}: {type(error).__name__}')
        if path.suffix.lower() == '.md':
            for link in re.findall(r'\]\(([^)]+)\)', path.read_text(encoding='utf-8-sig')):
                if link.startswith(('https:', 'http:', '#', 'mailto:')):
                    continue
                target = unquote(link.split('#', 1)[0]).strip('<>')
                if target and not (path.parent / target).exists():
                    errors.append(f'{path.relative_to(root).as_posix()}: missing link {target}')
    demo = root / 'examples/synthetic-signal'
    if (demo / 'data.csv').is_file():
        rows = list(csv.DictReader((demo / 'data.csv').open(encoding='utf-8')))
        if len(rows) != 41 or any(int(row['x']) != i or row['data_kind'] != 'SYNTHETIC DEMO'
                or abs(float(row['y_A']) - math.exp(-0.08 * i)) > 5.1e-13
                or abs(float(row['y_B']) - 0.7 * math.exp(-0.04 * i)) > 5.1e-13
                for i, row in enumerate(rows)):
            errors.append('Synthetic CSV does not match the documented formulas')
    if (demo / 'editable-demo.pptx').is_file() and (demo / 'source-figure.png').is_file():
        from pptx import Presentation
        def leaves(shapes):
            for shape in shapes:
                if shape.shape_type == 6:
                    yield from leaves(shape.shapes)
                else:
                    yield shape
        deck = Presentation(demo / 'editable-demo.pptx')
        pictures = [shape for slide in deck.slides for shape in leaves(slide.shapes) if shape.shape_type == 13]
        expected = hashlib.sha256((demo / 'source-figure.png').read_bytes()).digest()
        if len(deck.slides) != 1 or len(pictures) != 1 or hashlib.sha256(pictures[0].image.blob).digest() != expected:
            errors.append('Demo picture differs from the original synthetic figure')
        elif any(getattr(pictures[0], key) for key in ('crop_left', 'crop_right', 'crop_top', 'crop_bottom')):
            errors.append('Controlled demo has an unexpected figure crop')
    return errors


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    errors = check_repo()
    print(json.dumps({'passed': not errors, 'errors': errors}, ensure_ascii=False, indent=2))
    return int(bool(errors))


if __name__ == '__main__':
    sys.exit(main())
