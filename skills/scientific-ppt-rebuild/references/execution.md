# Execution and Ownership

`<skill>` is the directory containing SKILL.md; `<python>` is the discovered interpreter. Use absolute quoted paths for every tool call. No prior task path or secret is required. The scoped MIT runtime is adapted from ningzimu/image-to-editable-ppt-skill; runtime/LICENSE preserves its notice.

## Preflight

Run `<python> <skill>/scripts/sources.py doctor` and `<python> <skill>/runtime/main.py --help`. Required: Pillow, PyMuPDF, python-pptx, numpy, requests. The image CLI additionally uses openai; YAML is needed for skill validation. Missing dependencies may be installed only into a suitable task environment, not by changing unrelated projects. Do not install or start remote services speculatively.

`requirements.txt` lists runtime packages for a task environment if bundled dependencies are unavailable. Prefer the app's ready bundled interpreter. On Windows, use `<python> -X utf8` for direct script invocations and validation tools with Chinese paths/metadata; the scoped CLI also handles child-process encoding explicitly.

For maintenance, run `<python> -X utf8 -m unittest discover -s <skill>/tests -v`. These isolated synthetic tests check evidence extraction, source byte fidelity, native inventory coverage, aspect/provenance gates and overwrite protection. They supplement, not replace, actual slide reconstruction and PowerPoint QA.

For mixed/native PPTX the runtime can render using local Windows PowerPoint, falling back to an available LibreOffice converter. Pure full-slide image PPTX can be extracted without conversion. Final Windows QA still uses real PowerPoint. Runtime CLI capability does not imply that the agent has multi-agent tools; check those separately. Do not create user-visible new chats as a substitute for page subagents.

OCR: use an already configured provider if appropriate. Do not print tokens or copy credentials into the skill/run. Offline hints are measurements, not recognized words; transcription must be checked visually. If OCR is unavailable, tell the user when this materially affects accuracy. Local-only/confidential input must not be uploaded. No claim that a provider is free, risk-free, or has sufficient quota without current verification.

Only task-local necessary images may be sent to an authorized image/OCR backend. Scientific figure generation is prohibited even when imagegen is available. For complex illustrations, try unchanged embedded artwork first; otherwise isolate faithfully with an available authorized image tool, never a generative replacement masquerading as the original. If scientific content or extra text cannot be separated reliably, request the missing clean source.

## Prepare

```text
<python> <skill>/scripts/sources.py init --run <run> --slides <source.pptx> --papers <paper.docx> <paper.pdf>
<python> <skill>/runtime/main.py prepare <run>/snapshots/slides/001_source.pptx --job-dir <run>/deck --image-backend builtin-imagegen
```

Omit `--papers` for preserve-only mode; omit builtin selection when the tool is unavailable. Init requires a new directory and never overwrites an old run. Inputs are copied and checked for stable SHA256 before use. `source_catalog.json` retains original/snapshot paths, extracted media, block locations and native PPT object XML. Init extracts evidence, not correspondence guesses.

Parent creates `coordinator_context.md`: request, chosen mode, representation boundary, actual inputs, paper correspondences, unresolved issues, user reflow approvals, renderer and backend facts. It must be sufficient for fresh workers without conversation history. Parent may maintain catalogs/context but cannot write a worker's reconstruction files.

## Dispatch, Build, Record

```text
<python> <skill>/runtime/main.py run next <run>/deck
<python> <skill>/scripts/build_worker_prompt.py <run>/deck --page 1 --out <run>/deck/pages/page_001/worker-prompt.md
<python> <skill>/runtime/main.py run dispatch <run>/deck --page 1 --agent-id <real-worker-id> --prompt-file <absolute-worker-prompt>
```

Spawn a real agent before registering worker dispatch. Single-page only: use agent-id `main` and `--local` before building. Workers own one `pages/page_NNN` and may only read catalogs/shared sources. Supply exact page ID and input paths, not assumptions about page contents.

```text
<python> <skill>/runtime/build_pptx_from_manifest.py <page>/manifest.json --out <page>/page.pptx --preview <page>/preview.png
<python> <skill>/runtime/make_page_contact_sheet.py --help
<python> <skill>/runtime/validate_pptx.py <page>/page.pptx --manifest <page>/manifest.json --report <page>/validation.json
<python> <skill>/scripts/audit.py page --page <page>
<python> <skill>/runtime/main.py run record <run>/deck --page 1 --agent-id <real-worker-id>
```

Use actual CLI help if a command's flags differ. Record only after both validators pass and the page has been visually reviewed. Finalize rebuilds from manifests, rather than trusting merged page files:

```text
<python> <skill>/runtime/main.py run finalize <run>/deck
```

Prepare/state/dispatch/record/finalize mutations belong to CLI commands, not handwritten state JSON. `inventory.json`, `manifest.json`, visual review and correspondence evidence are agent-authored artifacts, not state files.

## Recovery

Identify the existing run and read input hashes, coordinator context, `run next`, page inventories and failure artifacts. Continue pending pages; do not rerun prepare against a used run. Refresh recorded pages only when actually edited and validated. Never use an age-based timeout to reset worker ownership. For failed or demonstrably lost leases use `run reset --page ... --agent-id ... --confirm-lost`, only after determining and fixing the root cause. Leave recoverable checkpoints when user quota/tool capability blocks work.
