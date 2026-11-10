# Dependencies and platform support

[README](../README.md) · [Usage](usage.md) · [Privacy](privacy.md)

Use **Python 3.11+**. The installer can create an isolated `.venv` within the installed skill with `python install.py --install-deps`. Existing task environments may also be used when they contain the required packages. The repository does not supply PowerPoint, a Python interpreter, agent capabilities, service credentials, or service quota.

## Python packages

The install requirements are maintained in [`skills/scientific-ppt-rebuild/requirements.txt`](../skills/scientific-ppt-rebuild/requirements.txt).

| Package | Declared minimum | Role |
| --- | --- | --- |
| Pillow | 10.0 | Image reading and processing |
| PyMuPDF | 1.24 | PDF inspection, extraction, and rendering |
| python-pptx | 1.0 | PowerPoint package construction and inspection |
| NumPy | 1.26 | Image and geometry calculations |
| Requests | 2.31 | HTTP support for optional integrations |
| OpenAI Python SDK | 2.0 | Optional image backend API support |
| PyYAML | 6.0 | Configuration and skill metadata support |

The requirements include optional-integration packages so the installed runtime can expose its complete CLI. Their installation does not enable a service or authorize an upload. A preservation-only run does not need scientific image generation.

These are lower bounds, not a lockfile. Resolved package versions and transitive dependencies depend on Python, platform, and package-index state. Use the metadata and license files shipped with the versions you actually install when preparing a deployment or distribution.

## Rendering and agent capabilities

| Requirement | Scope |
| --- | --- |
| Windows desktop PowerPoint | Required for the workflow's final rendering and representative edit tests via COM automation |
| Windows PowerShell | Runs the supplied Office rendering and QA scripts |
| LibreOffice, where available | Preliminary rendering/conversion fallback; does not replace final PowerPoint QA |
| Image inspection and local execution tools | Required agent capabilities for evidence reading, reconstruction, and review |
| Real independent page workers | Required for multi-page reconstruction; single-page local execution is supported |
| Appropriate source fonts | Needed for faithful layout; substitutions must be checked in the actual renderer |
| Authorized OCR/image backend | Optional, only when needed and permitted for the supplied material |

Python utilities can perform parts of the workflow on other platforms. This does not establish that the complete workflow is validated on macOS or Linux. A deck without the required Windows PowerPoint review must report that limitation and must not be labeled fully accepted under this skill.

Run `scripts/sources.py doctor` with the selected task Python to inspect import and local renderer availability. The result cannot establish whether the calling agent has worker or image-viewing tools. See [usage diagnostics](usage.md#resume-or-diagnose).

## Licenses

The repository's own reusable code and documentation are licensed under [MIT](../LICENSE). The adapted runtime retains the original MIT notice in [runtime/LICENSE](../skills/scientific-ppt-rebuild/runtime/LICENSE) and attribution in [runtime/NOTICE](../skills/scientific-ppt-rebuild/runtime/NOTICE).

Python packages are separately licensed. The following links point to the maintainers' own license information:

| Dependency | License information | Official source |
| --- | --- | --- |
| Pillow | MIT-CMU | [Pillow license](https://github.com/python-pillow/Pillow/blob/main/LICENSE) |
| PyMuPDF / MuPDF | GNU AGPLv3 or a separate Artifex commercial license | [PyMuPDF licensing](https://pymupdf.io/licensing) |
| python-pptx | MIT | [python-pptx license](https://github.com/scanny/python-pptx/blob/master/LICENSE) |
| NumPy | BSD 3-Clause | [NumPy license](https://github.com/numpy/numpy/blob/main/LICENSE.txt) |
| Requests | Apache 2.0 | [Requests license](https://github.com/psf/requests/blob/main/LICENSE) |
| OpenAI Python SDK | Apache 2.0 | [SDK license](https://github.com/openai/openai-python/blob/main/LICENSE) |
| PyYAML | MIT | [PyYAML license](https://github.com/yaml/pyyaml/blob/main/LICENSE) |

**The repository's MIT license does not relicense PyMuPDF or remove its obligations.** Review the upstream license route appropriate to your use and deployment. This table identifies direct dependencies; it is not an exhaustive inventory of transitive packages, binary-wheel components, or their notices.

PowerPoint, LibreOffice, fonts, agent platforms, and external services have their own terms. User-supplied slides and paper figures retain their respective rights; reconstructing a deck does not establish permission to publish those materials.
