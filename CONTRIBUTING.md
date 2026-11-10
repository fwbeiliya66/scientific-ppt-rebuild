# Contributing

Contributions should improve faithful, reviewable reconstruction: native editable slide structure, independent unchanged scientific pictures, explicit source evidence, and honest verification results.

## Use synthetic material

Public examples, tests, screenshots, and reports must use **newly created synthetic mathematical content**. Do not copy slides, manuscripts, data, figures, names, organizational identifiers, credentials, or local paths from a real task or prior work. Prefer a new minimal fixture to a redacted research file; notes, embedded media, and document properties can retain hidden content.

Read [privacy and sharing](docs/privacy.md) before attaching files. Never upload a complete run directory or authentication/configuration file. If a problem requires private content, describe the failure without supplying that content and try to recreate it with a simple generated equation, signal, or geometric figure.

## Report a problem

Use the [bug report form](https://github.com/fwbeiliya66/scientific-ppt-rebuild/issues/new?template=bug_report.yml) and include:

- The release version or commit and the relevant operating system, Python, PowerPoint, and agent capabilities.
- The smallest synthetic reproduction and the exact step that fails.
- Expected versus observed behavior, including whether the problem concerns structure, scientific integrity, rendering, or provenance.
- Relevant sanitized error excerpts and the actual QA outcome. Replace local paths with neutral synthetic names.

For a feature request, explain the concrete reconstruction problem and the desired behavior. Keep requests within the representation contract: scientific data is preserved, and uncertainty is disclosed.

## Make a focused change

The installable skill lives in `skills/scientific-ppt-rebuild`. Its [`SKILL.md`](skills/scientific-ppt-rebuild/SKILL.md) defines the scientific representation contract. The [references](skills/scientific-ppt-rebuild/references) document execution, source matching, page ownership, and acceptance.

Keep changes small and directly tied to the problem. Preserve source/output protection and active-worker ownership rules. Reconstruct pages from authoritative manifests rather than patching only a final output file. Keep upstream attribution and notices with adapted code. Update English and Chinese entry points together when their user-facing claims change.

For code changes, add or adjust a meaningful synthetic regression test for the changed behavior. Tests should check a real failure or contract; do not replace visual review with object counts or a boolean written by the builder itself.

## Verify the change

From the repository root, using a Python environment with the skill dependencies:

```sh
python -X utf8 -m unittest discover -s skills/scientific-ppt-rebuild/tests -v
python scripts/check_release.py
```

Run the applicable tests for the change. The release check should also pass for documentation and packaging changes. If a change affects construction, rendering, cropping, notes, or editability, use synthetic slides for actual PowerPoint rendering and edit tests, and visually inspect every affected page. Record what was checked and any unavailable tools.

The [synthetic signal example](examples/synthetic-signal/README.md) is a controlled fixture for inspecting native objects and source-picture identity. It is not an accuracy benchmark. Passing unit tests or generating a valid ZIP package does not establish visual fidelity or full PowerPoint acceptance.

To build the distributable after checks pass:

```sh
python scripts/build_release.py
```

Inspect the archive's contents before sharing. Include reusable source and deliberate synthetic examples only; exclude task data, local environments, credentials, and incidental machine artifacts.

## Submit a pull request

Lead with the concrete problem and resulting behavior. Include a minimal trigger or before/after example when useful, the checks actually run, and any known limitation. Screenshots and attachments must follow the synthetic-content rule above. Do not claim a visual or application-level check passed unless it was performed on the current output.
