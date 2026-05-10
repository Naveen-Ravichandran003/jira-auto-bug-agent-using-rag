"""
AI Agent Orchestrator
Top-level coordinator that manages the full bug generation workflow.
Follows bug_generation_sop.md strictly.
"""

import os
import sys
import shutil
from datetime import datetime, timezone
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from loguru import logger
from src.config import settings, ensure_directories, mask_token
from src.schemas import (
    BugGenerationRequest,
    BugGenerationResponse,
    JiraTicketPayload,
    FieldConfidence,
    GenerationStatus,
    INSUFFICIENT_EVIDENCE_MSG,
)
from src.rag_pipeline import RAGPipeline
from tools.validate_jira_connection import full_validation
from tools.validate_payload_schema import validate_payload
from tools.create_jira_issue import create_issue, attach_file_to_issue


class BugAgent:
    """
    Enterprise AI Agent for Jira bug generation.

    Orchestrates the complete workflow:
    1. Validate credentials
    2. Process evidence through RAG pipeline
    3. Validate generated payload
    4. Optionally submit to Jira

    Anti-hallucination rules are enforced at every stage.
    """

    def __init__(self):
        self.pipeline = RAGPipeline()
        ensure_directories()

    def validate_connection(
        self, base_url: str, email: str, api_token: str, project_key: str
    ) -> dict:
        """
        Validate Jira connection before any operations.
        This MUST succeed before bug generation can proceed.
        """
        logger.info(f"Validating Jira connection for {email}")
        result = full_validation(base_url, email, api_token, project_key)

        if result["success"]:
            logger.info(
                f"✅ Connection validated — User: {result.get('user_display_name')}, "
                f"Project: {result.get('project_name')}"
            )
        else:
            logger.error(
                f"❌ Connection failed at step: {result.get('step_failed')} — "
                f"{result.get('error')}"
            )

        return result

    def generate_bug(
        self,
        request: BugGenerationRequest,
        auto_submit: bool = False,
    ) -> BugGenerationResponse:
        """
        Full bug generation workflow.

        Steps:
        1. Validate credentials
        2. Save evidence to temp directory
        3. Run RAG pipeline
        4. Validate payload
        5. Build response
        6. Optionally submit to Jira

        Args:
            request: Complete bug generation request
            auto_submit: Submit to Jira if confidence >= threshold

        Returns:
            BugGenerationResponse with payload, confidence, and status
        """
        user_id = request.user_id
        creds = request.jira_credentials
        evidence = request.evidence
        rules = request.bug_generation_rules

        logger.info(f"=== Bug Generation Started — User: {user_id} ===")

        # ── Step 1: Validate Jira credentials ──
        conn_result = self.validate_connection(
            creds.base_url, creds.email, creds.api_token, creds.project_key
        )
        if not conn_result["success"]:
            return BugGenerationResponse(
                jira_ticket_payload=JiraTicketPayload(
                    summary="Connection Failed",
                    description=conn_result.get("error", "Jira connection failed"),
                ),
                generation_status=GenerationStatus.FAILED,
                warnings=[conn_result.get("error", "Connection validation failed")],
            )

        # ── Step 2: Process evidence through RAG pipeline ──
        pipeline_result = self.pipeline.process_evidence(
            evidence_type=evidence.type.value,
            user_id=user_id,
            file_path=evidence.file_path,
            text_description=evidence.text_description,
            jira_ticket_key=evidence.jira_ticket_key,
            jira_base_url=creds.base_url,
            jira_email=creds.email,
            jira_api_token=creds.api_token,
            groq_api_key=creds.groq_api_key,
            use_rag=rules.use_rag,
            llm_model=rules.llm_model,
            custom_prompt=rules.custom_prompt,
        )

        if not pipeline_result.get("success"):
            status = pipeline_result.get("generation_status", "failed")
            return BugGenerationResponse(
                jira_ticket_payload=JiraTicketPayload(
                    summary="Generation Failed",
                    description=pipeline_result.get("error", "Pipeline failed"),
                ),
                generation_status=GenerationStatus(status),
                warnings=[pipeline_result.get("error", "")],
            )

        # ── Step 3: Build validated response ──
        payload = pipeline_result["payload"]
        confidence = pipeline_result["confidence_score"]
        gen_status = pipeline_result["generation_status"]

        # Build ticket payload from generated data
        ticket = JiraTicketPayload(
            summary=payload.get("summary", INSUFFICIENT_EVIDENCE_MSG),
            description=payload.get("description", INSUFFICIENT_EVIDENCE_MSG),
            steps_to_reproduce=payload.get("steps_to_reproduce", INSUFFICIENT_EVIDENCE_MSG),
            actual_result=payload.get("actual_result", INSUFFICIENT_EVIDENCE_MSG),
            expected_result=payload.get("expected_result", INSUFFICIENT_EVIDENCE_MSG),
            priority=payload.get("priority", INSUFFICIENT_EVIDENCE_MSG),
        )

        # Build field confidence
        fc = pipeline_result.get("field_confidence", {})
        field_confidence = FieldConfidence(
            summary=fc.get("summary", 0.0),
            description=fc.get("description", 0.0),
            steps_to_reproduce=fc.get("steps_to_reproduce", 0.0),
            actual_result=fc.get("actual_result", 0.0),
            expected_result=fc.get("expected_result", 0.0),
            priority=fc.get("priority", 0.0),
        )

        response = BugGenerationResponse(
            jira_ticket_payload=ticket,
            evidence_trace=pipeline_result.get("evidence_trace", []),
            confidence_score=confidence,
            generation_status=GenerationStatus(gen_status),
            field_confidence=field_confidence,
            warnings=pipeline_result.get("warnings", []),
            evidence_file_path=evidence.file_path,
        )

        # ── Step 4: Auto-submit if enabled and confidence passes ──
        if auto_submit and confidence >= rules.confidence_threshold:
            submit_result = self.submit_to_jira(
                creds=creds,
                payload=payload,
                confidence_score=confidence,
                evidence_trace=pipeline_result.get("evidence_trace", []),
                evidence_file_path=evidence.file_path,
            )

            if submit_result.get("success"):
                response.jira_issue_key = submit_result.get("issue_key")
                response.jira_issue_url = submit_result.get("issue_url")
                logger.info(f"✅ Auto-submitted: {response.jira_issue_key}")
            else:
                response.warnings.append(
                    f"Auto-submit failed: {submit_result.get('error')}"
                )

        elif auto_submit and confidence < rules.confidence_threshold:
            response.warnings.append(
                f"Auto-submit skipped: confidence ({confidence:.2%}) below "
                f"threshold ({rules.confidence_threshold:.2%}). Manual review required."
            )

        logger.info(
            f"=== Bug Generation Complete — Status: {gen_status}, "
            f"Confidence: {confidence:.3f} ==="
        )

        return response

    def submit_to_jira(
        self,
        creds,
        payload: dict,
        confidence_score: float,
        evidence_trace: list,
        evidence_file_path: Optional[str] = None,
    ) -> dict:
        """
        Submit the generated bug to Jira.
        Called explicitly by the user or auto-submit.
        """
        logger.info("Submitting bug to Jira...")

        result = create_issue(
            base_url=creds.base_url,
            email=creds.email,
            api_token=creds.api_token,
            project_key=creds.project_key,
            bug_payload=payload,
            confidence_score=confidence_score,
            evidence_trace=evidence_trace,
        )

        # Attach evidence file if submission succeeded and file exists
        if (
            result.get("success")
            and evidence_file_path
            and os.path.exists(evidence_file_path)
        ):
            attach_result = attach_file_to_issue(
                base_url=creds.base_url,
                email=creds.email,
                api_token=creds.api_token,
                issue_key=result["issue_key"],
                file_path=evidence_file_path,
            )
            if not attach_result.get("success"):
                logger.warning(
                    f"Evidence attachment failed: {attach_result.get('error')}"
                )

        return result

    def cleanup_user_session(self, user_id: str):
        """
        Clean up temporary files and data for a user session.
        """
        # Clean temp directory
        user_tmp = os.path.join(settings.tmp_dir, user_id)
        if os.path.exists(user_tmp):
            shutil.rmtree(user_tmp)
            logger.info(f"Cleaned temp directory for user: {user_id}")

        # Clear user data from vector store
        try:
            self.pipeline.store.clear_user_data(user_id)
        except Exception as e:
            logger.warning(f"Could not clear vector store data: {str(e)}")
