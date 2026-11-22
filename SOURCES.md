# Third-Party Dependencies and Sources (SOURCES.md)

All third-party libraries, packages, and frameworks used in the IncuBrix Prompt-Based Video Editing Engine are commercially licensed (MIT or Apache 2.0). No AGPL, CC-BY-NC, or research-only packages are included in the default execution path.

## 1. Libraries and Frameworks

| Library | Version | License | Commercial Use | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| **Pydantic** | `>= 2.7.0` | MIT License | Permitted | High-performance, schema-validated immutable data models (`WordToken`, `EditOperation`, `CompiledTimeline`, `InstructionResponse`). |
| **Pytest** | `>= 8.0.0` | MIT License | Permitted | Automated test suite execution, fixture definitions, regression testing. |
| **Python Standard Library** | `3.11+ / 3.12` | PSF License | Permitted | `hashlib` (SHA-256 canonical hashing), `json` (serialization), `re` (regex intent parsing), `copy`, `typing`. |

## 2. Media and Test Data

* All synthetic test transcripts and token audio markers were procedurally generated in `tests/test_compiler.py`.
* No external proprietary speech data or voice assets without consent are used in this codebase.
