# IncuBrix Master Evidence Index

This document maps every requirement from the **IncuBrix Engineering Assessment 2** Submission Form to its exact source code implementation, automated test function, and reproducible test artifact in `test_pack/sessions/`.

---

## 1. Must-Haves (1–8)

| # | Must-Have Claim | Code Implementation | Test Function | Test Pack Artifact |
|---|---|---|---|---|
| **1** | **Never damage the original**<br>Source media is read-only; edits form an immutable step history; SHA-256 hash verified before and after editing. | [`engine/compiler.py`](file:///c:/Users/repal/Downloads/B-TECH/Placement/Incrubrix%20Software%20Intern/engine/compiler.py) | `tests/test_compiler.py::test_source_media_untouched` | [`test_pack/sessions/01_worked_example_8_steps/manifest.json`](file:///c:/Users/repal/Downloads/B-TECH/Placement/Incrubrix%20Software%20Intern/test_pack/sessions/01_worked_example_8_steps/manifest.json) |
| **2** | **Edits stick to content**<br>Captions, mutes, bleeps, and effects dynamically anchor to immutable `word_id`s (`w_xxxx`) across cuts, reorders, and speed changes. | [`engine/compiler.py`](file:///c:/Users/repal/Downloads/B-TECH/Placement/Incrubrix%20Software%20Intern/engine/compiler.py)<br>[`engine/models.py`](file:///c:/Users/repal/Downloads/B-TECH/Placement/Incrubrix%20Software%20Intern/engine/models.py) | `tests/test_scenarios_45.py::test_caption_follows_anchored_words_across_cuts` | [`test_pack/sessions/03_hard_case_1_caption_cut_restore/results.json`](file:///c:/Users/repal/Downloads/B-TECH/Placement/Incrubrix%20Software%20Intern/test_pack/sessions/03_hard_case_1_caption_cut_restore/results.json) |
| **3** | **Three-way answers**<br>Every instruction strictly evaluates to `applied`, `needs_clarification`, or `rejected` via Pydantic schema validation. | [`engine/gate.py`](file:///c:/Users/repal/Downloads/B-TECH/Placement/Incrubrix%20Software%20Intern/engine/gate.py) | `tests/test_scenarios_45.py::test_gate_rejection_scenarios` | [`test_pack/sessions/18_expected_rejections_and_failures/results.json`](file:///c:/Users/repal/Downloads/B-TECH/Placement/Incrubrix%20Software%20Intern/test_pack/sessions/18_expected_rejections_and_failures/results.json) |
| **4** | **Predictable (Determinism)**<br>Compiler uses deterministic integer millisecond projection and canonical SHA-256 timeline hashing across runs. | [`engine/compiler.py`](file:///c:/Users/repal/Downloads/B-TECH/Placement/Incrubrix%20Software%20Intern/engine/compiler.py) | `tests/test_scenarios_45.py::test_determinism_identical_hash_repeated_runs` | [`test_pack/metrics_report.json`](file:///c:/Users/repal/Downloads/B-TECH/Placement/Incrubrix%20Software%20Intern/test_pack/metrics_report.json) |
| **5** | **Render matches timeline**<br>Single-pass FFmpeg filtergraph with frame-tick boundary quantization guarantees $\le 1$ frame A/V offset and total length sync. | [`media/renderer.py`](file:///c:/Users/repal/Downloads/B-TECH/Placement/Incrubrix%20Software%20Intern/media/renderer.py) | `tests/test_render_sync.py::test_frame_accurate_render_sync` | [`test_pack/sessions/01_worked_example_8_steps/rendered.mp4`](file:///c:/Users/repal/Downloads/B-TECH/Placement/Incrubrix%20Software%20Intern/test_pack/sessions/01_worked_example_8_steps/rendered.mp4) |
| **6** | **All operations work, undo/redo & restore**<br>Linear undo/redo stacks (`new edit clears redo`) plus non-linear selective restoration (`restore_op`). | [`engine/compiler.py`](file:///c:/Users/repal/Downloads/B-TECH/Placement/Incrubrix%20Software%20Intern/engine/compiler.py) | `tests/test_scenarios_45.py::test_linear_undo_redo_cycle`<br>`tests/test_scenarios_45.py::test_non_linear_restore_specific_earlier_edit` | [`test_pack/sessions/06_hard_case_4_selective_undo_keep_music/results.json`](file:///c:/Users/repal/Downloads/B-TECH/Placement/Incrubrix%20Software%20Intern/test_pack/sessions/06_hard_case_4_selective_undo_keep_music/results.json) |
| **7** | **Clear time policy**<br>Standardized to `current_timeline_time` across all gate parsing and stated explicitly in every instruction summary. | [`engine/gate.py`](file:///c:/Users/repal/Downloads/B-TECH/Placement/Incrubrix%20Software%20Intern/engine/gate.py)<br>[`docs/TIMELINE_DESIGN.md`](file:///c:/Users/repal/Downloads/B-TECH/Placement/Incrubrix%20Software%20Intern/docs/TIMELINE_DESIGN.md) | `tests/test_scenarios_45.py::test_natural_time_parsing_ranges` | [`test_pack/sessions/05_hard_case_3_duplicates_and_time_formats/results.json`](file:///c:/Users/repal/Downloads/B-TECH/Placement/Incrubrix%20Software%20Intern/test_pack/sessions/05_hard_case_3_duplicates_and_time_formats/results.json) |
| **8** | **Integration Standard, runner & demo**<br>Microservice architecture, containerized dual deployment, 18 automated sessions, and Web Studio. | [`service/app.py`](file:///c:/Users/repal/Downloads/B-TECH/Placement/Incrubrix%20Software%20Intern/service/app.py)<br>[`cli/session_runner.py`](file:///c:/Users/repal/Downloads/B-TECH/Placement/Incrubrix%20Software%20Intern/cli/session_runner.py) | `tests/test_api_integration.py::test_session_lifecycle_flow`<br>`tests/test_studio_and_cli.py::test_cli_session_runner_worked_example_yaml` | [`test_pack/sessions/01_worked_example_8_steps/`](file:///c:/Users/repal/Downloads/B-TECH/Placement/Incrubrix%20Software%20Intern/test_pack/sessions/01_worked_example_8_steps/) |

---

## 2. Assessment Levels (Core, Advanced, Outstanding)

| Level | Item Description | Primary Files | Automated Test | Test Pack Artifact |
|---|---|---|---|---|
| **Core 1** | **All must-haves pass** | `engine/compiler.py`, `service/app.py` | `pytest tests/ -v` (95 passed) | All sessions in `test_pack/sessions/` |
| **Core 2** | **8-step worked example runs on own test video** | `sessions/01_worked_example_8_steps.yaml` | `tests/test_compiler.py::test_worked_example_full_flow` | `test_pack/sessions/01_worked_example_8_steps/` |
| **Core 3** | **Single & multi-speaker video support** | `test_media/single_speaker_interview.mp4`<br>`test_media/two_speaker_podcast.mp4` | `tests/test_render_sync.py::test_speaker_diarization_anomalies` | `test_pack/sessions/02_two_speaker_guest_job/` |
| **Advanced 1** | **Edits that shift each other**<br>(Captions follow words; 100% cut suppresses caption with warning; partial cuts keep remaining words; sped-up captions keep $\ge 700\text{ ms}$). | `engine/compiler.py` | `tests/test_scenarios_45.py::test_caption_total_cut_suppression`<br>`tests/test_scenarios_45.py::test_caption_minimum_display_duration_700ms` | `test_pack/sessions/03_hard_case_1_caption_cut_restore/results.json` |
| **Advanced 2** | **Ambiguity & references**<br>("that caption", "pricing" finds "cost", asks clarification with options, never guesses). | `engine/gate.py`<br>`adapters/base.py` | `tests/test_scenarios_45.py::test_ambiguous_pricing_asks_clarification` | `test_pack/sessions/13_semantic_search_synonyms/` |
| **Advanced 3** | **Conflicts & edge cases**<br>(Repeated instructions safe; protected pauses survive; impossible cuts rejected; latest-wins speed rule; multi-part partial execution). | `engine/compiler.py`<br>`engine/gate.py` | `tests/test_scenarios_45.py::test_duplicate_cut_rejected`<br>`tests/test_scenarios_45.py::test_multipart_valid_and_invalid_parts` | `test_pack/sessions/05_hard_case_3_duplicates_and_time_formats/`<br>`test_pack/sessions/08_hard_case_6_extreme_speed_multipart/` |
| **Advanced 4** | **Two speakers**<br>("remove everything guest says about old job" cuts only guest lines and asks about host lead-in question). | `sessions/02_two_speaker_guest_job.yaml` | `tests/test_compiler.py::test_hard_case_remove_after_phrase_multiple_occurrences` | `test_pack/sessions/02_two_speaker_guest_job/results.json` |
| **Outstanding 1** | **Imperfect data handling**<br>(Silence boundary snapping $\pm 120\text{ms}$; low confidence flagged $<0.65$; VFR-to-CFR normalization; no-audio synthesis). | `media/intake.py`<br>`adapters/base.py` | `tests/test_render_sync.py::test_media_intake_vfr_normalization`<br>`tests/test_render_sync.py::test_stt_vad_boundary_snapping` | `test_pack/sessions/09_hard_case_7_diarization_overlap_vfr/`<br>`test_pack/sessions/14_low_confidence_word_flagging/`<br>`test_pack/sessions/16_no_audio_clip_handling/` |
| **Outstanding 2** | **Scale ($\le 3.0$ seconds on 60-min video)**<br>Median latency 25.74 ms, slowest 73.29 ms on ~8,500 word timeline. | `scripts/run_benchmarks.py` | `tests/test_studio_and_cli.py::test_benchmark_60min_scale` | `test_pack/metrics_report.json` |
| **Outstanding 3** | **OpenTimelineIO (.otio) export** | `media/otio_export.py` | `tests/test_render_sync.py::test_otio_export_validation` | `test_pack/sessions/15_otio_export_interchange/final_timeline.otio` |
| **Outstanding 4** | **Automated CI test suite ($\ge 40$ scenarios)** | `tests/test_scenarios_45.py`<br>`.github/workflows/ci.yml` | `pytest tests/test_scenarios_45.py -v` (42 tests pass) | CI logs & GitHub Actions workflow |

---

## 3. Integration Standards (1–10)

| Point | Standard Requirement | Code Implementation | Verification Test | Test Pack Artifact |
|---|---|---|---|---|
| **1** | **One-command start and test** | `docker-compose.yml`<br>`.env.example`<br>`run_tests.sh` | `tests/test_api_integration.py` | `run_tests.sh` |
| **2** | **Documented HTTP API (OpenAPI 3.1)** | `openapi.yaml`<br>`service/app.py` | `tests/test_api_integration.py::test_openapi_parity` | `openapi.yaml` |
| **3** | **Background jobs ($>2\text{s}$) & HMAC webhooks** | `service/queue.py`<br>`service/app.py`<br>`service/hmac_util.py` | `tests/test_api_integration.py::test_render_and_manifest`<br>`tests/test_api_integration.py::test_hmac_webhook_signature` | `test_pack/sessions/01_worked_example_8_steps/manifest.json` |
| **4** | **Safe retries (`Idempotency-Key`)** | `service/app.py`<br>`service/database.py` | `tests/test_api_integration.py::test_idempotency_key_replay` | `data/incubrix.db` |
| **5** | **Clear errors (`{"error": {...}}`)** | `service/app.py`<br>`README.md` | `tests/test_api_integration.py::test_standard_error_envelope_404` | Error JSON response payload |
| **6** | **Configuration (environment-driven)** | `service/config.py`<br>`.env.example` | `tests/test_api_integration.py` | `.env.example` |
| **7** | **Files in, files out (S3 / MinIO storage)** | `service/storage.py`<br>`service/app.py` | `tests/test_api_integration.py::test_session_lifecycle_flow` | `data/storage/` |
| **8** | **Logs & health (/health, /ready, JSON logs)** | `service/logging.py`<br>`service/app.py` | `tests/test_api_integration.py::test_health_probe`<br>`tests/test_api_integration.py::test_ready_probe` | Application log output |
| **9** | **Output manifest (`manifest.json`)** | `service/manifest.py` | `tests/test_api_integration.py::test_render_and_manifest` | `test_pack/sessions/01_worked_example_8_steps/manifest.json` |
| **10** | **Batch CLI session runner** | `cli/session_runner.py`<br>`runner/batch_runner.py` | `tests/test_studio_and_cli.py::test_cli_session_runner_worked_example_yaml` | `test_pack/sessions/` |

---

## 4. Hardware Benchmarks & Measured Numbers

| Metric | Measured Real Value | Measurement Condition & Hardware | Reproducibility Command | Evidence File |
|---|---|---|---|---|
| **1. Latency (5-min)** | **Median: 4.28 ms**, Slowest: 6.88 ms | Windows 11 AMD64, Intel Core i5, Python 3.12, 5 runs | `python scripts/run_benchmarks.py` | [`test_pack/metrics_report.json`](file:///c:/Users/repal/Downloads/B-TECH/Placement/Incrubrix%20Software%20Intern/test_pack/metrics_report.json) |
| **1. Latency (60-min)** | **Median: 25.74 ms**, Slowest: 73.29 ms | Windows 11 AMD64, Intel Core i5, Python 3.12, 5 runs | `python scripts/run_benchmarks.py` | [`test_pack/metrics_report.json`](file:///c:/Users/repal/Downloads/B-TECH/Placement/Incrubrix%20Software%20Intern/test_pack/metrics_report.json) |
| **2. Render Accuracy** | **A/V Offset: 0.0 frames**, Length Delta: 0.0 frames | 30.0 fps, frame-tick quantized single-pass filtergraph | `pytest tests/test_render_sync.py::test_frame_accurate_render_sync` | [`test_pack/metrics_report.json`](file:///c:/Users/repal/Downloads/B-TECH/Placement/Incrubrix%20Software%20Intern/test_pack/metrics_report.json) |
| **3. Determinism** | **100.0%** (`d4020293bd56ae78...`) | 3 independent runs on 8-step session | `pytest tests/test_scenarios_45.py::test_determinism_identical_hash_repeated_runs` | [`test_pack/metrics_report.json`](file:///c:/Users/repal/Downloads/B-TECH/Placement/Incrubrix%20Software%20Intern/test_pack/metrics_report.json) |
| **4. Clarification Quality** | **100%** (10 asked / 0 guessed) | 10 ambiguous instructions across single/multi-speaker | `pytest tests/test_scenarios_45.py::test_ambiguous_pricing_asks_clarification` | [`test_pack/metrics_report.json`](file:///c:/Users/repal/Downloads/B-TECH/Placement/Incrubrix%20Software%20Intern/test_pack/metrics_report.json) |
| **5. Word Clipping** | **0 clipped words** (out of 20 cuts) | Ground-truth listening audit with $\pm 120\text{ms}$ snapping | `pytest tests/test_render_sync.py::test_stt_vad_boundary_snapping` | [`test_pack/metrics_report.json`](file:///c:/Users/repal/Downloads/B-TECH/Placement/Incrubrix%20Software%20Intern/test_pack/metrics_report.json) |
| **6. Operational Cost** | **$0.00 / minute** of video edited | 100% offline local inference (MIT/Apache-2.0 models) | `SOURCES.md` & `manifest.json` inspection | [`SOURCES.md`](file:///c:/Users/repal/Downloads/B-TECH/Placement/Incrubrix%20Software%20Intern/SOURCES.md) |

---

## 5. Hard Cases (1–7)

| Case | Scenario Tested | System Behavior | Evidence File Link |
|---|---|---|---|
| **1** | **Caption cut and restored** | Caption suppressed when words cut; automatically reappears on restore. | [`test_pack/sessions/03_hard_case_1_caption_cut_restore/results.json`](file:///c:/Users/repal/Downloads/B-TECH/Placement/Incrubrix%20Software%20Intern/test_pack/sessions/03_hard_case_1_caption_cut_restore/results.json) |
| **2** | **Reorder, mute & filler removal** | Mute locked to word during segment reorder; filler cut preserves bleep envelope. | [`test_pack/sessions/04_hard_case_2_reorder_mute_filler/results.json`](file:///c:/Users/repal/Downloads/B-TECH/Placement/Incrubrix%20Software%20Intern/test_pack/sessions/04_hard_case_2_reorder_mute_filler/results.json) |
| **3** | **Duplicate cuts & varied time formats** | Duplicate cuts safely return NO_OP with warning; varied time strings parsed cleanly. | [`test_pack/sessions/05_hard_case_3_duplicates_and_time_formats/results.json`](file:///c:/Users/repal/Downloads/B-TECH/Placement/Incrubrix%20Software%20Intern/test_pack/sessions/05_hard_case_3_duplicates_and_time_formats/results.json) |
| **4** | **Selective undo while keeping music** | Restores specific earlier cut op via `restore_op` while keeping active BGM intact. | [`test_pack/sessions/06_hard_case_4_selective_undo_keep_music/results.json`](file:///c:/Users/repal/Downloads/B-TECH/Placement/Incrubrix%20Software%20Intern/test_pack/sessions/06_hard_case_4_selective_undo_keep_music/results.json) |
| **5** | **Four "thanks" disambiguation** | DecisionGate detects 4 instances of "thanks", presents 4 options; user selects 3rd. | [`test_pack/sessions/07_hard_case_5_four_thanks/results.json`](file:///c:/Users/repal/Downloads/B-TECH/Placement/Incrubrix%20Software%20Intern/test_pack/sessions/07_hard_case_5_four_thanks/results.json) |
| **6** | **Extreme speed & multipart instruction** | Rejects 10x speed & empty timeline; validates 3-part instruction reporting partial failure. | [`test_pack/sessions/08_hard_case_6_extreme_speed_multipart/results.json`](file:///c:/Users/repal/Downloads/B-TECH/Placement/Incrubrix%20Software%20Intern/test_pack/sessions/08_hard_case_6_extreme_speed_multipart/results.json) |
| **7** | **Two-speaker, overlap, VFR & BGM** | VFR normalized to CFR; overlapping speech flagged; BGM ducked to -14 dB under speech. | [`test_pack/sessions/09_hard_case_7_diarization_overlap_vfr/results.json`](file:///c:/Users/repal/Downloads/B-TECH/Placement/Incrubrix%20Software%20Intern/test_pack/sessions/09_hard_case_7_diarization_overlap_vfr/results.json) |
