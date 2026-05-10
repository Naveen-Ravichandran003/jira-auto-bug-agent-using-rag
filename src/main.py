"""
FastAPI Application — Jira Auto-Bug Mapping AI Agent
Enterprise REST API server with CORS, file upload, and structured endpoints.
"""

import os
import sys
import uuid
import shutil
from datetime import datetime, timezone
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from loguru import logger
from pydantic import BaseModel

from src.config import settings, ensure_directories
from src.schemas import (
    BugGenerationRequest,
    BugGenerationResponse,
    JiraCredentials,
    Evidence,
    EvidenceType,
    BugGenerationRules,
    ConnectionTestResult,
)
from src.agent import BugAgent

# ─── App Initialization ─────────────────────────────────

app = FastAPI(
    title="Jira Auto-Bug Mapping AI Agent",
    description="Enterprise AI agent that generates structured Jira bug tickets from evidence with anti-hallucination enforcement.",
    version="1.0.0",
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files for UI
UI_DIR = os.path.join(os.path.dirname(__file__), "..", "ui")
if os.path.exists(UI_DIR):
    app.mount("/static", StaticFiles(directory=UI_DIR), name="static")

# Agent singleton
agent = BugAgent()

# Ensure directories exist
ensure_directories()


# ─── Request/Response Models ────────────────────────────

class TestConnectionRequest(BaseModel):
    base_url: str
    email: str
    api_token: str
    project_key: str


class SubmitBugRequest(BaseModel):
    base_url: str
    email: str
    api_token: str
    project_key: str
    payload: dict
    confidence_score: float = 0.0
    evidence_trace: list = []
    evidence_file_path: Optional[str] = None


# ─── API Endpoints ──────────────────────────────────────

@app.get("/")
async def serve_ui():
    """Serve the enterprise UI."""
    index_path = os.path.join(UI_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Jira Auto-Bug Mapping AI Agent API", "version": "1.0.0"}


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0",
    }


@app.post("/api/test-connection")
async def test_connection(req: TestConnectionRequest):
    """
    Test Jira connection with provided credentials.
    Validates auth, project access, and lists available projects.
    """
    logger.info(f"Testing connection for {req.email}")
    result = agent.validate_connection(
        base_url=req.base_url,
        email=req.email,
        api_token=req.api_token,
        project_key=req.project_key,
    )
    return result


@app.post("/api/generate-bug")
async def generate_bug(
    base_url: str = Form(...),
    email: str = Form(...),
    api_token: str = Form(...),
    project_key: str = Form(...),
    evidence_type: str = Form(...),
    text_description: Optional[str] = Form(None),
    jira_ticket_key: Optional[str] = Form(None),
    groq_api_key: Optional[str] = Form(None),
    llm_model: Optional[str] = Form("llama-3.3-70b-versatile"),
    custom_prompt: Optional[str] = Form(None),
    auto_submit: str = Form("false"),
    use_rag: str = Form("true"),
    use_ai: str = Form("true"),
    file: Optional[UploadFile] = File(None),
):
    """
    Generate a bug report from uploaded evidence.

    Accepts multipart form data with file upload.
    Runs the full RAG pipeline with anti-hallucination enforcement.
    """
    user_id = str(uuid.uuid4())[:8]
    # --- Helper to parse boolean from Form strings ---
    def parse_bool(val: str, default: bool) -> bool:
        if not val: return default
        return str(val).lower() == "true"

    submit_checked = parse_bool(auto_submit, False)
    rag_checked = parse_bool(use_rag, False)
    ai_checked = parse_bool(use_ai, True)

    # Save uploaded file if present
    file_path = None
    if file and file.filename:
        user_tmp = os.path.join(settings.tmp_dir, user_id)
        os.makedirs(user_tmp, exist_ok=True)
        file_path = os.path.join(user_tmp, file.filename)

        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        logger.info(f"Saved upload: {file.filename} ({len(content)} bytes)")

    # Build request
    try:
        request = BugGenerationRequest(
            user_id=user_id,
            jira_credentials=JiraCredentials(
                base_url=base_url,
                email=email,
                api_token=api_token,
                project_key=project_key,
                groq_api_key=groq_api_key,
            ),
            evidence=Evidence(
                type=EvidenceType(evidence_type),
                file_path=file_path,
                text_description=text_description,
                jira_ticket_key=jira_ticket_key,
            ),
            bug_generation_rules=BugGenerationRules(
                use_rag=rag_checked,
                use_ai=ai_checked,
                llm_model=llm_model,
                custom_prompt=custom_prompt
            ),
        )

        # Run the agent
        response = agent.generate_bug(request, auto_submit=submit_checked)

        return response.model_dump()

    except Exception as e:
        logger.error(f"Bug generation error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/submit-bug")
async def submit_bug(req: SubmitBugRequest):
    """
    Submit a generated (and optionally edited) bug report to Jira.
    Called when user clicks "Create Jira Bug" after reviewing the preview.
    """
    logger.info("Submitting bug to Jira...")

    creds = JiraCredentials(
        base_url=req.base_url,
        email=req.email,
        api_token=req.api_token,
        project_key=req.project_key,
    )

    result = agent.submit_to_jira(
        creds=creds,
        payload=req.payload,
        confidence_score=req.confidence_score,
        evidence_trace=req.evidence_trace,
        evidence_file_path=req.evidence_file_path,
    )

    return result


@app.get("/api/config")
async def get_config():
    """Get non-sensitive configuration values."""
    from src.config import get_ocr_status
    return {
        "chunk_size": settings.chunk_size,
        "chunk_overlap": settings.chunk_overlap,
        "top_k": settings.top_k,
        "similarity_threshold": settings.similarity_threshold,
        "confidence_threshold": settings.confidence_threshold,
        "supported_evidence_types": [e.value for e in EvidenceType],
        "ocr_status": get_ocr_status(),
    }


# ─── Startup ────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    logger.info("Starting Jira Auto-Bug Mapping AI Agent...")
    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
