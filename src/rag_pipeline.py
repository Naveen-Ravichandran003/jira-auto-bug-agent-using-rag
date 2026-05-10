"""
RAG Pipeline Coordinator
Orchestrates the full evidence processing → retrieval → generation pipeline.
Follows rag_retrieval_sop.md strictly.
"""

import os
import sys
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from loguru import logger
from src.config import settings

# Import tools
from tools.extract_text_from_image import extract_text as ocr_extract
from tools.chunk_document import chunk_text
from tools.embed_chunks import get_store
from tools.retrieve_context import retrieve_context, format_context_for_llm
from tools.generate_bug_payload import generate_bug_payload

# PDF extraction
try:
    import pdfplumber

    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    logger.warning("pdfplumber not installed — PDF processing unavailable")

# Jira ticket fetch
import base64
import requests


class RAGPipeline:
    """
    Full RAG pipeline coordinator.

    Flow:
    Evidence → Text Extraction → Chunking → Embedding → Retrieval → Generation
    """

    def __init__(self):
        self.store = get_store()

    def process_evidence(
        self,
        evidence_type: str,
        user_id: str,
        file_path: Optional[str] = None,
        text_description: Optional[str] = None,
        jira_ticket_key: Optional[str] = None,
        jira_base_url: Optional[str] = None,
        jira_email: Optional[str] = None,
        jira_api_token: Optional[str] = None,
        groq_api_key: Optional[str] = None,
        use_rag: bool = False,
        llm_model: str = "llama-3.3-70b-versatile",
        custom_prompt: Optional[str] = None,
    ) -> dict:
        """
        Process evidence through the full RAG pipeline.

        Stage 1: Extract text from evidence
        Stage 2: Chunk the text
        Stage 3: Embed and index chunks
        Stage 4: Retrieve relevant context
        Stage 5: Generate bug payload

        Returns:
            dict with generated payload, confidence, and evidence trace
        """
        logger.info(f"RAG Pipeline started — type={evidence_type}, user={user_id}")

        # ──────────────────────────────────────────────────
        # STAGE 1: Text Extraction
        # ──────────────────────────────────────────────────
        raw_text = ""
        source_file = "user_input"

        if evidence_type == "screenshot":
            if not file_path or not os.path.exists(file_path):
                return self._abort("Screenshot file not found", "insufficient_data")

            result = ocr_extract(file_path)
            # OCR is now optional for screenshots because we have Groq Vision (Visual AI)
            if result.get("success") and result.get("text"):
                raw_text = result["text"]
                logger.info(f"OCR extracted {len(raw_text)} chars")
            else:
                logger.warning(f"OCR extracted no text, but continuing with Visual AI: {result.get('error', 'No text found')}")
                raw_text = "Image analysis pending (Visual AI will be used)."
            
            source_file = os.path.basename(file_path)

        elif evidence_type == "pdf":
            if not file_path or not os.path.exists(file_path):
                return self._abort("PDF file not found", "insufficient_data")

            raw_text = self._extract_pdf_text(file_path)
            if not raw_text:
                return self._abort("No text could be extracted from PDF", "insufficient_data")
            source_file = os.path.basename(file_path)
            logger.info(f"PDF extracted {len(raw_text)} chars")

        elif evidence_type == "jira_ticket":
            if not jira_ticket_key:
                return self._abort("Jira ticket key not provided", "insufficient_data")

            raw_text = self._fetch_jira_ticket(
                jira_base_url, jira_email, jira_api_token, jira_ticket_key
            )
            if not raw_text:
                return self._abort(
                    f"Could not fetch Jira ticket: {jira_ticket_key}",
                    "insufficient_data",
                )
            source_file = f"jira_{jira_ticket_key}"
            logger.info(f"Jira ticket fetched: {len(raw_text)} chars")

        elif evidence_type in ("text_description", "document"):
            raw_text = text_description or ""
            if not raw_text.strip():
                return self._abort("No text description provided", "insufficient_data")
            source_file = "user_description"
            logger.info(f"Text input: {len(raw_text)} chars")

        else:
            return self._abort(f"Unknown evidence type: {evidence_type}", "failed")

        # Combine evidence
        logger.info(f"Evidence trace: file={source_file} ({len(raw_text)} chars), description=({len(text_description or '')} chars)")
        if text_description and not raw_text:
            combined_text = text_description
        elif raw_text and not text_description:
            combined_text = raw_text
        else:
            combined_text = f"{raw_text}\n\n--- User Description ---\n{text_description}"

        logger.info(f"Combined evidence length: {len(combined_text)} chars")

        # Stage 2-4: RAG Flow (Optional Enhancement)
        # ──────────────────────────────────────────────────
        retrieved_chunks = []
        
        # Use RAG if user requested it (using local model if no key provided)
        if use_rag:
            # Stage 2: Chunking
            chunks = chunk_text(
                text=combined_text,
                source_file=source_file,
                source_type=evidence_type,
                user_id=user_id,
            )

            if chunks:
                logger.info(f"Created {len(chunks)} chunks for RAG")

                # Stage 3: Embedding & Indexing (Local/Free)
                try:
                    added = self.store.add_chunks_with_content(
                        chunks, persist=True
                    )
                    logger.info(f"Indexed {added} chunks in FAISS (Local)")
                    
                    # Stage 4: Retrieval (Local/Free)
                    query = text_description or raw_text[:500]
                    retrieval_result = retrieve_context(
                        query=query,
                        user_id=user_id
                    )

                    if retrieval_result.get("success"):
                        retrieved_chunks = retrieval_result["chunks"]
                        logger.info(f"Retrieved {len(retrieved_chunks)} relevant chunks")
                except Exception as e:
                    logger.warning(f"RAG Enhancement failed, falling back to full context: {str(e)}")

        # Fallback: If RAG was skipped or failed, send FULL evidence context (Smart Full-Context)
        if not retrieved_chunks:
            logger.info("Using Direct Full-Context analysis (No embedding required)")
            retrieved_chunks = [{
                "content": combined_text,
                "metadata": {
                    "chunk_id": "direct_evidence",
                    "source_file": source_file,
                },
                "similarity_score": 1.0
            }]

        # ──────────────────────────────────────────────────
        # STAGE 5: Constrained Generation (Groq/OpenAI)
        # ──────────────────────────────────────────────────
        # Pass image_path if it's a screenshot to trigger Vision model
        image_to_analyze = file_path if evidence_type == "screenshot" else None

        generation_result = generate_bug_payload(
            retrieved_chunks=retrieved_chunks,
            user_description=text_description or "",
            api_key_override=groq_api_key,
            model_override=llm_model,
            image_path=image_to_analyze,
            custom_prompt=custom_prompt,
        )

        if not generation_result.get("success"):
            return self._abort(
                f"Generation failed: {generation_result.get('error', 'Unknown')}",
                "failed",
            )

        # Determine status based on confidence
        confidence = generation_result["confidence_score"]
        if confidence >= settings.confidence_threshold:
            status = "success"
        elif confidence >= 0.5:
            status = "low_confidence"
        else:
            status = "insufficient_data"

        logger.info(
            f"RAG Pipeline complete — Status: {status}, "
            f"Confidence: {confidence:.3f}"
        )

        return {
            "success": True,
            "payload": generation_result["payload"],
            "confidence_score": confidence,
            "generation_status": status,
            "evidence_trace": generation_result.get("evidence_chunk_ids", []),
            "field_confidence": generation_result.get("field_confidence", {}),
            "warnings": generation_result.get("warnings", []),
            "retrieval_stats": {
                "chunks_retrieved": len(retrieved_chunks),
                "avg_similarity": 1.0 if not use_rag else retrieval_result.get("avg_similarity", 0.0),
                "rag_used": use_rag
            },
        }

    def _extract_pdf_text(self, file_path: str) -> str:
        """Extract text from a PDF using pdfplumber."""
        if not PDF_AVAILABLE:
            logger.error("pdfplumber not installed")
            return ""

        try:
            text_parts = []
            with pdfplumber.open(file_path) as pdf:
                for i, page in enumerate(pdf.pages):
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(f"[Page {i + 1}]\n{page_text}")

            return "\n\n".join(text_parts)
        except Exception as e:
            logger.error(f"PDF extraction failed: {str(e)}")
            return ""

    def _fetch_jira_ticket(
        self,
        base_url: str,
        email: str,
        api_token: str,
        ticket_key: str,
    ) -> str:
        """Fetch an existing Jira ticket's content as text."""
        if not all([base_url, email, api_token]):
            logger.error("Jira credentials required to fetch ticket")
            return ""

        url = f"{base_url.rstrip('/')}/rest/api/3/issue/{ticket_key}"
        credentials = f"{email}:{api_token}"
        encoded = base64.b64encode(credentials.encode()).decode()
        headers = {
            "Authorization": f"Basic {encoded}",
            "Accept": "application/json",
        }

        try:
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            data = response.json()

            fields = data.get("fields", {})
            parts = [
                f"Summary: {fields.get('summary', '')}",
                f"Status: {fields.get('status', {}).get('name', '')}",
                f"Priority: {fields.get('priority', {}).get('name', '')}",
                f"Issue Type: {fields.get('issuetype', {}).get('name', '')}",
            ]

            # Extract description text from ADF
            description = fields.get("description", {})
            if isinstance(description, dict):
                desc_text = self._adf_to_text(description)
                parts.append(f"Description:\n{desc_text}")
            elif isinstance(description, str):
                parts.append(f"Description:\n{description}")

            # Comments
            comments = fields.get("comment", {}).get("comments", [])
            if comments:
                comment_texts = []
                for c in comments[:5]:  # Limit to 5 most recent
                    body = c.get("body", {})
                    if isinstance(body, dict):
                        comment_texts.append(self._adf_to_text(body))
                    elif isinstance(body, str):
                        comment_texts.append(body)
                if comment_texts:
                    parts.append(f"Comments:\n" + "\n---\n".join(comment_texts))

            return "\n\n".join(parts)

        except Exception as e:
            logger.error(f"Failed to fetch Jira ticket {ticket_key}: {str(e)}")
            return ""

    def _adf_to_text(self, adf: dict) -> str:
        """Convert Atlassian Document Format to plain text."""
        if not isinstance(adf, dict):
            return str(adf)

        text_parts = []
        for block in adf.get("content", []):
            block_type = block.get("type", "")
            if block_type in ("paragraph", "heading"):
                for item in block.get("content", []):
                    if item.get("type") == "text":
                        text_parts.append(item.get("text", ""))
            elif block_type == "bulletList":
                for list_item in block.get("content", []):
                    for para in list_item.get("content", []):
                        for item in para.get("content", []):
                            if item.get("type") == "text":
                                text_parts.append(f"• {item.get('text', '')}")

        return "\n".join(text_parts)

    def _abort(self, message: str, status: str) -> dict:
        """Abort pipeline with error message."""
        logger.warning(f"Pipeline ABORT: {message}")
        return {
            "success": False,
            "error": message,
            "generation_status": status,
            "payload": None,
            "confidence_score": 0.0,
        }
