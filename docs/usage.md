# Usage guide

[README](../README.md) · [简体中文](../README.zh-CN.md) · [Privacy](privacy.md) · [Dependencies](dependencies.md)

Scientific PPT Rebuild repairs scientific slide drafts against their supplied papers, then reconstructs editable PowerPoint structure. Its main use is a paper-to-AI/image-slide-to-repair workflow: a draft may have attractive layout but distorted figures, unsupported labels, wrong units, or invented results. The agent checks the paper correspondence, replaces verified regions with actual paper media, and records supported corrections.

Generic image-to-editable conversion restores editability. This skill adds paper/Figure/panel matching, original-media replacement, retention of complete source Figures, and source/correction evidence with hashes and crop coordinates. Verification is scoped to the supplied material and the checks actually performed; it is not automatic or exhaustive factual validation.

Use the installed [`scientific-ppt-rebuild`](../skills/scientific-ppt-rebuild/SKILL.md) skill through an agent that can inspect images, run local tools, and coordinate page workers. The skill handles repair and reconstruction; the initial draft may come from your existing AI slide workflow or another source.

## Installation

The repository contains one installable skill at `skills/scientific-ppt-rebuild`. With Python 3.11+, run the installer from the repository root:

```sh
python install.py --install-deps
```

`--install-deps` creates a `.venv` inside the installed skill and installs its Python requirements there. It does not run system-wide pip. If your agent already has a suitable environment, install only the skill:

```sh
python install.py
```

These are alternative initial-install commands. The installer refuses to overwrite an existing installation by default.

| Option | Meaning |
| --- | --- |
| `--target` | The exact final skill directory, including its final folder name; not a parent directory into which another folder is appended |
| `--install-deps` | Install Python dependencies into the destination skill's own `.venv` |
| `--replace` | Explicitly replace an existing installation after creating a timestamped backup |

For example, use a new destination to keep another installation untouched:

```sh
python install.py --target ./local-skills/scientific-ppt-rebuild --install-deps
```

A custom location must also be discoverable by your agent. The installer cannot give an arbitrary directory that property. For a deliberate update at the default destination:

```sh
python install.py --replace --install-deps
```

On Windows, [`Install.ps1`](../Install.ps1) detects Python and invokes the installer with dependency installation enabled by default:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Install.ps1
```

Inspect `python install.py --help` for the current installer interface. Reopen Codex if it has not discovered the new skill. Folder installation is currently validated with the local `.codex/skills` layout; this repository does not ship a marketplace plugin.

### If dependency setup fails

The installer first places the reusable core at the final destination, then creates `.venv` **at that final path**. This avoids moving an environment whose scripts may contain absolute interpreter paths.

If environment creation or pip fails, the command returns a failure status while retaining the copied core and any timestamped previous-installation backup. It prints the exact environment-creation and dependency-install commands for that destination. Fix the reported network, package, or Python problem and run those printed repair commands. Replacing the core again is unnecessary for a dependency retry.

Dependency failure does not trigger automatic deletion or rollback of the destination. Such a rollback could discard files created or changed there after installation. Inspect the retained core and backup before choosing any manual restoration; do not treat a failed dependency step as permission to overwrite later work.

## Choose your inputs

| Supplied material | Workflow |
| --- | --- |
| Slide draft plus paper DOCX/PDF files — primary mode | Verify claim/experiment/Figure correspondence, replace matched draft graphics with actual paper media, and correct supported slide annotations |
| PPT/PPTX, a slide PDF, or ordered screenshots without papers — secondary mode | Restore editable structure and preserve slide figures as independent pictures; source preservation does not verify their scientific claims |

PPTX is preferable to legacy PPT when available because its embedded media and native object information can be inspected directly. Legacy PPT requires an available presentation renderer/converter. Label a PDF as “slides” or “paper” when its role could be unclear. Give screenshots an explicit page order.

Provide the highest-quality source you have. A crop cannot restore obscured pixels, and a higher DPI label cannot create missing detail. Source speaker notes can be retained from a presentation; screenshots cannot reveal notes they never contained.

Supply the original reference papers for the main repair workflow. The agent uses the versions you provide rather than finding a similar paper online. A mismatching draft may be wrong, or the paper may be a different version: inspect the experiment, result, caption, panel, axes, scale, and statistical annotations before choosing the source. Record any paper-supported correction and clarify differences that change meaning but cannot be resolved from the supplied evidence.

## Start a paper-aware repair

Attach the slide draft and papers, then give the agent this prompt:

```text
Use $scientific-ppt-rebuild to repair the attached scientific slide draft against its papers.

