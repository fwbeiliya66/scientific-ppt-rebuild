# Page Inventory and Construction

Read runtime-schema.md for generic manifest syntax. Scientific representation and source exceptions are defined by SKILL.md and figure-matching.md, not by upstream generic no-crop/bitmap-formula rules.

Before building, each worker inventories every visible semantic object in `inventory.json`:

```json
{
  "page_id": "page_001",
  "reviewed_against_source": false,
  "items": [
    {"id": "title", "kind": "native_text", "text": "Results", "source_box_px": [30, 20, 500, 70], "object_ids": ["page-heading"]},
    {"id": "graph", "kind": "scientific_image", "source_box_px": [80, 160, 520, 390], "object_ids": ["research-left-a"]},
    {"id": "border", "kind": "native_shape", "source_box_px": [70, 140, 540, 420], "object_ids": ["research-border"]}
  ]
}
```

Kinds: `native_text`, `native_shape`, `scientific_image`, `complex_image`, `logo_image`. Include formulas as native_text plus fraction/radical/structure native_shape pieces as needed. Every item needs real object IDs; combine primitives where useful, not whole sections into bitmap tiles. Shape repetition is allowed but justify it visually. Existing native item XML in the catalog provides original content/formatting evidence, not a requirement to reuse unsafe relationships blindly.

Use `Page` from `<skill>/scripts/page_builder.py` in a page-local script:

```python
from page_builder import Page
p = Page(page_directory)
p.text('page-heading', 'Results', [30, 20, 500, 70], 24, bold=True)
p.shape('research-border', [70, 140, 540, 420], kind='roundRect', stroke='#12377D')
p.image('research-left-a', absolute_raw_media, [80, 160, 520, 390],
        crop=[0, 0, 1200, 900], role='source_scientific',
        scientific_source={'status': 'source-preserved', 'evidence': 'Unchanged source plot region.'})
p.save()
```

Pass absolute asset paths from the run catalog, not old username/task paths. Helper preserves raw bytes, fits native crops proportionally, hashes actual original and copied bytes, and carries original notes. Default font is only a starting point: measure source fonts/size, use available matching fonts and check actual PowerPoint render. Supports `runs` for native superscript/subscript, `group_id`, gradients, custom paths, rotation and arrows as supported by bundled runtime. Inspect runtime functions/schema for exact supported fields rather than inventing them.

Set `quality_checks` true only after actual inspection. Set `inventory.reviewed_against_source` true only after every item was verified. Write `page_review.json` with source/preview paths, issues found/fixed, unresolved blocking issues, and actual review conclusions. The final slide's drawn objects must match the inventory semantically, not merely in object counts.

Required page artifacts: inventory.json, manifest.json, page.pptx, preview.png, split_assets_contact.png, imagegen-jobs.json (empty jobs valid for unchanged originals), validation.json, page_result.json, page_review.json, scientific_audit.json. The helper writes manifest/result skeletons, not a visual pass. Run build and both validators before record. No original user file is a write target.
