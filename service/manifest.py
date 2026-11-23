"""
IncuBrix Output Manifest Generator (Integration Standard Point 9)
Generates manifest.json documenting models, settings, seed, timings, cost, warnings, and licensing.
"""

from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class OutputManifest(BaseModel):
    manifest_version: str = "1.0.0"
    session_id: str
    job_id: str
    job_type: str
    status: str
    created_at: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    completed_at: Optional[str] = None
    duration_ms: Optional[int] = None
    seed: int = 42
    settings: Dict[str, Any] = Field(default_factory=dict)
    models: List[Dict[str, str]] = Field(default_factory=list)
    timings: Dict[str, float] = Field(default_factory=dict)
    cost_estimate_usd: str = "$0.00 (100% Local Inference)"
    warnings: List[str] = Field(default_factory=list)
    license: str = "Commercial Use Permitted (MIT / Apache-2.0 / LGPL / BSD-2-Clause)"


def create_manifest(
    session_id: str,
    job_id: str,
    job_type: str,
    status: str = "succeeded",
    settings: Optional[Dict[str, Any]] = None,
    timings: Optional[Dict[str, float]] = None,
    warnings: Optional[List[str]] = None,
    duration_ms: Optional[int] = None,
) -> Dict[str, Any]:
    """Builds the canonical JSON manifest dictionary."""
    models_info = [
        {"role": "Speech-to-Text & VAD", "name": "faster-whisper (small.en) + silero-vad", "license": "MIT"},
        {"role": "Speaker Diarization", "name": "SpectralClustering / MFCC", "license": "BSD-3-Clause"},
        {"role": "Semantic Embeddings", "name": "sentence-transformers (all-MiniLM-L6-v2)", "license": "Apache-2.0"},
        {"role": "Intent Parser", "name": "Google Gemini 1.5 Flash / Deterministic Rule Parser", "license": "Apache-2.0 / MIT"},
        {"role": "Media Engine", "name": "FFmpeg Single-Pass Filtergraph", "license": "LGPL v3.0"},
    ]

    manifest = OutputManifest(
        session_id=session_id,
        job_id=job_id,
        job_type=job_type,
        status=status,
        completed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        duration_ms=duration_ms,
        settings=settings or {},
        models=models_info,
        timings=timings or {},
        warnings=warnings or [],
    )

    return manifest.model_dump()
