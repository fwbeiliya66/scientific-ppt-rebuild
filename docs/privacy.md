# Privacy and sharing

[README](../README.md) · [Usage](usage.md) · [Dependencies](dependencies.md)

Scientific PPT Rebuild creates working copies of your supplied files and records the evidence needed to reconstruct and review a deck. Treat the run directory as having the same sensitivity as its inputs. Keeping a scientific figure unchanged is a statement about content integrity, not a guarantee that every tool processing it runs locally.

## Where content is processed

| Component | Data flow |
| --- | --- |
| Local snapshot, extraction, build, and audit scripts | Read local inputs and write run artifacts on the machine executing them |
| PowerPoint or LibreOffice rendering | Opens files through the installed application and creates local render/QA output |
| The agent and its image-viewing tools | May send supplied material, extracted text, or page images to the agent provider, according to that environment's configuration and terms |
| Optional cloud OCR | Sends the selected input to its configured service; the bundled experimental PaddleOCR helper uploads its input image or PDF when explicitly used |
| Optional image services | May send selected images and prompts to the chosen backend for authorized non-scientific illustration separation; scientific-data redrawing is prohibited |
| Dependency installation | Downloads packages through pip and the user's configured package indexes; it is separate from slide processing |

An online agent can process a page even when no separate OCR service is used. Before supplying confidential inputs, choose an environment approved for those inputs and specify which external services, if any, are allowed. A request to use only local extraction/building does not by itself change the agent provider's processing or retention policies.

The runtime includes optional image-provider integrations that can use configured API credentials or existing Codex authentication. Their availability is not permission to send content. Keep tokens in the environment or an appropriate external credential configuration, and authorize only the necessary task inputs. Do not paste credentials into prompts, manifests, issue reports, or the installed skill.

## What a run retains

Run artifacts can include:

- Full snapshots of the supplied slide files and papers.
- Extracted embedded media, rendered pages, and text/document evidence.
- Original and snapshot paths, filenames, SHA256 hashes, image coordinates, and crop records.
- Page inventories, reconstruction manifests, worker context, previews, and review notes.
- Source speaker notes, PowerPoint QA copies, and audit reports.

`image_sources.csv` and `used_figures/` are useful deliverables, but can disclose figure content, document names, and local paths. A PPTX can also contain notes, document properties, and images outside the currently visible crop. A cropped image's hidden pixels remain in the package when the full source figure is embedded.

The workflow keeps data in a run directory separate from the installed skill. Do not move run artifacts into the reusable skill folder or publish that folder with task data added to it. Keep the run while you need resumability and verification evidence; remove it through your normal data-retention process when that need ends.

## Share only deliberate outputs

Before sharing, inspect the actual PPTX and any accompanying CSV, figures, screenshots, logs, or archives. Share the selected deliverables, not an entire run directory. Do not assume a hidden slide, a cropped region, a removed visible label, or a shortened filename makes an artifact safe to publish.

Do not include full papers in a delivery unless requested. Possessing an input does not establish permission to redistribute it. Source hashes support byte identity and provenance; they do not grant publishing rights or prove a scientific correspondence.

## Public contributions and issue reports

This public repository uses **newly created synthetic mathematical examples only**. Do not contribute real research slides, papers, data, images, organizational material, participant information, credentials, personal names, or local paths from an actual task, including material from prior work.

Build a minimal synthetic reproduction instead of redacting a real presentation. New files are easier to inspect for hidden media, notes, metadata, and identifiers. Use neutral filenames and paths such as `synthetic-input.pptx` and `demo-run` in reports.

The [bug report form](../.github/ISSUE_TEMPLATE/bug_report.yml) asks for environment details, steps, expected behavior, and sanitized diagnostics. Include only the relevant error excerpt. Do not attach authentication files, environment dumps, manuscripts, or complete run archives. If you cannot reproduce a problem without private content, describe the behavior without uploading that content.
