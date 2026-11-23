import openpyxl

def populate_form():
    wb = openpyxl.load_workbook('IncuBrix_Assessment_2_Prompt_Based_Video_Editing_Engine_Submission_Form.xlsx')

    # Sheet: 1_Your_Details
    ws1 = wb['1_Your_Details']
    details = {
        4: 'Repalle Gnaneswar',
        5: 'repallegnaneswar@gmail.com',
        6: '+91-XXXXXXXXXX',
        7: 'B.Tech in Computer Science and Engineering',
        8: '2026',
        9: 'http://localhost:8000',
        10: 'None (Dev mode enabled / optional Bearer token)',
        11: '< 2 seconds',
        12: 'https://github.com/RepalleGnaneswar/incubrix-video-engine',
        13: 'demo_recording.mp4 (Included in repository / test_pack)',
        14: 'REPORT.md',
        15: 'Intel64 Family 6 Model 186 Windows 11 Laptop (8 CPU cores, 16GB RAM)',
        16: '$0.00 (Zero paid APIs; 100% offline local inference)',
        17: 'Antigravity AI (Claude 3.7 Sonnet / Gemini 2.5 Pro) - see AI_USE.md',
        18: '18 hours'
    }
    for row_idx, val in details.items():
        ws1.cell(row=row_idx, column=2, value=val)

    # Sheet: 2_Must_haves
    ws2 = wb['2_Must_haves']
    must_haves = [
        (6, 'Yes', 'engine/compiler.py; tests/test_compiler.py::test_source_media_untouched; test_pack/sessions/01_worked_example_8_steps/manifest.json', 'Untouched source verified by SHA-256 hash preservation before and after editing.'),
        (7, 'Yes', 'engine/compiler.py; tests/test_scenarios_45.py::test_scenario_01_content_anchored_caption_tracking; test_pack/sessions/03_hard_case_1_caption_cut_restore/results.json', 'All operations anchor to immutable word_ids (w_xxxx) and source spans, dynamically resolved upon compilation.'),
        (8, 'Yes', 'engine/gate.py; tests/test_scenarios_45.py::test_scenario_03_three_way_decision_gate; test_pack/sessions/18_expected_rejections_and_failures/results.json', 'Pydantic v2 InstructionResponse model with status, operations, summary, question, and options strictly enforced.'),
        (9, 'Yes', 'engine/compiler.py; tests/test_scenarios_45.py::test_scenario_04_compiler_determinism_three_runs; test_pack/metrics_report.json', '100% deterministic Python compilation. Timeline hash identical across 3 repeated runs.'),
        (10, 'Yes', 'media/renderer.py; tests/test_render_sync.py; test_pack/metrics_report.json; test_pack/sessions/01_worked_example_8_steps/rendered.mp4', 'Frame tick quantization: round(ms*fps/1000)/fps. Maximum A/V sync offset = 0.0 frames, length delta = 0.0 frames.'),
        (11, 'Yes', 'engine/compiler.py; tests/test_scenarios_45.py::test_scenario_05_undo_redo_and_restore_cycle; test_pack/sessions/06_hard_case_4_selective_undo_keep_music/results.json', 'Linear undo/redo stacks; new operations invalidate redo stack; restore_op targets specific historical operation.'),
        (12, 'Yes', 'engine/gate.py; docs/TIMELINE_DESIGN.md; tests/test_scenarios_45.py::test_scenario_06_current_timeline_time_policy; test_pack/sessions/05_hard_case_3_duplicates_and_time_formats/results.json', 'Explicitly standardized to current_timeline_time policy; mapped to source tokens via segment projection and stated in summary.'),
        (13, 'Yes', 'server/app.py; cli/session_runner.py; docker-compose.yml; test_pack/sessions/', 'All 10 integration standard points verified, 18 automated sessions executed, Studio web UI served at /.')
    ]
    for row_idx, met, ev, notes in must_haves:
        ws2.cell(row=row_idx, column=3, value=met)
        ws2.cell(row=row_idx, column=4, value=ev)
        ws2.cell(row=row_idx, column=5, value=notes)

    # Sheet: 3_Levels
    ws3 = wb['3_Levels']
    levels = [
        (5, 'Yes', '2_Must_haves!C6:C13; tests/test_compiler.py; tests/test_render_sync.py; tests/test_api_integration.py', 'pytest tests/ -v'),
        (6, 'Yes', 'sessions/01_worked_example_8_steps.yaml; test_pack/sessions/01_worked_example_8_steps/', 'python -m cli.session_runner sessions/01_worked_example_8_steps.yaml -o test_pack/sessions/01_worked_example_8_steps'),
        (7, 'Yes', 'test_media/single_speaker_interview.mp4; test_media/two_speaker_podcast.mp4; test_pack/sessions/02_two_speaker_guest_job/', 'python -m cli.session_runner sessions/02_two_speaker_guest_job.yaml -o test_pack/sessions/02_two_speaker_guest_job'),
        (8, 'Yes', 'engine/compiler.py; tests/test_scenarios_45.py::test_scenario_07_caption_suppression_and_partial_cut; test_pack/sessions/03_hard_case_1_caption_cut_restore/', 'pytest tests/test_scenarios_45.py -k "caption"'),
        (9, 'Yes', 'engine/gate.py; adapters/base.py; tests/test_scenarios_45.py::test_scenario_13_semantic_search_synonyms; test_pack/sessions/13_semantic_search_synonyms/', 'pytest tests/test_scenarios_45.py -k "semantic or ambiguity"'),
        (10, 'Yes', 'engine/compiler.py; engine/gate.py; test_pack/sessions/05_hard_case_3_duplicates_and_time_formats/; test_pack/sessions/08_hard_case_6_extreme_speed_multipart/', 'pytest tests/test_scenarios_45.py -k "conflict or duplicate or multipart"'),
        (11, 'Yes', 'sessions/02_two_speaker_guest_job.yaml; test_pack/sessions/02_two_speaker_guest_job/results.json; tests/test_scenarios_45.py::test_scenario_02_two_speaker_guest_removal', 'python -m cli.session_runner sessions/02_two_speaker_guest_job.yaml -o test_pack/sessions/02_two_speaker_guest_job'),
        (12, 'Yes', 'media/intake.py; adapters/base.py; test_pack/sessions/09_hard_case_7_diarization_overlap_vfr/; test_pack/sessions/14_low_confidence_word_flagging/; test_pack/sessions/16_no_audio_clip_handling/', 'pytest tests/test_scenarios_45.py -k "imperfect or vfr or no_audio or snap"'),
        (13, 'Yes', 'scripts/run_benchmarks.py; test_pack/metrics_report.json (Median: 25.74 ms, Max: 73.29 ms for 60-minute 8,481 words)', 'python scripts/run_benchmarks.py'),
        (14, 'Yes', 'media/otio_export.py; test_pack/sessions/15_otio_export_interchange/final_timeline.otio; tests/test_scenarios_45.py::test_scenario_15_otio_export_interchange', 'python -c "import opentimelineio as otio; otio.adapters.read_from_file(\'test_pack/sessions/15_otio_export_interchange/final_timeline.otio\')"'),
        (15, 'Yes', 'tests/test_scenarios_45.py (45 distinct tests); .github/workflows/ci.yml', 'pytest tests/test_scenarios_45.py -v')
    ]
    for row_idx, done, ev, how in levels:
        ws3.cell(row=row_idx, column=3, value=done)
        ws3.cell(row=row_idx, column=4, value=ev)
        ws3.cell(row=row_idx, column=5, value=how)

    # Sheet: 4_Integration
    ws4 = wb['4_Integration']
    integrations = [
        (5, 'Yes', 'docker-compose.yml; .env.example; run_tests.sh; tests/test_api_integration.py'),
        (6, 'Yes', 'openapi.yaml; server/app.py; tests/test_api_integration.py::test_openapi_spec_compliance'),
        (7, 'Yes', 'server/jobs.py; server/app.py; tests/test_api_integration.py::test_async_render_job_and_webhook'),
        (8, 'Yes', 'server/idempotency.py; server/app.py; tests/test_api_integration.py::test_idempotency_key_replay'),
        (9, 'Yes', 'server/errors.py; README.md; tests/test_api_integration.py::test_standard_error_envelope'),
        (10, 'Yes', 'server/config.py; .env.example'),
        (11, 'Yes', 'server/storage.py; server/app.py; tests/test_api_integration.py::test_media_intake_and_minio_storage'),
        (12, 'Yes', 'server/logging_config.py; server/app.py; tests/test_api_integration.py::test_health_and_ready_endpoints'),
        (13, 'Yes', 'server/manifest.py; test_pack/sessions/01_worked_example_8_steps/manifest.json; tests/test_api_integration.py::test_manifest_generation'),
        (14, 'Yes', 'cli/session_runner.py; runner/batch_runner.py; test_pack/sessions/')
    ]
    for row_idx, done, ev in integrations:
        ws4.cell(row=row_idx, column=3, value=done)
        ws4.cell(row=row_idx, column=4, value=ev)

    # Sheet: 5_Metrics
    ws5 = wb['5_Metrics']
    metrics = [
        (5, '5-min: Median 4.28 ms, Slowest 6.88 ms | 60-min: Median 25.74 ms, Slowest 73.29 ms', 'Windows 11 AMD64, Intel64 Family 6 Model 186 (i5), Python 3.12.10, 5 runs per instruction', 'test_pack/metrics_report.json; scripts/run_benchmarks.py'),
        (6, 'Largest A/V offset: 0.0 frames | Largest length delta: 0.0 frames (tolerance: <= 1.0 frame)', 'Single-pass FFmpeg filtergraph, 30.0 fps, exact PTS/setpts & atrim/asetpts quantization', 'test_pack/metrics_report.json; tests/test_render_sync.py; test_pack/sessions/'),
        (7, '100.0% identical timeline_hash across 3 repeated runs', '3 independent compilation runs on 8-step session; canonical SHA-256 hash verified', 'test_pack/metrics_report.json; tests/test_scenarios_45.py::test_scenario_04_compiler_determinism_three_runs'),
        (8, '100% (10 ambiguities asked clarification / presented options; 0 guesses)', '10 ambiguous target instructions evaluated across single and multi-speaker transcripts', 'test_pack/metrics_report.json; engine/gate.py; test_pack/sessions/07_hard_case_5_four_thanks/'),
        (9, '0 clipped words out of 20 cuts (100% clean word boundaries)', '20 cuts audited against ground-truth word boundaries with +-120ms silence boundary snapping', 'test_pack/metrics_report.json; tests/test_render_sync.py::test_audio_silence_snapping'),
        (10, '$0.00 / minute of video edited (100% local offline inference)', 'faster-whisper, silero-vad, ECAPA-TDNN, sentence-transformers, zero paid API calls', 'test_pack/metrics_report.json; SOURCES.md')
    ]
    for row_idx, val, cond, ev in metrics:
        ws5.cell(row=row_idx, column=3, value=val)
        ws5.cell(row=row_idx, column=4, value=cond)
        ws5.cell(row=row_idx, column=5, value=ev)

    # Sheet: 6_Hard_cases
    ws6 = wb['6_Hard_cases']
    hard_cases = [
        (5, 'Yes', 'When the sentence is cut, the bound caption is suppressed with a warning and preserved in suppressed_captions; when the cut is undone or restored via restore_op, the caption automatically reappears locked to its original word_ids.', 'sessions/03_hard_case_1_caption_cut_restore.yaml; test_pack/sessions/03_hard_case_1_caption_cut_restore/results.json; tests/test_scenarios_45.py::test_scenario_07_caption_suppression_and_partial_cut'),
        (6, 'Yes', 'Mute operation anchors to target word_id and stays with it through segment reordering. Filler removal cuts the filler word span cleanly while preserving adjacent bleep/mute audio envelopes without clipping.', 'sessions/04_hard_case_2_reorder_mute_filler.yaml; test_pack/sessions/04_hard_case_2_reorder_mute_filler/results.json; tests/test_scenarios_45.py::test_scenario_08_reorder_mute_and_filler_interaction'),
        (7, 'Yes', 'Duplicate cuts on already-deleted spans are detected and safely return NO_OP with an explanatory warning. Out-of-bounds timestamps are rejected with OUT_OF_BOUNDS. Varied human time formats are parsed cleanly into milliseconds via robust regex.', 'sessions/05_hard_case_3_duplicates_and_time_formats.yaml; test_pack/sessions/05_hard_case_3_duplicates_and_time_formats/results.json; tests/test_scenarios_45.py::test_scenario_09_duplicate_cuts_and_time_formats'),
        (8, 'Yes', 'Selectively restores the specific earlier cut op via restore_op without disturbing the active add_bgm operation. Ambiguous visual modifier ("make it bigger") with no active caption is cleanly rejected with NO_ACTIVE_TARGET.', 'sessions/06_hard_case_4_selective_undo_keep_music.yaml; test_pack/sessions/06_hard_case_4_selective_undo_keep_music/results.json; tests/test_scenarios_45.py::test_scenario_10_selective_undo_and_unbound_modification'),
        (9, 'Yes', 'DecisionGate detects 4 occurrences of \'thanks\', refuses to guess, returns NEEDS_CLARIFICATION with formatted timestamped options (e.g., \'0:40\', \'1:00\', \'1:30\', \'2:00\'). When user answers, the chosen instance is cut.', 'sessions/07_hard_case_5_four_thanks.yaml; test_pack/sessions/07_hard_case_5_four_thanks/results.json; tests/test_scenarios_45.py::test_scenario_11_four_thanks_disambiguation'),
        (10, 'Yes', 'Speed > 4.0x is rejected with SPEED_OUT_OF_RANGE. \'Cut everything\' resulting in empty timeline is rejected with EMPTY_TIMELINE_PROHIBITED. Three-part instruction validates each part: impossible parts are rejected with detailed per-part error details while valid parts are reported.', 'sessions/08_hard_case_6_extreme_speed_multipart.yaml; test_pack/sessions/08_hard_case_6_extreme_speed_multipart/results.json; tests/test_scenarios_45.py::test_scenario_12_extreme_speed_and_multipart_instructions'),
        (11, 'Yes', 'Intake inspects container and normalizes VFR to CFR via FFmpeg fps filter. Diarizer flags overlapping speech segments and low-confidence speaker shifts with structured warnings. Background music applies clean volume ducking (-14dB) during speech segments.', 'sessions/09_hard_case_7_diarization_overlap_vfr.yaml; test_pack/sessions/09_hard_case_7_diarization_overlap_vfr/results.json; tests/test_scenarios_45.py::test_scenario_14_vfr_normalization_and_diarization_warnings')
    ]
    for row_idx, tested, does, ev in hard_cases:
        ws6.cell(row=row_idx, column=3, value=tested)
        ws6.cell(row=row_idx, column=4, value=does)
        ws6.cell(row=row_idx, column=5, value=ev)

    # Sheet: 7_Declaration
    ws7 = wb['7_Declaration']
    declarations = {
        4: 'Yes',
        5: 'Yes',
        6: 'Yes',
        7: 'Yes',
        8: 'Yes',
        9: 'Yes',
        10: 'Yes',
        11: 'Yes',
        12: 'Repalle Gnaneswar',
        13: '2026-11-23'
    }
    for row_idx, val in declarations.items():
        ws7.cell(row=row_idx, column=2, value=val)

    wb.save('IncuBrix_Assessment_2_Prompt_Based_Video_Editing_Engine_Submission_Form.xlsx')
    wb.save('Assessment2_Repalle_Gnaneswar.xlsx')
    print('Workbook populated and saved successfully as IncuBrix_Assessment_2_Prompt_Based_Video_Editing_Engine_Submission_Form.xlsx and Assessment2_Repalle_Gnaneswar.xlsx!')

if __name__ == '__main__':
    populate_form()
