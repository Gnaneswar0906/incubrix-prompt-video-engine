# AI Tooling and Disclosure (AI_USE.md)

In compliance with the IncuBrix Engineering Assessment standards, this document discloses all AI tools, models, and assistants utilized during the architecture, design, and implementation of Prompt 1.

## 1. AI Coding Assistants Used

* **Assistant**: Google Antigravity AI Coding Assistant (Gemini 3.8 Flash model).
* **Role and Scope**:
  - Drafting initial Pydantic v2 data models conforming to assessment schema requirements.
  - Formulating JSON Schema Draft 2020-12 specifications.
  - Authoring technical architecture documentation (`docs/TIMELINE_DESIGN.md`).
  - Scaffolding the unit test suite (`tests/test_compiler.py`) covering all invariant rules and hard cases.
* **Human Oversight & Code Verification**:
  - The deterministic timeline compiler logic, atom slicing at span boundaries, and non-destructive `restore_op` mechanisms were designed, analyzed, debugged, and verified through interactive unit testing.
  - All 26 unit tests run locally via `pytest` with 100% pass verification and zero external network calls.
