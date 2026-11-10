# Controlled paper-aware repair demo

**SYNTHETIC DEMO. Restore the original paper figure, correct the draft formulas from the source, and keep the slide structure editable. All content is freshly generated mathematics, not measured data or scientific evidence.**

The unverified draft deliberately contains a wrong plot and wrong native formula values. The repaired slide uses the original Figure 1 supplied in `synthetic-paper.pdf` and the correct definitions from that document. Its plot is one independent PNG, embedded byte-for-byte from `source-figure.png`.

This is a controlled illustration of errors that can occur when drafting slides from papers. **No GPT or other model call occurred; the draft is not actual GPT output.** The generator constructs known incorrect and correct states with known object positions. It does not perform blind figure matching, run an automatic reconstruction, or establish benchmark accuracy.

There are no real authors, institutions, publications, DOI, participants, or private project materials. The synthetic paper's figure, caption, axes, and formula definitions supply the complete source for this example.

## What changes

| Draft object | Deliberate error | Source-supported repair |
| --- | --- | --- |
| Left plot panel | Wrong curve shapes from the draft formulas below. | Replace the whole panel with the original `source-figure.png`, identified as page 1, Figure 1 of `synthetic-paper.pdf`. |
| `equation-A` | `y_A(x) = 0.95 exp(-0.02x)` | Correct native text to `y_A(x) = exp(-0.08x)`, supported by Section 1. |
| `equation-B` | `y_B(x) = 0.4 exp(-0.10x)` | Correct native text to `y_B(x) = 0.7 exp(-0.04x)`, supported by Section 1. |

`figure-mapping.csv` records the three mappings, relative file paths, page and figure number, the full SHA-256 of the original figure, caption/axes/formula evidence, and repair actions. These are explicit known-source mappings for this fixture, not the output of an evaluated matching algorithm.

The original plot was generated first and embedded as Figure 1 in the synthetic paper. The repaired deck reuses that same original PNG; it does not redraw or reinterpret the paper figure. Native text, simple formula text, shapes, arrows, and the header group remain editable. Labels inside the original scientific plot remain part of that preserved picture.

## Contents

| File | Purpose |
| --- | --- |
| `generate.py` | Rebuilds both known states and the source audit without a network or model call. |
| `data.csv` | Correct source values: 41 deterministic samples and a `SYNTHETIC DEMO` data-kind label. |
| `synthetic-paper.pdf` | Authoritative one-page synthetic source with Figure 1, its caption, axes, and definitions. |
| `source-figure.png` | Original 1600 x 1000 Figure 1; unchanged bytes are embedded in the repaired deck. |
| `draft-figure.png` | Deliberately wrong curves labeled `INTENTIONALLY INCORRECT DEMO`. |
| `draft-demo.pptx` | Known incorrect native fixture, visibly marked `UNVERIFIED DRAFT`. |
| `editable-demo.pptx` | Correct repair target with the original figure and source-supported native formulas. |
| `figure-mapping.csv` | Relative-path audit connecting draft errors to the original source and repaired objects. |
| `flattened-input.pptx` | Image-based draft input, produced separately from the draft's actual PowerPoint render. |
| `before.png`, `after.png` | Separate desktop PowerPoint renders of the unverified draft and repaired deck. |
| `before-after.png` | Side-by-side comparison assembled from those actual PowerPoint renders. |

PowerPoint render/comparison files are generated separately and must be regenerated when either deck changes. `generate.py` does not write or simulate screenshots, the flattened input, or desktop PowerPoint QA results. See [verification scope](../../docs/verification.md) for the recorded application checks.

## Correct source and deliberate draft values

The source defines the following signals. `data.csv` samples them for integer `x` from 0 through 40:

```text
y_A(x) = exp(-0.08 x)
y_B(x) = 0.7 exp(-0.04 x)
```

The draft intentionally uses these unsupported definitions instead:

```text
WRONG: y_A(x) = 0.95 exp(-0.02 x)
WRONG: y_B(x) = 0.4 exp(-0.10 x)
```

The source CSV rounds to 12 decimal places. Both plots evaluate their respective formulas more densely to draw curves. Axes use arbitrary units; Curve A is solid teal and Curve B is dashed graphite. There are no random draws, statistical estimates, error bars, or empirical claims. The draft values do not replace the authoritative source data.

## Reproduce

From the repository root, using Python with Pillow, python-pptx, and PyMuPDF already available:

```sh
python -B examples/synthetic-signal/generate.py
```

The script resolves all inputs and outputs relative to its own location and uses the repository's `write_pptx` manifest builder. It writes seven artifacts: the source CSV, two PNGs, synthetic PDF, two native decks, and mapping CSV. No network, model API, Office automation, or OCR is required. ZIP timestamps are fixed and PDF dates/document IDs are omitted; byte identity across different dependency versions is not promised.

In both native decks, the five-member `slide-header` group contains the two kicker labels, title, subtitle, and header rule. It can be ungrouped in PowerPoint. The two formulas use native editable text runs with subscripts, rather than Office Math objects. The plot can be moved or replaced as one picture.

## Checks and limits

The generator checks the correct sample values, source and deliberately wrong native formulas, explicit draft status, header group, exactly one picture per deck, byte-identical media embedding, absence of picture cropping, full original-figure hash in the audit, and relative mapping paths. The draft and repaired images must differ.

These checks do not establish PowerPoint visual fidelity, general reconstruction accuracy, automatic source matching, or scientific validity. Desktop PowerPoint rendering, editing, ungrouping, and save/reopen checks are separate verification steps. The before/after comparison illustrates a known-source repair, not an independent evaluation of GPT or any other model.
