# Acceptance and Delivery

## Page Checks

`audit.py page` checks coverage, typed native/image object references, full-slide image shortcuts, provenance/file hashes, source metadata, crop bounds, all picture aspect ratios (2% numerical tolerance, not permission to visibly stretch), nonempty native text, and explicit inventory review. Runtime validator checks generated PPTX against the manifest. Both gates must pass; neither can prove that an inventory omitted something visible. The worker must visually compare original and reconstruction at readable zoom.

## Assembled Deck

Use the real application, not only script previews:

```text
powershell -NoProfile -ExecutionPolicy Bypass -File <skill>/scripts/powerpoint_qa.ps1 -InputPptx <final.pptx> -OutputDir <new-qa-dir> -TestEdits
```

The script opens the output read-only, renders every slide, tests representative edits in a copy, saves/reopens that copy, and checks original hash unchanged. It never quits the user's PowerPoint application. If a relevant test is unavailable, inspect its reason; do not convert it to true. A group test is not applicable only when no output grouping exists. Inspect each slide's rendering and compare with source. Repair manifest sources, rebuild/re-record affected pages, finalize and rerun QA after changes. Do not patch only a final PPTX while leaving the authoritative manifests stale.

Write `<run>/final_review.json` with:

```json
{
  "pptx_sha256": "actual-reviewed-file-hash",
  "reviewed_pages": [1, 2],
  "visual_passed": true,
  "blocking_issues": [],
  "exceptions": []
}
```

The list must contain every page, including apparently simple cover and references. Review detailed text, superscripts/subscripts, equations, missing edges, layering, native callout separation, scientific exact identity and proportion. The hash ties review to the actual final bytes, not a previous version.

Run:

```text
<python> <skill>/scripts/audit.py deck --run <run> --pptx <final.pptx> --review <run>/final_review.json --powerpoint-report <qa-dir>/report.json
```

This rechecks every page, package geometry/media/object integrity, current hash/QA evidence and source snapshots, and writes `delivery_audit.json`, `image_sources.csv` plus `used_figures/`. Failure is not delivery acceptance; generated reports remain diagnostic. Only provide the accepted file as final. Never say perfect when critical elements are missing; name noncritical known differences honestly.

## Output Policy

Choose a new output filename next to the user's requested location; do not overwrite source PPT, papers, original scientific data/code, previous results or files changed since last validation. Default deliverables: PPTX, source CSV, concise exceptions summary; paper mode also used raw full Figures. The CSV distinguishes verified replacement, preserved source, unmatched preservation and separated illustration. Include actual paper Figure identifiers and panels, never infer them from media numbers. User-provided material remains user data in run directories; no data or credentials go into the installed skill or shared package.
