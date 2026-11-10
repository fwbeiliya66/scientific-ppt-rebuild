"""Snapshot inputs and extract source evidence, never guess Figure identity."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
import os
import posixpath
import re
import shutil
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image

NS = {
    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
    'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
    'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    'rel': 'http://schemas.openxmlformats.org/package/2006/relationships',
}


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def write_json(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def freeze_inputs(inputs, output):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    for index, value in enumerate(inputs, 1):
        original = Path(value).expanduser().resolve(strict=True)
        dest = output / f'{index:03d}_{original.name}'
        if dest.exists():
            raise FileExistsError(f'Refusing to replace snapshot: {dest}')
        for attempt in range(3):
            before = digest(original)
            shutil.copyfile(original, dest)
            after = digest(original)
            if before == after == digest(dest):
                break
        else:
            raise RuntimeError(f'Input changed while snapshotting; close/save it first: {original}')
        rows.append({'original': str(original), 'snapshot': str(dest), 'sha256': before})
    return rows


def relationships(z, part):
    parent, name = posixpath.split(part)
    rel_part = f'{parent}/_rels/{name}.rels'
    if rel_part not in z.namelist():
        return {}
    root = ET.fromstring(z.read(rel_part))
    result = {}
    for rel in root:
        if rel.get('TargetMode') == 'External':
            continue
        target = rel.get('Target', '')
        member = target.lstrip('/') if target.startswith('/') else posixpath.normpath(posixpath.join(parent, target))
        result[rel.get('Id')] = member
    return result


def media_entry(z, member, output, document):
    raw = z.read(member)
    filename = f'{hashlib.sha256(raw).hexdigest()[:16]}_{Path(member).name}'
    dest = Path(output).resolve() / filename
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.read_bytes() != raw:
        raise ValueError(f'Media filename collision: {dest}')
    dest.write_bytes(raw)
    size = None
    try:
        with Image.open(io.BytesIO(raw)) as image:
            size = list(image.size)
    except (OSError, ValueError):
        pass
    return {'document': str(Path(document).resolve()), 'member': member,
            'path': str(dest), 'sha256': hashlib.sha256(raw).hexdigest(),
            'size_px': size, 'figure': None}


def extract_docx(path, output):
    media, blocks, candidates = [], [], []
    with zipfile.ZipFile(path) as z:
        for member in sorted(z.namelist()):
            if member.startswith('word/media/') and not member.endswith('/'):
                media.append(media_entry(z, member, output, path))
        parts = [n for n in z.namelist() if re.fullmatch(r'word/(document|header\d+|footer\d+)\.xml', n)]
        for part in sorted(parts):
            root = ET.fromstring(z.read(part))
            rels = relationships(z, part)
            for index, paragraph in enumerate(root.findall('.//w:p', NS)):
                text = ''.join(t.text or '' for t in paragraph.findall('.//w:t', NS))
                ids = [n.get(f'{{{NS["r"]}}}embed') for n in paragraph.findall('.//a:blip', NS)]
                for node in paragraph.iter():
                    if node.tag.endswith('}imagedata'):
                        ids.append(node.get(f'{{{NS["r"]}}}id'))
                members = [rels[rid] for rid in ids if rid in rels]
                row = {'part': part, 'paragraph': index, 'text': text, 'media_members': members}
                blocks.append(row)
                if re.match(r'^\s*(?:Figure|Fig\.?|Scheme|图)\s*(?:S?\d+|[一二三四五六七八九十])', text, re.I):
                    candidates.append({**row, 'verified': False})
    return {'type': 'docx', 'document': str(Path(path).resolve()), 'media': media,
            'blocks': blocks, 'caption_candidates': candidates}


def extract_pptx(path, output):
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read('ppt/presentation.xml'))
        size = root.find('p:sldSz', NS)
        cx, cy = int(size.get('cx')), int(size.get('cy'))
        rels = relationships(z, 'ppt/presentation.xml')
        slide_parts = [rels[node.get(f'{{{NS["r"]}}}id')] for node in root.findall('p:sldIdLst/p:sldId', NS)]
        media = [media_entry(z, n, output, path) for n in sorted(z.namelist())
                 if n.startswith('ppt/media/') and not n.endswith('/')]
        slides = []
        for page, part in enumerate(slide_parts, 1):
            slide_root = ET.fromstring(z.read(part))
            slide_rels = relationships(z, part)
            tree = slide_root.find('p:cSld/p:spTree', NS)
            objects = []
            for obj in tree if tree is not None else []:
                if obj.tag.rsplit('}', 1)[-1] not in {'sp', 'pic', 'grpSp', 'cxnSp', 'graphicFrame'}:
                    continue
                props = obj.find('.//p:cNvPr', NS)
                text = '\n'.join(''.join(t.text or '' for t in paragraph.findall('.//a:t', NS))
                                 for paragraph in obj.findall('.//a:p', NS))
                ids = [b.get(f'{{{NS["r"]}}}embed') for b in obj.findall('.//a:blip', NS)]
                objects.append({'id': props.get('id') if props is not None else None,
                                'name': props.get('name') if props is not None else None,
                                'kind': obj.tag.rsplit('}', 1)[-1], 'text': text,
                                'media_members': [slide_rels[r] for r in ids if r in slide_rels],
                                'xml': ET.tostring(obj, encoding='unicode')})
            slides.append({'page': page, 'part': part, 'objects': objects})
    return {'type': 'pptx', 'document': str(Path(path).resolve()), 'slide': {
        'width': cx / 914400, 'height': cy / 914400, 'size_mode': 'source'},
        'size_emu': [cx, cy], 'slides': slides, 'media': media}


def extract_pdf(path, output):
    import fitz
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    media, pages = [], []
    seen = set()
    with fitz.open(path) as doc:
        for index, page in enumerate(doc, 1):
            refs = []
            for item in page.get_images(full=True):
                xref, smask = item[0], item[1]
                refs.append({'xref': xref, 'soft_mask': smask})
                if xref in seen:
                    continue
                seen.add(xref)
                image = doc.extract_image(xref)
                dest = output / f'xref_{xref}.{image["ext"]}'
                dest.write_bytes(image['image'])
                media.append({'document': str(Path(path).resolve()), 'member': f'pdf:xref:{xref}',
                              'path': str(dest), 'sha256': digest(dest), 'size_px': [image['width'], image['height']],
                              'figure': None, 'soft_mask': smask,
                              'needs_composite_review': bool(smask)})
            pages.append({'page': index, 'text': page.get_text(), 'images': refs,
                          'size_pt': [page.rect.width, page.rect.height]})
    return {'type': 'pdf', 'document': str(Path(path).resolve()), 'media': media, 'pages': pages}


def contain_box(box, crop):
    x, y, width, height = map(float, box)
    _, _, cw, ch = map(float, crop)
    if min(width, height, cw, ch) <= 0:
        raise ValueError('Image and placement must have positive dimensions')
    scale = min(width / cw, height / ch)
    w, h = cw * scale, ch * scale
    return [x + (width - w) / 2, y + (height - h) / 2, w, h]


def render_paper_pdf(run, paper, page_number, dpi):
    import fitz
    run = Path(run).resolve()
    catalog_path = run / 'source_catalog.json'
    catalog = json.loads(catalog_path.read_text(encoding='utf-8'))
    candidates = [d for d in catalog['documents'] if d.get('type') == 'pdf' and d.get('input_role') == 'papers'
                  and any(str(paper) == d.get(k) or Path(paper).name == Path(d.get(k, '')).name
                          for k in ['document', 'original_document'])]
    if len(candidates) != 1:
        raise ValueError('Choose an unambiguous PDF paper in this run catalog')
    source = Path(candidates[0]['document'])
    if dpi <= 0:
        raise ValueError('DPI must be positive')
    output = run / 'extracted/pdf_renders' / f'{source.stem}_page{page_number}_{dpi}dpi.png'
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError(f'Refusing to replace an existing PDF render: {output}')
    with fitz.open(source) as document:
        if not 1 <= page_number <= len(document):
            raise ValueError('PDF page out of bounds')
        pix = document[page_number-1].get_pixmap(dpi=dpi, alpha=False)
        pix.save(output)
        size = [pix.width, pix.height]
    entry = {'document': str(source), 'member': f'pdf:page:{page_number}:render:{dpi}dpi',
             'path': str(output), 'sha256': digest(output), 'size_px': size, 'figure': None,
             'extraction': 'pdf-render', 'page': page_number, 'dpi': dpi,
             'source_document_sha256': digest(source)}
    candidates[0]['media'].append(entry)
    write_json(catalog_path, catalog)
    return entry


def init_run(slides, papers, run):
    run = Path(run).expanduser().resolve()
    run.mkdir(parents=True, exist_ok=False)
    slide_rows = freeze_inputs(slides, run / 'snapshots/slides')
    paper_rows = freeze_inputs(papers, run / 'snapshots/papers')
    catalog = {'schema_version': 1, 'mode': 'paper-replacement' if papers else 'source-preservation',
               'slide_inputs': slide_rows, 'paper_inputs': paper_rows, 'documents': []}
    for kind, rows in [('slides', slide_rows), ('papers', paper_rows)]:
        for index, row in enumerate(rows, 1):
            path = Path(row['snapshot'])
            output = run / f'extracted/{kind}/{index:03d}'
            extractor = {'.pptx': extract_pptx, '.docx': extract_docx, '.pdf': extract_pdf}.get(path.suffix.lower())
            if extractor:
                entry = extractor(path, output)
                entry.update(input_role=kind, original_document=row['original'])
                catalog['documents'].append(entry)
            elif kind == 'papers':
                raise ValueError(f'Paper format requires conversion to DOCX/PDF: {path}')
    write_json(run / 'source_catalog.json', catalog)
    print(json.dumps({'run': str(run), 'mode': catalog['mode'],
                      'slides': [r['snapshot'] for r in slide_rows],
                      'catalog': str(run / 'source_catalog.json')}, ensure_ascii=False, indent=2))


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('doctor')
    render = sub.add_parser('render-pdf')
    render.add_argument('--run', required=True)
    render.add_argument('--paper', required=True)
    render.add_argument('--page', type=int, required=True)
    render.add_argument('--dpi', type=int, default=300)
    init = sub.add_parser('init')
    init.add_argument('--run', required=True)
    init.add_argument('--slides', nargs='+', required=True)
    init.add_argument('--papers', nargs='*', default=[])
    args = parser.parse_args()
    if args.command == 'render-pdf':
        print(json.dumps(render_paper_pdf(args.run, args.paper, args.page, args.dpi), ensure_ascii=False, indent=2))
        return 0
    if args.command == 'doctor':
        modules = {name: importlib.util.find_spec(name) is not None
                   for name in ['PIL', 'fitz', 'pptx', 'numpy', 'requests', 'openai', 'yaml']}
        pp = False
        if os.name == 'nt':
            import winreg
            try:
                with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, 'PowerPoint.Application'):
                    pp = True
            except OSError:
                pass
        print(json.dumps({'python': sys.executable, 'modules': modules,
                          'powerpoint_registered': pp, 'libreoffice': shutil.which('soffice'),
                          'agent_capability': 'Must be checked by the calling agent, not inferred here.'}, indent=2))
        return 0 if all(modules.values()) else 1
    init_run(args.slides, args.papers, args.run)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
