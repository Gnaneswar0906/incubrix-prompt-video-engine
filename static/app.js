/**
 * IncuBrix Studio Front-End Application
 * Powers word-anchored timeline visualization, natural-language editing,
 * three-way response cards with clickable clarification options, and live rendering.
 */

// Application State
let currentSessionId = null;
let currentTimeline = null;
let currentTranscript = null;
let editHistory = [];
let pollInterval = null;

// DOM Elements
const backendStatus = document.getElementById('backendStatus');
const backendStatusText = document.getElementById('backendStatusText');
const samplePicker = document.getElementById('samplePicker');
const sessionIdBadge = document.getElementById('sessionIdBadge');
const btnLoadSession = document.getElementById('btnLoadSession');
const loadSpinner = document.getElementById('loadSpinner');
const instructionInput = document.getElementById('instructionInput');
const btnSendInstruction = document.getElementById('btnSendInstruction');
const responseFeed = document.getElementById('responseFeed');
const historyCount = document.getElementById('historyCount');
const wordStream = document.getElementById('wordStream');
const timelineDurationText = document.getElementById('timelineDurationText');
const timelineWordCount = document.getElementById('timelineWordCount');
const timelineHashBadge = document.getElementById('timelineHashBadge');
const btnRender = document.getElementById('btnRender');
const progressSection = document.getElementById('progressSection');
const progressBarFill = document.getElementById('progressBarFill');
const progressStatusText = document.getElementById('progressStatusText');
const progressPercentText = document.getElementById('progressPercentText');
const videoPlayer = document.getElementById('videoPlayer');
const videoPlaceholder = document.getElementById('videoPlaceholder');
const exportTray = document.getElementById('exportTray');
const downloadVideoBtn = document.getElementById('downloadVideoBtn');
const downloadOtioBtn = document.getElementById('downloadOtioBtn');
const btnViewManifest = document.getElementById('btnViewManifest');
const btnViewTimeline = document.getElementById('btnViewTimeline');
const jsonModal = document.getElementById('jsonModal');
const modalTitle = document.getElementById('modalTitle');
const modalJsonContent = document.getElementById('modalJsonContent');
const modalCloseBtn = document.getElementById('modalCloseBtn');

let lastManifestData = null;

// -----------------------------------------------------------------------------
// Initialization & Health Checks
// -----------------------------------------------------------------------------

document.addEventListener('DOMContentLoaded', async () => {
  setupTabs();
  setupPresets();
  setupModal();
  await checkHealth();
});

async function checkHealth() {
  try {
    const res = await fetch('/ready');
    if (res.ok) {
      backendStatusText.textContent = 'Engine Ready';
      backendStatus.className = 'status-pill status-ready';
    } else {
      backendStatusText.textContent = 'Engine Busy/Degraded';
    }
  } catch (e) {
    backendStatusText.textContent = 'Backend Offline';
  }
}

// -----------------------------------------------------------------------------
// UI Tabs & Presets
// -----------------------------------------------------------------------------

function setupTabs() {
  const tabs = [
    { btn: document.getElementById('tabSampleBtn'), content: null },
    { btn: document.getElementById('tabUrlBtn'), content: document.getElementById('tabUrlContent') },
    { btn: document.getElementById('tabUploadBtn'), content: document.getElementById('tabUploadContent') },
  ];

  tabs.forEach(t => {
    t.btn.addEventListener('click', () => {
      tabs.forEach(o => {
        o.btn.classList.remove('active');
        if (o.content) o.content.style.display = 'none';
      });
      t.btn.classList.add('active');
      if (t.content) t.content.style.display = 'block';
    });
  });
}

function setupPresets() {
  const chips = document.querySelectorAll('.chip');
  chips.forEach(chip => {
    chip.addEventListener('click', () => {
      const prompt = chip.getAttribute('data-prompt');
      instructionInput.value = prompt;
      applyInstruction(prompt);
    });
  });

  btnSendInstruction.addEventListener('click', () => {
    const text = instructionInput.value.trim();
    if (text) applyInstruction(text);
  });

  instructionInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      const text = instructionInput.value.trim();
      if (text) applyInstruction(text);
    }
  });

  btnLoadSession.addEventListener('click', initializeSession);
  btnRender.addEventListener('click', triggerRender);
}

function setupModal() {
  modalCloseBtn.addEventListener('click', () => jsonModal.style.display = 'none');
  jsonModal.addEventListener('click', (e) => {
    if (e.target === jsonModal) jsonModal.style.display = 'none';
  });

  btnViewManifest.addEventListener('click', () => {
    modalTitle.textContent = 'manifest.json (Rich Output Manifest)';
    modalJsonContent.textContent = JSON.stringify(lastManifestData || { error: 'No manifest available' }, null, 2);
    jsonModal.style.display = 'flex';
  });

  btnViewTimeline.addEventListener('click', () => {
    modalTitle.textContent = 'compiled_timeline.json (Current Projected State)';
    modalJsonContent.textContent = JSON.stringify(currentTimeline || { error: 'No timeline compiled' }, null, 2);
    jsonModal.style.display = 'flex';
  });
}

