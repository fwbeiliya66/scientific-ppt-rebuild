"""Scientific editability/provenance gates supplement runtime structural validation."""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image
from sources import digest, write_json

ROOT = Path(__file__).resolve().parents[1]
SCIENCE_ROLES = {'word_original', 'source_scientific', 'preserve_missing_research_region'}
ORIGINAL_ROLES = SCIENCE_ROLES | {'original_logo', 'complex_original'}


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def compact(text):
    return re.sub(r'\s+', '', text or '')


def audit_page(directory):
    directory = Path(directory).resolve()
    errors = []
    manifest = load(directory / 'manifest.json')
    inventory = load(directory / 'inventory.json')
    if inventory.get('reviewed_against_source') is not True:
        errors.append('Inventory not visually reviewed against source')
    groups = {'native_text': manifest.get('text_boxes', []), 'native_shape': manifest.get('shapes', []),
              'scientific_image': manifest.get('images', []), 'complex_image': manifest.get('images', []),
              'logo_image': manifest.get('images', [])}
    all_objects = manifest.get('text_boxes', []) + manifest.get('shapes', []) + manifest.get('images', [])
    ids = [o.get('id') for o in all_objects]
    if len(ids) != len(set(ids)) or any(not i for i in ids):
        errors.append('Object IDs must be nonempty and unique')
    covered = set()
    for item in inventory.get('items', []):
        kind = item.get('kind')
        relevant = {o.get('id'): o for o in groups.get(kind, [])}
        targets = item.get('object_ids', [])
        if kind not in groups or not targets or len(item.get('source_box_px', [])) != 4:
            errors.append(f'Invalid inventory item: {item.get("id")}')
        for target in targets:
            if target not in relevant:
                errors.append(f'Inventory missing/wrong-type object: {target}')
            else:
                covered.add(target)
        if kind == 'native_text':
            actual = ''.join(relevant[t].get('text', '') for t in targets if t in relevant)
            if not compact(item.get('text')) or compact(item.get('text')) != compact(actual):
                errors.append(f'Inventory text differs from native text: {item.get("id")}')
        if kind in {'scientific_image', 'complex_image', 'logo_image'}:
            for target in targets:
                obj = relevant.get(target, {})
                status = obj.get('scientific_source', {}).get('status', '')
                if kind == 'scientific_image' and status not in {'matched-paper', 'source-preserved', 'unmatched-preserved'}:
                    errors.append(f'Scientific inventory has non-scientific source status: {target}')
                if kind != 'scientific_image' and not status.startswith('illustration-'):
                    errors.append(f'Illustration inventory incorrectly classified: {target}')
    if not inventory.get('items'):
        errors.append('Empty page inventory')
    for obj in all_objects:
        if obj.get('id') not in covered:
            errors.append(f'Object absent from coverage inventory: {obj.get("id")}')
    for obj in manifest.get('text_boxes', []):
        if not compact(obj.get('text')) or obj.get('hidden') or obj.get('opacity', 1) == 0:
            errors.append(f'Empty or hidden native text: {obj.get("id")}')
        box = obj.get('box_px', [])
        if len(box) != 4 or min(box[2:]) <= 0 or not all(math.isfinite(float(v)) for v in box):
            errors.append(f'Invalid native text placement: {obj.get("id")}')
    provenance = {p.get('path'): p for p in manifest.get('asset_provenance', [])}
    catalog_path = directory.parents[2] / 'source_catalog.json'
    catalog = load(catalog_path) if catalog_path.is_file() else {}
    source_area = manifest['source']['width_px'] * manifest['source']['height_px']
    image_rows = []
    for obj in manifest.get('images', []):
        name = obj.get('id')
        asset = directory / obj.get('path', '')
        evidence = obj.get('scientific_source', {})
        p = provenance.get(obj.get('path'), {})
        role = p.get('authorized_role')
        if not asset.is_file():
            errors.append(f'Picture asset missing: {name}')
            continue
        if not p.get('sha256') or digest(asset) != p.get('sha256'):
            errors.append(f'Picture hash differs: {name}')
        if role in ORIGINAL_ROLES:
            original = Path(p.get('source', ''))
            if not original.is_file() or digest(original) != p.get('original_sha256') or digest(asset) != p.get('original_sha256'):
                errors.append(f'Original source hash differs: {name}')
        elif p.get('source_type') not in {'asset-sheet-separated', 'imagegen'}:
            errors.append(f'Unrecognized image role/provenance: {name}')
        status = evidence.get('status')
        if not evidence.get('evidence') or status not in {'matched-paper', 'source-preserved', 'unmatched-preserved', 'illustration-preserved', 'illustration-separated'}:
            errors.append(f'Picture lacks verified source status/evidence: {name}')
        if status == 'matched-paper' and not all(evidence.get(k) for k in ['document', 'figure', 'media_member']):
            errors.append(f'Matched image lacks document/Figure/media evidence: {name}')
        if status == 'matched-paper':
            candidates = []
            for document in catalog.get('documents', []):
                filenames = {Path(document.get(key, '')).name for key in ['document', 'original_document']}
                if document.get('input_role') != 'papers' or Path(evidence.get('document', '')).name not in filenames:
                    continue
                candidates.extend(m for m in document.get('media', [])
                                  if m.get('member') == evidence.get('media_member') and m.get('sha256') == p.get('sha256'))
            if not candidates:
                errors.append(f'Matched paper media does not agree with source catalog: {name}')
        if status in {'matched-paper', 'source-preserved', 'unmatched-preserved'} and role not in SCIENCE_ROLES:
            errors.append(f'Scientific figure must be original, never generated: {name}')
        with Image.open(asset) as picture:
            iw, ih = picture.size
        crop = obj.get('crop_px', [0, 0, iw, ih])
        box = obj.get('box_px', [])
        if len(crop) != 4 or min(crop) < 0 or min(crop[2:]) <= 0 or crop[0]+crop[2] > iw+.1 or crop[1]+crop[3] > ih+.1:
            errors.append(f'Picture crop invalid: {name}')
        elif len(box) != 4 or min(box[2:]) <= 0:
            errors.append(f'Picture placement invalid: {name}')
        else:
            error = (box[2] / box[3]) / (crop[2] / crop[3]) - 1
            if abs(error) > .02:
                errors.append(f'Picture aspect distorted: {name} ({error:.4f})')
            if box[2] * box[3] >= .88 * source_area:
                errors.append(f'Near-full-page bitmap shortcut requires investigation: {name}')
        image_rows.append({'page': directory.name, 'object': name, 'status': status,
                           'document': evidence.get('document', ''), 'figure': evidence.get('figure', ''),
                           'panel': evidence.get('panel', ''), 'media_member': evidence.get('media_member', ''),
                           'crop_px': json.dumps(crop), 'sha256': p.get('sha256', ''),
                           'original_source': p.get('source', ''), 'evidence': evidence.get('evidence', '')})
    return {'page': directory.name, 'passed': not errors, 'errors': errors,
            'counts': {key: len(manifest.get(key, [])) for key in ['text_boxes', 'shapes', 'images']},
            'images': image_rows}


