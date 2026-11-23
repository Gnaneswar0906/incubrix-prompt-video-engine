# AI Tooling and Disclosure (AI_USE.md)

In compliance with the IncuBrix Engineering Assessment standards, this document discloses all AI tools, models, and assistants utilized during the architecture, design, and implementation of Prompt 1 and Prompt 2.

## 1. AI Coding Assistants Used

* **Assistant**: Google Antigravity AI Coding Assistant (Gemini 3.8 Flash model).
* **Role and Scope**:
  - Authoring Pydantic v2 data models conforming to assessment schema requirements.
  - Designing JSON Schema Draft 2020-12 specifications.
  - Formulating the frame-accurate single-pass FFmpeg filtergraph rendering layer with frame-tick quantization.
  - Implementing OpenTimelineIO (.otio) export adapter.
  - Authoring technical architecture documentation (`docs/TIMELINE_DESIGN.md`).
  - Scaffolding the unit test suites (`tests/test_compiler.py` and `tests/test_render_sync.py`).
* **Human Oversight & Code Verification**:
  - The deterministic timeline compiler logic, atom slicing at span boundaries, filtergraph atempo chaining, and non-destructive `restore_op` mechanisms were designed, analyzed, debugged, and verified through interactive unit testing.
  - All unit tests run locally via `pytest` with 100% pass verification.
