# IncuBrix Final Pre-Submission Launch Playbook

**Candidate**: Repalle Gnaneswar  
**Institution**: Amrita Vishwa Vidyapeetham, Bengaluru — B.Tech CSE (2027)  
**Email**: repallegnaneswar@gmail.com  

---

## 1. Push to Private GitHub Repository

Open **PowerShell** in the repository root directory (`c:\Users\repal\Downloads\B-TECH\Placement\Incrubrix Software Intern`) and run:

```powershell
# 1. Initialize git (if not already initialized) and verify remote
git status

# 2. Stage all audited files, test packs, reports, and submission workbooks
git add .

# 3. Create clean pre-submission commit
git commit -m "feat(submission): complete Prompt 1-6 submission pack with 95 passing tests, 18 executed sessions, and verified evidence index"

# 4. Set main branch and link to your private GitHub repository
git branch -M main

# Replace <YOUR_GITHUB_USERNAME> with your actual GitHub username:
git remote add origin https://github.com/RepalleGnaneswar/incubrix-prompt-video-engine.git

# 5. Push to GitHub
git push -u origin main
```

> **Reviewer Access Reminder**: Ensure your repository is set to **Private** and invite the IncuBrix reviewer GitHub handle before the deadline.

---

## 2. Deploy to Hugging Face Spaces (Free 16GB CPU Docker SDK)

Hugging Face Spaces provides free, persistent 16GB RAM CPU containers that run Dockerfiles natively:

```powershell
# 1. Create a new Space on Hugging Face (https://huggingface.co/new-space)
#    - Space Name: incubrix-video-studio
#    - License: Apache-2.0
#    - Space SDK: Docker (Blank)
#    - Visibility: Public

# 2. Add Hugging Face Space as a secondary git remote
# Replace <YOUR_HF_USERNAME> with your Hugging Face username:
git remote add space https://huggingface.co/spaces/<YOUR_HF_USERNAME>/incubrix-video-studio

# 3. Push container to Hugging Face Spaces
git push --force space main
```

Your space will automatically build the `Dockerfile`, install FFmpeg, bind to port `7860`, and serve the dark-mode Web Studio at:
`https://<YOUR_HF_USERNAME>-incubrix-video-studio.hf.space`

---

## 3. 8-Minute Unedited Demo Video Script & Timestamps

Record your screen and microphone using OBS Studio or Windows Snipping Tool (Win + Alt + R). Ensure the recording is **single-take and unedited** (under 8 minutes).

### Detailed 8-Minute Timeline:

```
00:00 - 01:00 (60s) | Introduction & Architecture Overview
01:00 - 02:45 (105s)| Interactive Web Studio & Clean 8-Step Worked Example
02:45 - 04:15 (90s) | Hard Cases: Disambiguation & Rejection Handling
04:15 - 05:45 (90s) | Test Suite Execution (95/95 Passing in CI)
05:45 - 07:15 (90s) | Deep Dive into Deterministic Compiler (engine/compiler.py)
07:15 - 08:00 (45s) | OTIO Interchange, Manifest Provenance & Closing
```

---

### Step-by-Step Talking Script:

#### `00:00 - 01:00` — Introduction & Core Architectural Philosophy
- **What to show**: VS Code workspace, `README.md`, and `REPORT.md`.
- **What to say**:
  > *"Hi everyone, I'm Repalle Gnaneswar from Amrita Vishwa Vidyapeetham, Bengaluru. This is my submission for Assessment 2: Prompt-Based Video Editing Engine.  
  > The core philosophy of this engine is that **edits attach to immutable content tokens—word IDs and source spans—rather than wall-clock timestamps**.  
  > Timeline compilation is 100% deterministic Python code. No LLM directly touches timeline math or video state, guaranteeing frame-accurate reproducibility and zero clock drift."*

#### `01:00 - 02:45` — Web Studio & 8-Step Worked Example
- **What to show**: Browser at `http://localhost:8000/` or your live HF Space.
- **What to say & click**:
  > *"Here is the interactive dark-mode Web Studio served by FastAPI.  
  > Let's load the built-in single speaker interview sample video. Notice the word-anchored visualizer showing spoken word pills colored by speaker.  
  > Now let's run the 8-step worked example:  
  > 1. 'Add a caption Welcome! when I say welcome' -> Caption badge locks directly to word `w_01`.  
  > 2. 'Cut the first 30 seconds' -> Words are visually struck out, timeline shifts, but the caption stays locked to the speech!  
  > 3. 'Remove the part about pricing' -> The system detects 'pricing' is mentioned at 0:35, 0:45, and 0:55. It refuses to guess and presents an Amber Needs Clarification card with clickable options. Let's click 'the second one' -> immediately applied!  
  > 4. 'Speed up from 1:00 to 1:30 by 2x' -> Highlighted in blue, segment speeds up.  
  > 5. 'Actually, put the intro back' -> Re-inserts the intro cut.  
  > 6. 'Undo' -> Cleanly reverses.  
  > 7. 'Make that caption red' -> Instantly applies CSS and ASS subtitle color."*

