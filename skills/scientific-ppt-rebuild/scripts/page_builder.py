"""Page-local manifest builder for native objects and unchanged scientific media."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from PIL import Image
from sources import contain_box, digest, write_json

ROOT = Path(__file__).resolve().parents[1]


class Page:
    def __init__(self, directory):
        self.directory = Path(directory).resolve()
        request = json.loads((self.directory / 'page_request.json').read_text(encoding='utf-8'))
        self.manifest = {'schema_version': 1,
                         'source': {'path': 'source.png', 'width_px': request['source_size_px']['width'],
                                    'height_px': request['source_size_px']['height']},
                         'slide': {**request['slide'], 'background': '#FFFFFF'},
                         'content_box': request['content_box'], 'preview_scale': 120,
                         'images': [], 'shapes': [], 'text_boxes': [], 'text_inventory': [],
                         'visual_inventory': [], 'asset_provenance': [],
                         'background_strategy': {'mode': 'native-or-script', 'note': 'Native layout; no panel tiles.'},
                         'quality_checks': {k: False for k in ['font_size_calibrated', 'visual_inventory_matched',
                                                             'background_strategy_checked', 'shape_corner_geometry_checked']},
                         'user_authorized_asset_policy': {'word_originals': True, 'original_logo': True,
                                                          'preserve_missing_research_region': True,
                                                          'source_scientific': True, 'complex_original': True},
                         'notes': ''}
        notes_file = self.directory.parents[1] / 'notes_manifest.json'
        if notes_file.is_file():
            notes = json.loads(notes_file.read_text(encoding='utf-8')).get('notes', [])
            self.manifest['notes'] = next((n.get('text', '') for n in notes
                                           if n.get('page_index') == request['page_index']), '')
        (self.directory / 'assets').mkdir(exist_ok=True)

    def text(self, name, content, box, size, bold=False, color='#12377D', align='left', font='Microsoft YaHei', **extra):
        item = {'id': name, 'text': content, 'box_px': list(box), 'font_size': size,
                'font_size_source': 'measured', 'font': font, 'bold': bold, 'color': color,
                'align': align, 'valign': 'middle', 'fit_text': True, 'text_fit_safety': .98,
                'z_index': 300, **extra}
        self.manifest['text_boxes'].append(item)
        self.manifest['text_inventory'].append({'id': name, 'text': content, 'decision': 'native-text'})
        return item

    def shape(self, name, box, fill='none', stroke='none', kind='rect', **extra):
        item = {'id': name, 'box_px': list(box), 'type': kind, 'fill': fill, 'stroke': stroke,
                'stroke_width': .7, 'z_index': 100, **extra}
        if kind == 'roundRect':
            item.setdefault('source_corner_radius_px', 8)
        self.manifest['shapes'].append(item)
        self.manifest['visual_inventory'].append({'id': name, 'decision': 'native structural', 'type': kind})
        return item

    def line(self, name, points, stroke='#12377D', **extra):
        x1, y1, x2, y2 = points
        return self.shape(name, [min(x1, x2), min(y1, y2), abs(x2-x1), abs(y2-y1)],
                          stroke=stroke, kind='line', points_px=list(points), **extra)

    def image(self, name, filename, box, crop=None, role='source_scientific', scientific_source=None, **extra):
        if not scientific_source:
            raise ValueError('Every image requires explicit source status and evidence')
        source = Path(filename).expanduser().resolve(strict=True)
        sha = digest(source)
        target = self.directory / 'assets' / f'{sha[:16]}_{source.name}'
        if source != target:
            if target.exists() and digest(target) != sha:
                raise ValueError(f'Asset collision: {target}')
            shutil.copyfile(source, target)
        with Image.open(target) as image:
            iw, ih = image.size
        visible = list(crop) if crop is not None else [0, 0, iw, ih]
        if min(visible) < 0 or visible[0]+visible[2] > iw+.1 or visible[1]+visible[3] > ih+.1:
            raise ValueError('Crop outside original image')
        path = target.relative_to(self.directory).as_posix()
        item = {'id': name, 'path': path, 'box_px': contain_box(box, visible), 'alt': name,
                'crop_px': visible, 'image_size_px': [iw, ih], 'z_index': 200,
                'scientific_source': dict(scientific_source), **extra}
        self.manifest['images'].append(item)
        self.manifest['asset_provenance'].append({'path': path, 'source': str(source),
                                                  'source_type': 'user-provided', 'authorized_role': role,
                                                  'sha256': sha, 'original_sha256': sha,
                                                  'provenance_note': 'Unchanged user-provided semantic image.'})
        self.manifest['visual_inventory'].append({'id': name, 'path': path,
                                                 'decision': 'unchanged user-provided scientific/semantic image',
                                                 'authorized_role': role})
        return item

    def save(self):
        write_json(self.directory / 'manifest.json', self.manifest)
        jobs = self.directory / 'imagegen-jobs.json'
        if not jobs.exists():
            write_json(jobs, {'schema_version': 1, 'jobs': []})
        result = {'page_manifest': 'manifest.json', 'imagegen_jobs': 'imagegen-jobs.json',
                  'page_pptx': 'page.pptx', 'preview': 'preview.png',
                  'contact_sheet': 'split_assets_contact.png', 'validation': 'validation.json',
                  'page_result': 'page_result.json'}
        write_json(self.directory / 'page_result.json', result)