// -----------------------------------------------------------------------------
// Session Intake Flow
// -----------------------------------------------------------------------------

async function initializeSession() {
  loadSpinner.style.display = 'inline-block';
  btnLoadSession.disabled = true;

  try {
    const activeTab = document.querySelector('.source-tabs .tab-btn.active').id;
    let body = new FormData();

    if (activeTab === 'tabSampleBtn') {
      const selectedSample = samplePicker.value;
      body.append('video_url', selectedSample);
    } else if (activeTab === 'tabUrlBtn') {
      const url = document.getElementById('customUrlInput').value.trim();
      body.append('video_url', url || 'https://example.com/demo.mp4');
    } else {
      const file = document.getElementById('fileUploadInput').files[0];
      if (file) {
        body.append('file', file);
      } else {
        body.append('video_url', 'test_media/single_speaker_interview.mp4');
      }
    }

    const res = await fetch('/api/v1/sessions', {
      method: 'POST',
      headers: {
        'Idempotency-Key': `ses_init_${Date.now()}`
      },
      body: body,
    });

    const data = await res.json();
    if (res.status === 202) {
      currentSessionId = data.session_id;
      sessionIdBadge.textContent = currentSessionId;
      await pollJob(data.job_id, 'Indexing & Transcribing Video...', async () => {
        await refreshTimeline();
        btnRender.disabled = false;
      });
    } else {
      alert(`Error creating session: ${JSON.stringify(data)}`);
    }
  } catch (err) {
    alert(`Failed to initialize session: ${err}`);
  } finally {
    loadSpinner.style.display = 'none';
    btnLoadSession.disabled = false;
  }
}

// -----------------------------------------------------------------------------
// Instruction Execution & Disambiguation
// -----------------------------------------------------------------------------

