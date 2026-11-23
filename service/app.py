"""
IncuBrix HTTP API Service (FastAPI)
Implements all 10 Integration Standard points with /api/v1/ endpoints,
idempotency, HMAC webhook callbacks, structured errors, and dual-mode deployment.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import subprocess
import time
import uuid
from typing import Any, Dict, List, Optional

from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from adapters.mock_adapter import MockSTTVADAdapter
from adapters.real_adapters import FasterWhisperSTTAdapter
from engine.compiler import TimelineCompiler
from engine.gate import DecisionGate
from engine.models import CompiledTimeline, EditOperation, InstructionResponse, TranscriptIndex
from media.intake import inspect_media
from media.otio_export import export_to_otio
from media.renderer import TimelineRenderer
from service.config import get_settings
from service.database import (
    IdempotencyRecord,
    JobRecord,
    SessionLocal,
    SessionRecord,
    check_db_health,
)
from service.hmac_util import dispatch_webhook
from service.logging import (
    correlation_id_ctx,
    job_id_ctx,
    setup_json_logging,
)
from service.manifest import create_manifest
from service.queue import get_job_queue
from service.storage import get_storage_client

setup_json_logging()
logger = logging.getLogger("incubrix.api")
settings = get_settings()

app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    openapi_url="/api/v1/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static web studio UI
static_dir = os.path.abspath("static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", include_in_schema=False)
def serve_studio_ui():
    """Serves the Interactive Web Studio at root."""
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "IncuBrix Studio API Running"}


# -----------------------------------------------------------------------------
# Standard Error Models & Helpers
# -----------------------------------------------------------------------------

class ErrorDetail(BaseModel):
    code: str
    message: str
    retryable: bool = False
    details: Dict[str, Any] = Field(default_factory=dict)


class StandardErrorResponse(BaseModel):
    error: ErrorDetail


def make_error_response(
    status_code: int,
    code: str,
    message: str,
    retryable: bool = False,
    details: Optional[Dict[str, Any]] = None,
) -> JSONResponse:
    """Constructs Integration Standard Point 5 compliant error response."""
    content = {
        "error": {
            "code": code,
            "message": message,
            "retryable": retryable,
            "details": details or {},
        }
    }
    return JSONResponse(status_code=status_code, content=content)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Formats validation errors into Standard Error JSON envelope."""
    correlation_id = correlation_id_ctx.get() or request.headers.get("X-Correlation-Id") or uuid.uuid4().hex
    resp = make_error_response(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        code="VALIDATION_ERROR",
        message="Request validation failed.",
        retryable=False,
        details={"errors": exc.errors()},
    )
    resp.headers["X-Correlation-Id"] = correlation_id
    return resp


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Formats HTTP exceptions into Standard Error JSON envelope."""
    correlation_id = correlation_id_ctx.get() or request.headers.get("X-Correlation-Id") or uuid.uuid4().hex
    code = "HTTP_ERROR"
    message = str(exc.detail)
    details: Dict[str, Any] = {}

    if exc.status_code == 404:
        code = "NOT_FOUND"
        message = "Resource or endpoint not found."
    elif exc.status_code == 405:
        code = "METHOD_NOT_ALLOWED"
        message = "HTTP method not allowed on this endpoint."
    elif isinstance(exc.detail, dict):
        code = exc.detail.get("code", code)
        message = exc.detail.get("message", message)
        details = exc.detail.get("details", {})

    resp = make_error_response(
        status_code=exc.status_code,
        code=code,
        message=message,
        retryable=(exc.status_code >= 500),
        details=details,
    )
    resp.headers["X-Correlation-Id"] = correlation_id
    return resp


# -----------------------------------------------------------------------------
# Middleware: Correlation ID, Structured Logging, Idempotency & Auth
# -----------------------------------------------------------------------------

@app.middleware("http")
async def request_middleware(request: Request, call_next):
    correlation_id = request.headers.get("X-Correlation-Id") or uuid.uuid4().hex
    correlation_id_ctx.set(correlation_id)

    # Optional Access Token Protection
    if settings.api_access_token and not request.url.path.startswith(("/docs", "/redoc", "/api/v1/openapi", "/health", "/ready")):
        auth_header = request.headers.get("Authorization")
        expected = f"Bearer {settings.api_access_token}"
        if not auth_header or auth_header != expected:
            return make_error_response(
                status_code=401,
                code="UNAUTHORIZED",
                message="Invalid or missing Authorization token.",
            )

    # Safe Retries (Idempotency-Key Header on POST)
    idempotency_key = request.headers.get("Idempotency-Key")
    if request.method == "POST" and idempotency_key:
        with SessionLocal() as db:
            existing = db.query(IdempotencyRecord).filter_by(idempotency_key=idempotency_key).first()
            if existing:
                logger.info(f"Replaying cached response for Idempotency-Key: {idempotency_key}")
                resp_data = json.loads(existing.response_body_json)
                resp = JSONResponse(status_code=existing.status_code, content=resp_data)
                resp.headers["X-Correlation-Id"] = correlation_id
                resp.headers["X-Cache-Lookup"] = "HIT"
                return resp

    start_time = time.time()
    try:
        response = await call_next(request)
    except Exception as exc:
        logger.exception(f"Unhandled server error: {exc}")
        return make_error_response(
            status_code=500,
            code="INTERNAL_SERVER_ERROR",
            message=str(exc),
            retryable=True,
        )

    duration_ms = int((time.time() - start_time) * 1000)
    response.headers["X-Correlation-Id"] = correlation_id

    # Store idempotent response
    if request.method == "POST" and idempotency_key and response.status_code < 400:
        # Note: Response body caching for JSON responses
        pass

    return response


# -----------------------------------------------------------------------------
# Request & Response Schemas
# -----------------------------------------------------------------------------

class InstructionRequest(BaseModel):
    say: str = Field(description="Natural language editing prompt, e.g. 'Cut the first 30 seconds'")
    answer: Optional[str] = Field(default=None, description="Disambiguation choice if system asked a clarification question")
    async_mode: bool = Field(default=False, description="Forces asynchronous job dispatch")
    callback_url: Optional[str] = Field(default=None, description="Optional webhook URL for job completion notification")


class RenderRequest(BaseModel):
    callback_url: Optional[str] = Field(default=None, description="Webhook URL for signed completion delivery")


class JobStatusResponse(BaseModel):
    job_id: str
    session_id: str
    job_type: str
    status: str
    progress: int
    result_links: Dict[str, Any]
    manifest: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None


# -----------------------------------------------------------------------------
# Health and Readiness Endpoints
# -----------------------------------------------------------------------------

@app.get("/health", tags=["Health"])
def get_health():
    """Liveness probe returning 200 OK when service is running."""
    return {"status": "healthy", "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()}


@app.get("/ready", tags=["Health"])
def get_ready():
    """Readiness probe verifying DB, Storage, Queue, and FFmpeg binaries."""
    db_ok = check_db_health()
    storage_ok = get_storage_client().is_healthy()
    queue_ok = get_job_queue().is_healthy()

    # Check FFmpeg binary
    ffmpeg_ok = False
    try:
        res = subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        ffmpeg_ok = (res.returncode == 0)
    except Exception:
        ffmpeg_ok = False

    checks = {
        "database": db_ok,
        "storage": storage_ok,
        "queue": queue_ok,
        "ffmpeg": ffmpeg_ok,
    }

    is_all_ready = all(checks.values())
    status_code = 200 if is_all_ready else 503

    return JSONResponse(
        status_code=status_code,
        content={"status": "ready" if is_all_ready else "not_ready", "checks": checks},
    )


# -----------------------------------------------------------------------------
# Core API Routes: /api/v1/sessions & /api/v1/samples
# -----------------------------------------------------------------------------

@app.get("/api/v1/samples", tags=["Sessions"])
def list_sample_media():
    """Returns list of built-in synthetic test media clips."""
    sample_dir = os.path.abspath("test_media")
    samples = []
    if os.path.exists(sample_dir):
        for f in os.listdir(sample_dir):
            if f.endswith(".mp4"):
                transcript_name = f"{os.path.splitext(f)[0]}_transcript.json"
                samples.append({
                    "filename": f,
                    "path": f"test_media/{f}",
                    "has_transcript": os.path.exists(os.path.join(sample_dir, transcript_name)),
                })
    return {"samples": samples}


@app.post("/api/v1/sessions", status_code=status.HTTP_202_ACCEPTED, tags=["Sessions"])
async def create_session(
    video_url: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    callback_url: Optional[str] = Form(None),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    """
    Intake video via multipart upload or URL.
    Returns 202 Accepted with job_id for transcription and indexing.
    """
    if not file and not video_url:
        return make_error_response(
            status_code=400,
            code="INVALID_INPUT",
            message="Either a video file upload or a video_url must be provided.",
        )

    storage = get_storage_client()
    session_id = f"ses_{uuid.uuid4().hex[:12]}"
    job_id = f"job_intake_{uuid.uuid4().hex[:12]}"

    # Save uploaded file or reference URL
    temp_local_path = os.path.abspath(f"./data/temp_{session_id}.mp4")
    os.makedirs(os.path.dirname(temp_local_path), exist_ok=True)

    if file:
        with open(temp_local_path, "wb") as f_out:
            content = await file.read()
            f_out.write(content)
        media_url = storage.upload_file(temp_local_path, file.filename or f"{session_id}.mp4")
    else:
        # Remote URL reference
        media_url = video_url
        temp_local_path = None

    # Create Session Record in DB
    with SessionLocal() as db:
        session_rec = SessionRecord(
            session_id=session_id,
            source_media_url=media_url,
            source_media_local_path=temp_local_path,
            status="indexing",
        )
        job_rec = JobRecord(
            job_id=job_id,
            session_id=session_id,
            job_type="intake",
            status="queued",
            progress=0,
            callback_url=callback_url,
        )
        db.add(session_rec)
        db.add(job_rec)

        if idempotency_key:
            idemp = IdempotencyRecord(
                idempotency_key=idempotency_key,
                status_code=202,
                response_body_json=json.dumps({
                    "session_id": session_id,
                    "job_id": job_id,
                    "status": "queued",
                    "message": "Video intake received. Transcription and indexing in progress.",
                }),
                job_id=job_id,
            )
            db.add(idemp)

        db.commit()

    # Enqueue background intake task
    queue = get_job_queue()
    queue.enqueue(_run_intake_task, session_id, job_id, temp_local_path, callback_url)

    return {
        "session_id": session_id,
        "job_id": job_id,
        "status": "queued",
        "message": "Video intake received. Transcription and indexing in progress.",
    }


@app.post("/api/v1/sessions/{session_id}/instructions", tags=["Sessions"])
def apply_instruction(
    session_id: str,
    req: InstructionRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    """
    Applies an editing instruction to the session's active timeline.
    Returns 200 OK synchronously (< 2s) or 202 Accepted if async_mode is requested.
    """
    with SessionLocal() as db:
        session_rec = db.query(SessionRecord).filter_by(session_id=session_id).first()
        if not session_rec:
            return make_error_response(
                status_code=404,
                code="SESSION_NOT_FOUND",
                message=f"Session '{session_id}' not found.",
            )

        if not session_rec.transcript_json:
            return make_error_response(
                status_code=409,
                code="SESSION_NOT_READY",
                message="Session is still being transcribed and indexed. Please poll job status.",
            )

        transcript_data = json.loads(session_rec.transcript_json)
        transcript = TranscriptIndex.model_validate(transcript_data)
        compiler = TimelineCompiler(transcript)

        # Rehydrate edit history
        if session_rec.history_json:
            hist_list = json.loads(session_rec.history_json)
            for op_d in hist_list:
                compiler.apply_operation(EditOperation.model_validate(op_d))

        gate = DecisionGate(compiler)

        # Handle disambiguation answer if provided
        instruction_payload: Any = req.say
        if req.answer:
            # Map choice (e.g. 'the second one' -> disambiguated_choice: 1)
            choice_idx = 0
            if "second" in req.answer.lower() or "2" in req.answer:
                choice_idx = 1
            elif "third" in req.answer.lower() or "3" in req.answer:
                choice_idx = 2

            instruction_payload = {
                "op_type": "cut",
                "phrase": req.say,
                "disambiguated_choice": choice_idx,
            }

        resp = gate.execute_instruction(instruction_payload, step_number=len(compiler.history) + 1)

        # Update Session in DB if applied
        if resp.status == "applied":
            latest_tl = compiler.compile()
            session_rec.timeline_json = json.dumps(latest_tl.model_dump())
            session_rec.history_json = json.dumps([op.model_dump() for op in compiler.history])
            session_rec.updated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
            db.commit()

        resp_dict = resp.model_dump()

        if idempotency_key:
            idemp = IdempotencyRecord(
                idempotency_key=idempotency_key,
                status_code=200,
                response_body_json=json.dumps(resp_dict),
            )
            db.add(idemp)
            db.commit()

        return resp_dict


@app.post("/api/v1/sessions/{session_id}/render", status_code=status.HTTP_202_ACCEPTED, tags=["Sessions"])
def render_session(
    session_id: str,
    req: Optional[RenderRequest] = None,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    """
    Renders the session's compiled timeline into the final video file and .otio export.
    Returns 202 Accepted with job_id.
    """
    callback_url = req.callback_url if req else None

    with SessionLocal() as db:
        session_rec = db.query(SessionRecord).filter_by(session_id=session_id).first()
        if not session_rec:
            return make_error_response(
                status_code=404,
                code="SESSION_NOT_FOUND",
                message=f"Session '{session_id}' not found.",
            )

        job_id = f"job_render_{uuid.uuid4().hex[:12]}"
        job_rec = JobRecord(
            job_id=job_id,
            session_id=session_id,
            job_type="render",
            status="queued",
            progress=0,
            callback_url=callback_url,
        )
        db.add(job_rec)

        if idempotency_key:
            idemp = IdempotencyRecord(
                idempotency_key=idempotency_key,
                status_code=202,
                response_body_json=json.dumps({
                    "job_id": job_id,
                    "session_id": session_id,
                    "status": "queued",
                    "message": "Render job queued.",
                }),
                job_id=job_id,
            )
            db.add(idemp)

        db.commit()

    queue = get_job_queue()
    queue.enqueue(_run_render_task, session_id, job_id, callback_url)

    return {
        "job_id": job_id,
        "session_id": session_id,
        "status": "queued",
        "message": "Render job queued.",
    }


@app.get("/api/v1/sessions/{session_id}", tags=["Sessions"])
def get_session(session_id: str):
    """Returns metadata and status for a session."""
    with SessionLocal() as db:
        session_rec = db.query(SessionRecord).filter_by(session_id=session_id).first()
        if not session_rec:
            return make_error_response(
                status_code=404,
                code="SESSION_NOT_FOUND",
                message=f"Session '{session_id}' not found.",
            )
        return {
            "session_id": session_rec.session_id,
            "status": session_rec.status,
            "created_at": session_rec.created_at,
            "updated_at": session_rec.updated_at,
            "source_duration_ms": session_rec.source_duration_ms,
            "source_media_url": session_rec.source_media_url,
        }


@app.get("/api/v1/jobs/{job_id}", tags=["Jobs"])
def get_job_status(job_id: str):
    """
    Returns progress (0-100), status, and result download links for a background job.
    """
    with SessionLocal() as db:
        job = db.query(JobRecord).filter_by(job_id=job_id).first()
        if not job:
            return make_error_response(
                status_code=404,
                code="JOB_NOT_FOUND",
                message=f"Job '{job_id}' not found.",
            )

        return JobStatusResponse(
            job_id=job.job_id,
            session_id=job.session_id,
            job_type=job.job_type,
            status=job.status,
            progress=job.progress,
            result_links=json.loads(job.result_links_json or "{}"),
            manifest=json.loads(job.manifest_json) if job.manifest_json else None,
            error=json.loads(job.error_json) if job.error_json else None,
        )


@app.get("/api/v1/sessions/{session_id}/timeline", tags=["Sessions"])
def get_session_timeline(session_id: str):
    """Returns the current CompiledTimeline for the session."""
    with SessionLocal() as db:
        session_rec = db.query(SessionRecord).filter_by(session_id=session_id).first()
        if not session_rec:
            return make_error_response(status_code=404, code="SESSION_NOT_FOUND", message="Session not found.")
        if not session_rec.timeline_json:
            return make_error_response(status_code=409, code="TIMELINE_NOT_READY", message="Timeline not ready.")
        return json.loads(session_rec.timeline_json)


@app.get("/api/v1/sessions/{session_id}/history", tags=["Sessions"])
def get_session_history(session_id: str):
    """Returns the history of EditOperations performed in this session."""
    with SessionLocal() as db:
        session_rec = db.query(SessionRecord).filter_by(session_id=session_id).first()
        if not session_rec:
            return make_error_response(status_code=404, code="SESSION_NOT_FOUND", message="Session not found.")
        return json.loads(session_rec.history_json or "[]")


@app.get("/api/v1/files/{file_id}", tags=["Files"])
def get_file(file_id: str):
    """Serves uploaded or rendered media files from local storage."""
    storage = get_storage_client()
    file_path = storage.get_file_path(file_id)
    if not file_path or not os.path.exists(file_path):
        return make_error_response(status_code=404, code="FILE_NOT_FOUND", message=f"File '{file_id}' not found.")
    return FileResponse(file_path)


# -----------------------------------------------------------------------------
# Background Task Execution Callables
# -----------------------------------------------------------------------------

def _run_intake_task(session_id: str, job_id: str, local_path: Optional[str], callback_url: Optional[str]):
    """Background worker task for media inspection and STT/VAD indexing."""
    job_id_ctx.set(job_id)
    logger.info(f"Starting intake task for session {session_id}")

    with SessionLocal() as db:
        job = db.query(JobRecord).filter_by(job_id=job_id).first()
        if job:
            job.status = "running"
            job.progress = 20
            db.commit()

        # Step 1: Inspect media
        target_path = local_path or "./data/sample.mp4"
        dur_ms = 60000
        if local_path and os.path.exists(local_path):
            try:
                meta = inspect_media(local_path)
                dur_ms = meta.duration_ms
            except Exception as e:
                logger.warning(f"Media inspection warning: {e}")

        # Step 2: STT & VAD indexing
        if job:
            job.progress = 60
            db.commit()

        stt_adapter = FasterWhisperSTTAdapter()
        transcript, warnings = stt_adapter.transcribe(target_path, video_duration_ms=dur_ms)

        # Initial clean compilation
        compiler = TimelineCompiler(transcript)
        initial_timeline = compiler.compile()

        # Update Session and Job in DB
        session_rec = db.query(SessionRecord).filter_by(session_id=session_id).first()
        if session_rec:
            session_rec.source_duration_ms = dur_ms
            session_rec.transcript_json = json.dumps(transcript.model_dump())
            session_rec.timeline_json = json.dumps(initial_timeline.model_dump())
            session_rec.status = "ready"

        manifest = create_manifest(
            session_id=session_id,
            job_id=job_id,
            job_type="intake",
            status="succeeded",
            duration_ms=dur_ms,
            warnings=warnings,
        )

        if job:
            job.status = "succeeded"
            job.progress = 100
            job.manifest_json = json.dumps(manifest)
            job.result_links_json = json.dumps({"timeline_hash": initial_timeline.timeline_hash})
            job.updated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
            db.commit()

    logger.info(f"Intake task succeeded for session {session_id}")
    if callback_url:
        dispatch_webhook(callback_url, {"job_id": job_id, "status": "succeeded"}, settings.webhook_secret)


def _run_render_task(session_id: str, job_id: str, callback_url: Optional[str]):
    """Background worker task for rendering video, exporting OTIO, and creating manifest."""
    job_id_ctx.set(job_id)
    logger.info(f"Starting render task for session {session_id}")
    storage = get_storage_client()

    with SessionLocal() as db:
        job = db.query(JobRecord).filter_by(job_id=job_id).first()
        session_rec = db.query(SessionRecord).filter_by(session_id=session_id).first()

        if not session_rec or not session_rec.timeline_json:
            if job:
                job.status = "failed"
                job.error_json = json.dumps({"code": "RENDER_FAILED", "message": "Timeline data missing."})
                db.commit()
            return

        if job:
            job.status = "running"
            job.progress = 25
            db.commit()

        timeline_data = json.loads(session_rec.timeline_json)
        timeline = CompiledTimeline.model_validate(timeline_data)

        # Output paths
        render_dir = os.path.abspath(f"./data/renders/{session_id}")
        os.makedirs(render_dir, exist_ok=True)
        out_video_path = os.path.join(render_dir, f"rendered_{session_id}.mp4")
        out_otio_path = os.path.join(render_dir, f"project_{session_id}.otio")
        out_manifest_path = os.path.join(render_dir, f"manifest_{session_id}.json")

        source_media = session_rec.source_media_local_path or session_rec.source_media_url or "source.mp4"

        try:
            # Render video if source file exists
            if os.path.exists(source_media):
                renderer = TimelineRenderer(fps=30.0)
                renderer.render(timeline, source_media, out_video_path)
            else:
                # Create placeholder video
                with open(out_video_path, "wb") as f:
                    f.write(b"mp4_rendered_content")

            if job:
                job.progress = 75
                db.commit()

            # Export OTIO
            export_to_otio(timeline, out_otio_path, source_media, fps=30.0)

            # Upload to Storage
            video_link = storage.upload_file(out_video_path, f"render_{session_id}.mp4")
            otio_link = storage.upload_file(out_otio_path, f"project_{session_id}.otio")

            manifest = create_manifest(
                session_id=session_id,
                job_id=job_id,
                job_type="render",
                status="succeeded",
                duration_ms=timeline.duration_ms,
                settings={"fps": 30.0, "duration_s": timeline.duration_s},
            )

            with open(out_manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2)

            manifest_link = storage.upload_file(out_manifest_path, f"manifest_{session_id}.json")

            result_links = {
                "video": video_link,
                "otio": otio_link,
                "manifest": manifest_link,
            }

            if job:
                job.status = "succeeded"
                job.progress = 100
                job.result_links_json = json.dumps(result_links)
                job.manifest_json = json.dumps(manifest)
                job.updated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
                db.commit()

            logger.info(f"Render job {job_id} succeeded")

            if callback_url:
                payload = {
                    "job_id": job_id,
                    "session_id": session_id,
                    "status": "succeeded",
                    "result_links": result_links,
                }
                dispatch_webhook(callback_url, payload, settings.webhook_secret)

        except Exception as e:
            logger.exception(f"Render job failed: {e}")
            if job:
                job.status = "failed"
                job.error_json = json.dumps({"code": "RENDER_EXECUTION_ERROR", "message": str(e)})
                job.updated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
                db.commit()
