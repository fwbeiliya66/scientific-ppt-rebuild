# Verification scope

The included example is a controlled paper-aware repair fixture with known
positions and formula-generated values. The draft curves and formulas are
deliberately wrong; the synthetic source paper and its original Figure 1 define
the repair. No GPT/model call produced the draft, and this is not a blind
reconstruction or factual-verification benchmark.

Both native demonstration decks were opened in Windows desktop PowerPoint. The
following operations were performed on disposable copies, with changes checked
and restored. Passing an edit test on the deliberately wrong draft does not make
its scientific content correct:

| Check | Observed result |
| --- | --- |
| Open read-only and render the slide | Passed |
| Modify native text | Passed |
| Modify a native shape fill | Passed |
| Move the independent figure picture | Passed |
| Replace a picture, then restore the original | Passed |
| Ungroup a native multi-member group and save the result | Passed |
| Save, close, reopen and verify the test changes | Passed |
| Preserve the source PPTX hash | Passed |

The example contains 17 nonempty native text objects, eight native shapes and one
independent PNG. The PNG's bytes match `source-figure.png`; its data and internal
labels are not redrawn by the reconstruction representation.

The draft embeds `draft-figure.png`; the repaired deck embeds the unchanged
`source-figure.png`. The source PDF's Figure 1 pixels match that source PNG, and
the PDF's definitions support both repaired native formulas. The three rows in
`figure-mapping.csv` document the complete-panel replacement and the two formula
corrections using relative source paths and the full original figure hash.

CI runs unit tests, synthetic generation, public-content checks and archive
building. Hosted CI does **not** run Microsoft PowerPoint or establish the visual
accuracy of unseen documents. A successful CI run is not full acceptance of a
user's slide reconstruction. That requires the actual per-page review and
PowerPoint checks specified by the skill.

The public comparison uses actual PowerPoint exports. The flattened input is
made from the incorrect draft export. The before and after intentionally differ
in the source figure, supported formulas and verification labeling. Colored
outlines in the comparison explain object boundaries; they are not simulated
application controls. This demonstrates the representation and source-repair
contract, not automatic matching accuracy, processing speed, or success on an
unseen research paper.
