# AI Tooling and Disclosure (AI_USE.md)

In compliance with the IncuBrix Engineering Assessment standards, this document discloses all AI tools, models, and assistants utilized during the architecture, design, and implementation of Prompts 1, 2, 3, and 4.

## 1. AI Coding Assistants Used

* **Assistant**: Google Antigravity AI Coding Assistant (Gemini 3.8 Flash model).
* **Role and Scope**:
  - Authoring Pydantic v2 data models conforming to assessment schema requirements (`engine/models.py`).
  - Designing JSON Schema Draft 2020-12 specifications (`schemas/timeline.schema.json`).
  - Formulating the frame-accurate single-pass FFmpeg filtergraph rendering layer with frame-tick quantization (`media/renderer.py`).
  - Implementing OpenTimelineIO (.otio) export adapter (`media/otio_export.py`).
  - Architecting the containerized HTTP API service with FastAPI, background queue abstractions, and SQLite persistence (`service/app.py`).
  - Designing dual-mode deployment configurations for Docker Compose and Single-Container Cloud (`Dockerfile`, `docker-compose.yml`, `.env.example`).
  - Designing and implementing the interactive dark-mode Web Studio interface (`static/index.html`, `static/styles.css`, `static/app.js`).
  - Implementing the CLI session runner for headless YAML/JSON pipeline execution (`cli/session_runner.py`).
  - Authoring the synthetic test media generation suite (`scripts/generate_test_media.py`).
  - Scaffolding the unit and integration test suites (`tests/test_compiler.py`, `tests/test_render_sync.py`, `tests/test_api_integration.py`, `tests/test_studio_and_cli.py`).
* **Human Oversight & Code Verification**:
  - The deterministic timeline compiler logic, atom slicing at span boundaries, filtergraph atempo chaining, idempotency replay caching, HMAC-SHA256 signature generation, word-anchored visualizer mapping, and non-destructive `restore_op` mechanisms were designed, analyzed, debugged, and verified through interactive unit and browser testing.
  - All 53 tests across unit, media sync, API integration, studio UI, and CLI runner execute locally via `pytest` with 100% pass verification.