async function applyInstruction(sayText, answer = null) {
  if (!currentSessionId) {
    alert('Please initialize or load a video session first!');
    return;
  }

  try {
    const payload = { say: sayText };
    if (answer) payload.answer = answer;

    const res = await fetch(`/api/v1/sessions/${currentSessionId}/instructions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Idempotency-Key': `inst_${Date.now()}`
      },
      body: JSON.stringify(payload),
    });

    const data = await res.json();
    addResponseCard(sayText, data);
    await refreshTimeline();
  } catch (err) {
    console.error('Instruction error:', err);
  }
}

function addResponseCard(instruction, resp) {
  // Clear placeholder
  const placeholder = responseFeed.querySelector('.empty-feed-placeholder');
  if (placeholder) placeholder.remove();

  const card = document.createElement('div');
  const status = resp.status || 'applied';

  const cardTypeClass = status === 'needs_clarification' ? 'card-clarify card-needs_clarification' : `card-${status}`;
  card.className = `response-card ${cardTypeClass}`;

  let summaryHtml = '';
  if (status === 'applied') {
    summaryHtml = `
      <div class="card-summary">
        ${resp.summary?.what_moved || 'Instruction applied successfully.'}
        <br><small>Before: ${resp.summary?.before_duration_s}s → After: ${resp.summary?.after_duration_s}s | Policy: ${resp.summary?.time_policy}</small>
      </div>
    `;
  } else if (status === 'needs_clarification') {
    const optionsHtml = (resp.options || []).map(opt => `
      <button class="option-btn" onclick="submitClarificationChoice('${encodeURIComponent(instruction)}', '${encodeURIComponent(opt)}')">${opt}</button>
    `).join('');

    summaryHtml = `
      <div class="clarify-question">❓ ${resp.question || 'Disambiguation Required'}</div>
      <div class="clarify-options">${optionsHtml}</div>
    `;
  } else if (status === 'rejected') {
    const errCode = resp.summary?.error_code || 'INSTRUCTION_REJECTED';
    const errMsg = resp.summary?.message || resp.warnings?.join(', ') || 'Rule violation.';
    summaryHtml = `
      <div class="card-summary" style="color: #fca5a5;">
        <strong>[${errCode}]</strong> ${errMsg}
      </div>
    `;
  }

  card.innerHTML = `
    <div class="card-top">
      <span class="instruction-text">"${instruction}"</span>
      <span class="status-tag">${status.toUpperCase()}</span>
    </div>
    ${summaryHtml}
  `;

  responseFeed.prepend(card);
  editHistory.push(resp);
  historyCount.textContent = `${editHistory.length} Edits`;
}

window.submitClarificationChoice = function (encodedInstruction, encodedChoice) {
  const instruction = decodeURIComponent(encodedInstruction);
  const choice = decodeURIComponent(encodedChoice);
  applyInstruction(instruction, choice);
};

// -----------------------------------------------------------------------------
// Timeline Refresh & Visualization
// -----------------------------------------------------------------------------

async function refreshTimeline() {
  if (!currentSessionId) return;

  try {
    const res = await fetch(`/api/v1/sessions/${currentSessionId}/timeline`);
    if (!res.ok) return;

    currentTimeline = await res.json();
    renderTimelineVisualizer(currentTimeline);
  } catch (err) {
    console.error('Failed to refresh timeline:', err);
  }
}

function renderTimelineVisualizer(tl) {
  timelineDurationText.textContent = `${tl.duration_s.toFixed(1)}s`;
  timelineHashBadge.textContent = `SHA: ${tl.timeline_hash.slice(0, 12)}...`;
  timelineHashBadge.title = tl.timeline_hash;

  // Active word IDs in current compiled video segments
  const activeWordIds = new Set();
  const spedUpWordIds = new Set();
  const mutedWordIds = new Set();

  tl.video_segments.forEach(seg => {
    (seg.word_ids || []).forEach(wId => {
      activeWordIds.add(wId);
      if (seg.speed > 1.0) spedUpWordIds.add(wId);
      if (seg.is_muted) mutedWordIds.add(wId);
    });
  });

  // Map captions to their bound words
  const captionMap = new Map();
  (tl.caption_tracks || []).forEach(cap => {
    if (!cap.suppressed) {
      (cap.bound_word_ids || []).forEach(wId => {
        captionMap.set(wId, cap);
      });
    }
  });

  // Collect all unique words
  wordStream.innerHTML = '';
  let count = 0;

  // We retrieve session metadata or render words from timeline video segments
  tl.video_segments.forEach(seg => {
    (seg.word_ids || []).forEach(wId => {
      count++;
      const pill = document.createElement('div');
      const isSpedUp = spedUpWordIds.has(wId);
      const isCut = !activeWordIds.has(wId);

      pill.className = `word-pill speaker_0 ${isSpedUp ? 'sped-up' : ''} ${isCut ? 'cut' : ''}`;

      // Check if caption bound
      if (captionMap.has(wId)) {
        const cap = captionMap.get(wId);
        const capBadge = document.createElement('span');
        const isRed = cap.style?.color === 'red';
        capBadge.className = `caption-lock-badge ${isRed ? 'red' : ''}`;
        capBadge.textContent = cap.text;
        pill.appendChild(capBadge);
      }

      const textSpan = document.createElement('span');
      textSpan.textContent = wId;
      pill.appendChild(textSpan);

      const timeSpan = document.createElement('span');
      timeSpan.className = 'time-stamp';
      timeSpan.textContent = `${(seg.timeline_start_ms / 1000).toFixed(1)}s`;
      pill.appendChild(timeSpan);

      wordStream.appendChild(pill);
    });
  });

  timelineWordCount.textContent = count;
}

// -----------------------------------------------------------------------------
// Live Render & Export
// -----------------------------------------------------------------------------

async function triggerRender() {
  if (!currentSessionId) return;

  btnRender.disabled = true;
  progressSection.style.display = 'block';
  progressBarFill.style.width = '0%';
  progressPercentText.textContent = '0%';
  progressStatusText.textContent = 'Dispatching frame-accurate single-pass render...';

  try {
    const res = await fetch(`/api/v1/sessions/${currentSessionId}/render`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Idempotency-Key': `render_${Date.now()}`
      },
      body: JSON.stringify({}),
    });

    const data = await res.json();
    if (res.status === 202) {
      await pollJob(data.job_id, 'Rendering video & exporting OpenTimelineIO...', async (job) => {
        progressSection.style.display = 'none';
        btnRender.disabled = false;

        const links = job.result_links || {};
        if (links.video) {
          videoPlayer.src = links.video;
          videoPlayer.style.display = 'block';
          videoPlaceholder.style.display = 'none';
          downloadVideoBtn.href = links.video;
        }
        if (links.otio) {
          downloadOtioBtn.href = links.otio;
        }

        lastManifestData = job.manifest;
        exportTray.style.display = 'flex';
      });
    } else {
      alert(`Render error: ${JSON.stringify(data)}`);
      progressSection.style.display = 'none';
      btnRender.disabled = false;
    }
  } catch (err) {
    alert(`Render failed: ${err}`);
    progressSection.style.display = 'none';
    btnRender.disabled = false;
  }
}

// -----------------------------------------------------------------------------
// Polling Utility
// -----------------------------------------------------------------------------

async function pollJob(jobId, statusMessage, onComplete) {
  progressSection.style.display = 'block';
  progressStatusText.textContent = statusMessage;

  return new Promise((resolve, reject) => {
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`/api/v1/jobs/${jobId}`);
        const job = await res.json();

        const progress = job.progress || 0;
        progressBarFill.style.width = `${progress}%`;
        progressPercentText.textContent = `${progress}%`;

        if (job.status === 'succeeded') {
          clearInterval(interval);
          if (onComplete) await onComplete(job);
          resolve(job);
        } else if (job.status === 'failed') {
          clearInterval(interval);
          alert(`Job failed: ${JSON.stringify(job.error)}`);
          reject(new Error('Job failed'));
        }
      } catch (e) {
        clearInterval(interval);
        reject(e);
      }
    }, 400);
  });
}
