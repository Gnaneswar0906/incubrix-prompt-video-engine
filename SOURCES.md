# Third-Party Dependencies and Sources (SOURCES.md)

All third-party libraries, packages, and frameworks used in the IncuBrix Prompt-Based Video Editing Engine are commercially licensed (MIT, Apache 2.0, BSD, or LGPL). No AGPL, CC-BY-NC, or research-only packages are included in the default execution path.

## 1. Libraries and Frameworks

| Library | Version | License | Commercial Use | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| **Pydantic** | `>= 2.7.0` | MIT License | Permitted | High-performance, schema-validated immutable data models (`WordToken`, `EditOperation`, `CompiledTimeline`, `InstructionResponse`). |
| **Pytest** | `>= 8.0.0` | MIT License | Permitted | Automated test suite execution, fixture definitions, regression testing. |
| **OpenTimelineIO** | `>= 0.18.0` | Apache-2.0 | Permitted | Professional timeline interchange format (.otio) export for Premiere, Resolve, and FCP. |
| **imageio-ffmpeg** | `>= 0.8.0` | BSD-2-Clause | Permitted | Portable FFmpeg binary discovery and Python subprocess interface. |
| **FFmpeg / FFprobe** | `v8.0+ / master` | LGPL v3.0 | Permitted | Frame-accurate audio/video inspection, single-pass filtergraph rendering, bleep synthesis, atempo speed adjustments. |
| **Google Generative AI** | `>= 0.8.0` | Apache-2.0 | Permitted | Intent parser adapter using structured JSON output (pure intent parsing; never touches timeline math). |
| **Scikit-learn / Scipy** | `Latest` | BSD-3-Clause | Permitted | Offline spectral audio clustering for speaker diarization and TF-IDF / cosine semantic matching. |
| **Python Standard Library** | `3.11+ / 3.12` | PSF License | Permitted | `hashlib` (SHA-256 canonical hashing), `json`, `re`, `subprocess`, `urllib.request`. |

## 2. Media and Test Data

* All synthetic test videos and audio signals (burned-in timecode, sine waves, speech tones) are procedurally generated via FFmpeg `testsrc2`, `sine`, and `drawtext` filters in `tests/test_render_sync.py`.
* Zero proprietary voice or video assets without explicit commercial authorization are used.