def audit_deck(run, pptx, review_file, qa_file):
    run, pptx = Path(run).resolve(), Path(pptx).resolve()
    errors, rows, page_reports = [], [], []
    deck = load(run / 'deck/deck_manifest.json')
    jobs = load(run / 'deck/page_jobs.json')
    for page in deck['pages']:
        directory = run / 'deck' / page['page_dir']
        report = audit_page(directory)
        page_reports.append(report)
        rows.extend(report['images'])
        errors.extend(report['errors'])
        page_review = directory / 'page_review.json'
        if not page_review.is_file() or load(page_review).get('visual_passed') is not True:
            errors.append(f'Page lacks real visual review: {directory.name}')
    if any(p.get('status') not in {'recorded', 'accepted'} for p in jobs['pages']):
        errors.append('Not every page is recorded')
    validation = subprocess.run([sys.executable, '-X', 'utf8', str(ROOT / 'runtime/validate_pptx.py'), str(pptx),
                                 '--deck-manifest', str(run / 'deck/deck_manifest.json')],
                                capture_output=True, text=True, encoding='utf-8')
    if validation.returncode:
        errors.append('Runtime deck validator failed: ' + validation.stdout[-2500:] + validation.stderr[-1000:])
    from pptx import Presentation
    presentation = Presentation(pptx)
    if len(presentation.slides) != len(deck['pages']):
        errors.append('Actual page count differs from source')
    expected_size = [round(deck['slide']['width'] * 914400), round(deck['slide']['height'] * 914400)]
    if any(abs(a-b) > 1 for a, b in zip([presentation.slide_width, presentation.slide_height], expected_size)):
        errors.append('Actual page dimensions differ from source')
    def walk(shapes):
        for shape in shapes:
            if shape.shape_type == 6:
                yield from walk(shape.shapes)
            else:
                yield shape
    for index, slide in enumerate(presentation.slides):
        expected = load(run / 'deck' / deck['pages'][index]['manifest'])
        named = {s.name: s for s in walk(slide.shapes)}
        for obj in expected.get('text_boxes', []):
            shape = named.get(obj['id'])
            if shape is None or not shape.has_text_frame or compact(shape.text) != compact(obj.get('text')):
                errors.append(f'Actual native text missing/different: {index+1}/{obj["id"]}')
        for obj in expected.get('shapes', []):
            shape = named.get(obj['id'])
            if shape is None or shape.shape_type in {13, 6}:
                errors.append(f'Actual native structure missing/wrong type: {index+1}/{obj["id"]}')
        for obj in expected.get('images', []):
            shape = named.get(obj['id'])
            if shape is None or not hasattr(shape, 'image'):
                errors.append(f'Actual independent picture missing: {index+1}/{obj["id"]}')
                continue
            raw_sha = __import__('hashlib').sha256(shape.image.blob).hexdigest()
            entry = next((p for p in expected['asset_provenance'] if p['path'] == obj['path']), {})
            if raw_sha != entry.get('sha256'):
                errors.append(f'Actual embedded picture hash differs: {index+1}/{obj["id"]}')
            iw, ih = shape.image.size
            visible = [iw * (1-shape.crop_left-shape.crop_right), ih * (1-shape.crop_top-shape.crop_bottom)]
            if min(visible) <= 0 or abs((shape.width/shape.height)/(visible[0]/visible[1])-1) > .02:
                errors.append(f'Actual picture aspect distorted: {index+1}/{obj["id"]}')
    final_hash = digest(pptx)
    review = load(review_file)
    if review.get('pptx_sha256') != final_hash or review.get('visual_passed') is not True or review.get('blocking_issues'):
        errors.append('Final visual review missing, failed, or stale')
    if sorted(review.get('reviewed_pages', [])) != list(range(1, len(deck['pages'])+1)):
        errors.append('Final visual review does not cover every page')
    qa = load(qa_file)
    if qa.get('input_sha256', '').lower() != final_hash.lower() or qa.get('passed') is not True:
        errors.append('PowerPoint QA failed, incomplete or stale')
    if any(qa.get(key) is not True for key in ['opened_read_only', 'source_unchanged', 'render_complete', 'test_edits_requested']):
        errors.append('PowerPoint QA lacks read-only opening, source invariance, rendering or actual edit tests')
    renders = qa.get('rendered_files', [])
    if qa.get('slide_count') != len(deck['pages']) or len(renders) != len(deck['pages']) or any(not Path(p).is_file() for p in renders):
        errors.append('PowerPoint rendered evidence missing or page count differs')
    for snapshot in load(run / 'source_catalog.json')['slide_inputs'] + load(run / 'source_catalog.json')['paper_inputs']:
        if digest(snapshot['snapshot']) != snapshot['sha256']:
            errors.append(f'Input snapshot changed: {snapshot["snapshot"]}')
    output = run / 'deliverables'
    output.mkdir(exist_ok=True)
    fields = ['page', 'object', 'status', 'document', 'figure', 'panel', 'media_member', 'crop_px', 'sha256', 'original_source', 'evidence']
    with (output / 'image_sources.csv').open('w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)
    for row in rows:
        if row['status'] != 'matched-paper':
            continue
        source = Path(row['original_source'])
        figure_name = re.sub(r'[^\w.-]+', '_', f'{Path(row["document"]).stem}_{row["figure"]}')
        dest = output / 'used_figures' / f'{figure_name}_{row["sha256"][:12]}{source.suffix}'
        dest.parent.mkdir(exist_ok=True)
        if dest.exists() and digest(dest) != digest(source):
            errors.append(f'Existing Figure output differs: {dest}')
        else:
            shutil.copyfile(source, dest)
    result = {'passed': not errors, 'pptx': str(pptx), 'pptx_sha256': final_hash,
              'errors': errors, 'pages': page_reports, 'exceptions': review.get('exceptions', []),
              'source_report': str(output / 'image_sources.csv')}
    write_json(output / 'delivery_audit.json', result)
    write_json(output / 'exceptions.json', {'blocking_issues': errors, 'exceptions': result['exceptions']})
    return result


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    page = sub.add_parser('page'); page.add_argument('--page', required=True)
    deck = sub.add_parser('deck')
    for name in ['run', 'pptx', 'review', 'powerpoint-report']:
        deck.add_argument('--'+name, required=True)
    args = parser.parse_args()
    if args.command == 'page':
        result = audit_page(args.page)
        write_json(Path(args.page) / 'scientific_audit.json', result)
    else:
        result = audit_deck(args.run, args.pptx, args.review, args.powerpoint_report)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