#### `02:45 - 04:15` — Hard Cases: Disambiguation & Semantic Rejection
- **What to show**: Web Studio input or CLI runner executing hard cases.
- **What to say**:
  > *"Let's test our Decision Gate with extreme edge cases:  
  > First, let's type 'Cut everything' or 'Cut the first 200 seconds' -> Red Rejected Card: `WHOLE_VIDEO_CUT_REJECTED`—an edit must leave at least one segment.  
  > Next, 'Speed up by 10x' -> Rejected with `EXTREME_SPEED_REJECTED` (maximum valid factor is 4.0x / 8.0x).  
  > Next, 'Make that caption bigger' when no captions exist -> Rejected with `MISSING_TARGET`.  
  > And in Session 07, saying 'Remove everything after I say thanks' when 'thanks' is said four times triggers structured disambiguation with 4 timestamped choices. It never guesses on destructive edits."*

#### `04:15 - 05:45` — Automated Test Suite (95/95 Passing)
- **What to show**: Terminal running `pytest tests/ -v`.
- **What to say**:
  > *"Now let's switch to the terminal and run our automated test suite with `pytest tests/ -v`.  
  > Notice that all 95 tests pass in approximately 32 seconds with zero API keys:  
  > - 26 compiler unit tests testing determinism, 700ms caption clamping, protected silences, and non-linear `restore_op`.  
  > - 9 render sync tests verifying that audio and video stay in sync within $\le 1$ frame using our single-pass FFmpeg filtergraph.  
  > - 11 API integration tests covering OpenAPI 3.1, background jobs, idempotency key replay, and HMAC webhooks.  
  > - 42 comprehensive CI scenarios in `test_scenarios_45.py`."*

#### `05:45 - 07:15` — Code Walkthrough: `engine/compiler.py` & Invariants
- **What to show**: `engine/compiler.py` and `engine/gate.py` in VS Code.
- **What to say**:
  > *"Let's inspect `engine/compiler.py`.  
  > Notice lines 40 to 110: the compilation starts with an untouched `TranscriptIndex`.  
  > For every active operation in the history:  
  > - When a cut occurs, we remove or slice spans from `active_segments`.  
  > - Captions dynamically check if their bound words are still alive. If 100% of bound words are cut, the caption is placed in `suppressed_captions` with a warning. If that cut is later restored, the caption automatically reappears!  
  > - Line 140: Sped-up captions enforce a readable minimum duration of 700 ms.  
  > - Line 195: In `SinglePassRenderer`, we quantize every segment start and end point to exact video frame ticks: `round(ms * fps / 1000) / fps`, eliminating any audio-video drift."*

#### `07:15 - 08:00` — OTIO Export, Output Manifest & Closing
- **What to show**: Open `test_pack/sessions/01_worked_example_8_steps/` showing the 5 artifacts (`results.json`, `final_timeline.json`, `final_timeline.otio`, `manifest.json`, `rendered.mp4`).
- **What to say**:
  > *"Finally, every session exports 5 reproducible artifacts including OpenTimelineIO (`.otio`) for DaVinci Resolve or Premiere, and `manifest.json` detailing our $0.00 local inference cost and commercial MIT/Apache-2.0 licenses.  
  > All evidence is indexed in `test_pack/EVIDENCE_INDEX.md` and `Assessment2_Repalle_Gnaneswar.xlsx`.  
  > Thank you!"*

---

## 4. Final Submission Checklist Before Sending Email

- [ ] Paste your Live Demo URL in cell `C9` of `1_Your_Details` in `Assessment2_Repalle_Gnaneswar.xlsx`.
- [ ] Paste your Private GitHub Repo URL in cell `C12` of `1_Your_Details`.
- [ ] Paste your 8-min Demo Video URL in cell `C13` of `1_Your_Details`.
- [ ] Confirm your Phone number in cell `C6` of `1_Your_Details`.
- [ ] Save the workbook and attach `Assessment2_Repalle_Gnaneswar.xlsx` to your reply to the invitation email before the deadline.
