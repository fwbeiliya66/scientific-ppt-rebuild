# Figure Integrity and Matching

## Without Papers

Extract original PPT media bytes first, recording relationship, object name, placement, native crop and raw hash. For a flattened page, identify the entire scientific region including axes/legend/scale bars and crop from the highest-resolution available source. Native PPT crop preserves raw encoding and is preferred. A crop cannot recover covered pixels or increase real resolution.

Chinese callouts, slide arrows and red circles added to the figure are outside the scientific exception. Find an unobscured duplicate in the deck or supplied materials before separating. If the sole source is obscured, do not invent the covered data, inpaint it, or add hidden/duplicate text. Ask for a clean source or explicit local exception and record it as unresolved; the default strict acceptance remains failed for a missing required native object.

## With Papers

For an AI-generated draft, first distinguish faithful-image replacement from paper-guided correction. An invented draft curve may have no original image to identify. In that case use the intended claim, species/material, treatment, time point, endpoint and caption to establish an unambiguous supporting Figure; record a claim-based correction rather than claiming the invented graphic was the paper's image. If the source does not support the claim, record it as unresolved. A nearest-looking panel is not evidence.

1. Inspect the raw media and document evidence from source_catalog.json. DOCX `imageN` numbering is unrelated to Figure numbering; TOC graphics, equations and drawing objects offset it. Captions may precede images, follow them, or be collected elsewhere. Extractor caption candidates are NOT validated assignments.
2. Read complete captions and relevant article sections. View actual Figure images and the PPT region. Match distinct panel layout, labels, axes, series, scale bars and specimen features. A similar micrograph is not the same microscope field.
3. A verified replacement may reflect the supplied manuscript version rather than an old screenshot. If data, material, experiment, scale, panel lettering or statistical annotation differ, disclose that and seek clarification when it changes the scientific meaning. Do not silently edit the paper figure to resemble the screenshot.
4. Record exact document, Figure, subpanel and crop coordinates for each region. Reuse the same full raw Figure with separate native crops when several panels are shown separately. Verify crop bounds and proportional placement.
5. If no reliable match exists, preserve the PPT region and state `unmatched-preserved` with the reason. Never use the nearest-looking image. This is an allowed scientific-source exception, not permission for other missing content.

`unmatched-preserved` records an unresolved source identity, not scientific verification. Known or suspected invented data must remain labeled unverified and must not support an accepted scientific conclusion. Source-grounded corrections include the necessary surrounding units, labels and numerical callouts; record their original wording and supporting paper location. Do not invent underlying values or refit a curve.

PDF extraction: recover embedded raster bytes when meaningful; soft masks and composite/vector Figures may require actual page rendering or a faithful vector export. Page render is labeled `pdf-render`, with page and resolution, never described as an extracted raw image. Obtain higher-quality source if necessary. PDF xref numbers and caption proximity are not Figure identity.

For composite/vector PDF Figures, the parent can run `sources.py render-pdf --run <run> --paper <catalog-PDF-path> --page <1-based-page> --dpi 300`. It registers the actual render, PDF hash, page and resolution in the catalog. Workers use native crop on that page render, with the exact `pdf:page:...:render:...` member and a verified Figure assignment. Do not describe this PNG as raw embedded paper pixels. Parent owns catalog updates; workers must not edit the shared catalog themselves.

## Per-Image Evidence

Each manifest image has matching provenance and `scientific_source` metadata:

```json
{
  "id": "research-left-a",
  "scientific_source": {
    "status": "matched-paper",
    "document": "paper.docx",
    "figure": "Figure 3",
    "panel": "a",
    "media_member": "word/media/image4.png",
    "evidence": "Panel layout, axis ranges and named series visually verified."
  }
}
```

Other statuses: `source-preserved`, `unmatched-preserved`. Neither requires a paper/figure field; both require a reason/evidence and the exact original asset source. Allowed image roles: `word_original` (verified paper media, also applicable to PDF raster), `source_scientific`, `preserve_missing_research_region`, `original_logo`, `complex_original`; separated complex artwork uses real asset-sheet/imagegen provenance instead. Picture crop/scale is stored on the image object, not rasterized into lower-resolution replacement media.

Use `scientific_source` for all independent images, with `status: illustration-preserved` or `illustration-separated` for non-scientific art; leave Figure/panel blank. Keep scientific and illustration provenance distinct. Never fake imagegen records for supplied media or label page-layout tiles as science.