For every scientific result, inspect the paper's claim, experiment, Figure, complete caption,
panel labels, axes, units, scale, and statistical annotations. Verify the correspondence.
Replace matched draft graphics with actual supplied-paper media without redrawing their data.
Retain the complete source Figure and use native picture crops for displayed panels.
Correct slide labels, equations, units, and callouts only when the paper supports the correction.
Record the draft wording, supported replacement, paper/Figure/panel, and reasoning.

Rebuild text, equations, shapes, borders, arrows, and extra callouts as native objects.
Preserve page order, dimensions, colors, layout, layering, and available notes, except for
the documented source-supported repairs. Keep complex illustrations and logos separate.
Retain unmatched draft regions and mark them unverified; flag known or suspected invented content.

Use a new run directory and a new output filename. For multiple pages, use real page workers.
Check every page visually, run the structural and scientific audits, and perform the Windows
PowerPoint rendering and edit tests before claiming full acceptance.

Deliver the PPTX, image_sources.csv, used full Figures, a correction/exception summary,
and the actual source-verification and PowerPoint QA status.
```

Matching is a reviewed correspondence, not a nearest-image search. DOCX `imageN` members and PDF xref numbers do not identify a Figure. Read actual captions and relevant results, and visually compare panels and experiment details. If no reliable original is available, preserve the draft region as unverified. It cannot count as verified paper evidence. A hash of an invented graph proves only that the same invented bytes were retained.

### Secondary mode: slides without papers

When you only want to preserve the supplied deck and have no papers, use:

```text
Use $scientific-ppt-rebuild in slides-only preservation mode.
Restore native text, equations, shapes, and layout; keep figure regions as independent pictures.
Preserve the source layout and available notes, and disclose unclear content.
Mark source-unverified figures and suspected invented content. Do not describe preservation
as paper verification. Deliver a new PPTX, source report, exceptions, and PowerPoint QA status.
```

State any material constraint up front: approved processing services, fonts, output location, or whether a local layout adjustment is allowed. If you require confidential processing, choose an approved agent environment and explicitly prohibit external OCR/image services. See [privacy](privacy.md) for the distinction between local utilities and agent/provider processing.

## Understand the object boundary

The editable portion includes slide titles, body text, labels outside scientific figures, color blocks, numbers, arrows, borders, connectors, and callouts. Equations use native text, text runs such as superscripts/subscripts, and shapes where needed. Complex notation needs source-by-source review; native components do not promise a semantic equation editor for every expression.

Verified scientific figures remain independent unchanged paper-source pictures. Their internal axes, labels, legends, scale bars, data points, and statistical marks stay together; they do not all become editable graph marks. Independent panels may use separate native crops of the same full figure. Logos and complex illustrations are also independent semantic pictures. Unmatched regions remain explicitly unverified, even when their bytes are faithfully preserved.

Correct supported slide text around the figure as native objects, while leaving the paper figure's scientific content unchanged. Replacing a wrong draft curve with the actual paper Figure is an evidence repair; redrawing a curve to make it appear consistent is not. Do not invent missing data, infer a dataset from a screenshot, or alter an original figure to fit a draft's unsupported claim.

Extra annotations added on the slide are separate native objects when the clean figure is available. If the sole source has a callout or circle baked over data, the agent must seek an unobscured source or record the unresolved exception. It must not invent the covered pixels or cover an old baked label with a duplicate and call it removed.

A full-slide bitmap with hidden or overlaid text does not satisfy the representation contract. Nor does a bitmap tile that combines a scientific figure with surrounding slide layout.

## What happens during a run

1. **Preflight.** Check Python packages, input readability, rendering tools, and actual agent capabilities. Multi-page tasks require real independent workers; a single page may run locally.
2. **Snapshot and inspect.** Copy inputs into a new run directory, check hashes, extract media and document evidence, and read the draft and supplied papers. Extraction does not establish Figure identity.
3. **Match and document repairs.** Map each scientific result to paper, experiment, Figure, caption, and panel. Record source-supported corrections to text, equations, units, and callouts. Leave unresolved or invented content unverified rather than certifying it through preservation.
4. **Inventory and reconstruct.** Record visible objects per page. Page workers replace verified regions with unchanged source media, apply supported native-text corrections, and rebuild native structure. The coordinator owns shared context and paper matching.
5. **Validate and review.** Each page passes runtime and scientific audits. Compare scientific content with the paper and layout with the draft, allowing the documented repairs. Assemble from accepted manifests, render every page in Windows PowerPoint, and test representative edits on a scratch copy. Tie review to the final file hash. Object counts and hashes cannot replace this review.
6. **Deliver.** Run the deck audit and provide the PPTX with sources, corrections, exceptions, and actual verification results. Known draft hallucinations remain evidence-verification blockers until supported replacement resolves them.

The operational commands, ownership rules, and artifact contracts are in [execution.md](../skills/scientific-ppt-rebuild/references/execution.md), [page-contract.md](../skills/scientific-ppt-rebuild/references/page-contract.md), and [verification.md](../skills/scientific-ppt-rebuild/references/verification.md). The bundled runtime's generic schema has broader options; the scientific skill's representation rules take precedence.

## Read the results

| Artifact | Purpose |
| --- | --- |
| Final `.pptx` | Repaired, editable slide structure with independent source pictures and disclosed unverified regions |
| `image_sources.csv` | Paper/Figure/panel identity, preservation/replacement status, hashes, and crop provenance |
| Correction and exceptions summary | Original versus supported text/equation/units/callout changes, reasons, unresolved matches or claims, and visual limits |
| `used_figures/` in paper mode | Actually used paper figures; retain full figures for cropped panels |
| Run directory | Snapshots, source catalog, coordinator context, inventories, manifests, previews, validation and QA evidence |

`matched-paper` means a correspondence was reviewed and verified against the supplied paper. `source-preserved` means the slide's own picture was retained; it does not establish its paper origin or scientific correctness. `unmatched-preserved` means the draft region was retained because reliable replacement evidence was missing; it remains unverified. A PDF page render must be identified as `pdf-render`, with page and resolution, rather than raw embedded raster media. Hashes establish file identity, not figure correspondence, claim validity, or absence of AI hallucination.

The [controlled synthetic example](../examples/synthetic-signal/README.md) illustrates this distinction: `draft-demo.pptx` intentionally has wrong curves and an equation; the repaired `editable-demo.pptx` uses the exact `source-figure.png` from the synthetic paper's Figure 1 and corrects native equation text. `figure-mapping.csv` records the changes. The draft was constructed programmatically, not generated by GPT, and the example is not a blind matching or factual-verification benchmark. The before/after difference is intentional. See [what was actually verified](verification.md).

Full input papers are not part of the default delivery. Run records and exported sources may still contain confidential material and local paths. Inspect them before sharing.

## Resume or diagnose

Keep the existing run directory after a tool failure or interruption. Ask the agent to inspect the source catalog, coordinator context, page inventories, and `runtime/main.py run next` output, then continue pending work. An active worker is not lost just because it has been silent; reset only with actual failure, cancellation, or lost-worker evidence.

From a checkout, these diagnostic commands expose the local environment and actual CLI surface. Run them with your selected task Python; replace `python` with its interpreter path if necessary:

```sh
python -X utf8 skills/scientific-ppt-rebuild/scripts/sources.py doctor
python -X utf8 skills/scientific-ppt-rebuild/runtime/main.py --help
```

| Situation | Next action |
| --- | --- |
| PowerPoint is unavailable | Use available preliminary checks, disclose missing final QA, and complete the PowerPoint review in a suitable Windows environment |
| Multi-page workers are unavailable | Report the capability blocker and retain checkpoints; do not substitute flattened pages |
| Text is unreadable | Inspect better sources or request clarification; do not invent wording |
| A paper figure cannot be matched | Preserve the draft region, mark it unverified, and record the reason |
| A draft contains a known or suspected invented result | Seek a reliable supplied-paper source; retain unresolved regions only with explicit unverified status and do not count them as verified evidence |
| The output changed after review | Rebuild or revalidate the changed version and repeat the affected QA before acceptance |

For a bug report, reproduce the issue with newly created synthetic mathematical content and follow [CONTRIBUTING.md](../CONTRIBUTING.md). Do not upload a real run directory.
