"""
Tool: Generate Bug Payload
Uses constrained LLM generation with anti-hallucination enforcement
to create a structured Jira bug payload from retrieved evidence chunks.
"""

import os
import sys
import json
import base64
from typing import List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from loguru import logger
from src.config import settings
from tools.retrieve_context import format_context_for_llm

# Removed OpenAI imports completely
LLM_AVAILABLE = False

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False


# ─── Anti-Hallucination System Prompt ────────────────────────
SYSTEM_PROMPT = """You are a deterministic bug report extraction tool. Your goal is to map unstructured evidence into a structured Jira bug report.

STRICT RULES:
1. ONLY use information provided in the "EVIDENCE CONTEXT CHUNKS".
2. You MUST cite which chunk_id(s) support EACH field in the "evidence_chunk_ids" array.
3. If a field (like steps_to_reproduce) is found in the evidence, extract it exactly or summarize it accurately.
4. If a field is NOT in the chunks, use exactly: "Insufficient evidence provided to generate this section."
5. If there is only one chunk (e.g., 'direct_evidence'), and the information is there, cite ["direct_evidence"].
6. Do NOT assume anything. If priority isn't mentioned, set it to "Medium" but note it in warnings.
7. Return ONLY JSON.

JSON SCHEMA:
{
  "summary": "Short descriptive title",
  "description": "Comprehensive description including environment/context found",
  "steps_to_reproduce": "Number steps found in evidence or the 'Insufficient' message",
  "actual_result": "What happened vs what was expected",
  "expected_result": "What should have happened",
  "priority": "Highest, High, Medium, Low, or Lowest",
  "evidence_chunk_ids": ["chunk_id1", "chunk_id2"],
  "field_confidence": {
    "summary": 1.0, "description": 1.0, "steps_to_reproduce": 1.0, 
    "actual_result": 1.0, "expected_result": 1.0, "priority": 1.0
  },
  "warnings": []
}"""
# ─── Visual Bug Analyzer Prompt ─────────────────────────────
VISION_SYSTEM_PROMPT = """You are a Visual Bug Analyzer. Your goal is to look at the provided screenshot and identify technical bugs, UI glitches, or functional errors.

STRICT RULES:
1. FOCUS on visual inconsistencies (misaligned text, broken images, overlapping elements).
2. COMBINE the visual evidence with the "EVIDENCE CONTEXT CHUNKS" provided in text.
3. If the user provided a description, use it to prioritize what to look for.
4. Return ONLY JSON in the same format as the text-only analyzer.

JSON SCHEMA:
{
  "summary": "Short descriptive title",
  "description": "Describe the visual bug and its context",
  "steps_to_reproduce": "Based on UI state or text evidence",
  "actual_result": "What is visually wrong in the screenshot",
  "expected_result": "What the UI should look like",
  "priority": "Highest, High, Medium, Low, or Lowest",
  "evidence_chunk_ids": ["visual_screenshot", "chunk_id1"],
  "field_confidence": {
    "summary": 1.0, "description": 1.0, "steps_to_reproduce": 1.0, 
    "actual_result": 1.0, "expected_result": 1.0, "priority": 1.0
  },
  "warnings": []
}"""


def generate_bug_payload(
    retrieved_chunks: List[dict],
    user_description: str = "",
    api_key_override: str = None,
    model_override: str = None,
    image_path: str = None,
    custom_prompt: str = None,
) -> dict:
    """
    Generate a structured bug payload using constrained LLM generation.
    Supports both OpenAI and Groq (defaulting to Groq for speed/cost).
    """
    # ── Selection Logic ──
    key = api_key_override or settings.groq_api_key
    use_groq = GROQ_AVAILABLE and (str(key).startswith("gsk_") or settings.groq_api_key)
    
    # Use override or default to Groq from settings
    model = model_override or settings.groq_model
    
    # Visual Bug Auto-Selection
    active_prompt = SYSTEM_PROMPT
    if image_path and os.path.exists(image_path):
        # meta-llama/llama-4-scout-17b-16e-instruct is the new multimodal standard on Groq
        model = "meta-llama/llama-4-scout-17b-16e-instruct" 
        active_prompt = VISION_SYSTEM_PROMPT
        logger.info(f"Visual Bug Analyzer active: Using {model}")
    
    # ── Custom Instruction Injection ──
    if custom_prompt and custom_prompt.strip():
        active_prompt += f"\n\nADDITIONAL USER INSTRUCTIONS:\n{custom_prompt.strip()}"
        logger.info("Custom AI instructions injected into system prompt.")

    if not key:
        return {
            "success": False,
            "error": "No LLM API Key provided. Please configure Groq or OpenAI key.",
        }

    # ENFORCEMENT: Retrieval gate — must have context chunks
    if not retrieved_chunks:
        logger.warning("ABORT: No context chunks provided — retrieval gate enforced")
        return {
            "success": False,
            "error": "No evidence context available. Cannot generate bug without evidence.",
            "generation_status": "insufficient_data",
        }

    # Format context for the prompt
    context_text = format_context_for_llm(retrieved_chunks)

    # Build the user prompt
    user_prompt = f"""EVIDENCE CONTEXT CHUNKS:
{context_text}

USER'S BUG DESCRIPTION:
{user_description if user_description else "No additional description provided."}

INSTRUCTIONS:
Generate a Jira bug report using ONLY the evidence chunks above.
For every field, cite which chunk_id(s) support the content.
If any field cannot be filled from the evidence, use exactly:
"Insufficient evidence provided to generate this section."
Return ONLY the JSON object. No other text."""

    try:
        if use_groq:
            logger.info(f"Generating bug payload via Groq ({model})...")
            client = Groq(api_key=key)
            
            messages = [{"role": "system", "content": active_prompt}]
            
            if image_path and os.path.exists(image_path):
                # Vision message structure
                with open(image_path, "rb") as image_file:
                    base64_image = base64.b64encode(image_file.read()).decode('utf-8')
                
                messages.append({
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}",
                            },
                        },
                    ],
                })
            else:
                messages.append({"role": "user", "content": user_prompt})

            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.1,
                max_tokens=2000,
                response_format={"type": "json_object"},
            )
        else:
            return {
                "success": False,
                "error": "Groq is not configured. OpenAI support has been disabled.",
            }

        raw_output = response.choices[0].message.content.strip()
        # Handle cases where model wraps in markdown blocks
        if raw_output.startswith("```json"):
            raw_output = raw_output.split("```json")[1].split("```")[0].strip()
        elif raw_output.startswith("```"):
            raw_output = raw_output.split("```")[1].split("```")[0].strip()

        logger.debug(f"LLM raw output length: {len(raw_output)} chars")

        # Parse JSON
        try:
            payload = json.loads(raw_output)
        except json.JSONDecodeError as e:
            logger.error(f"LLM returned invalid JSON: {str(e)}")
            return {
                "success": False,
                "error": f"LLM returned invalid JSON: {str(e)}",
                "raw_output": raw_output,
            }

        # Calculate overall confidence
        field_conf = payload.get("field_confidence", {})
        fields = ["summary", "description", "steps_to_reproduce",
                   "actual_result", "expected_result", "priority"]
        
        # Field completeness ratio
        insufficient_msg = "Insufficient evidence provided to generate this section."
        filled_fields = sum(
            1 for f in fields
            if payload.get(f, insufficient_msg) != insufficient_msg
        )
        field_completeness = filled_fields / len(fields)

        # Evidence density
        cited_chunks = payload.get("evidence_chunk_ids", [])
        total_chunks = len(retrieved_chunks)
        evidence_density = min(1.0, len(set(cited_chunks)) / max(1, total_chunks * 0.6))

        # Average retrieval similarity
        avg_similarity = sum(
            c.get("similarity_score", 0) for c in retrieved_chunks
        ) / max(1, len(retrieved_chunks))

        # Overall confidence
        overall_confidence = (
            0.30 * avg_similarity +
            0.40 * field_completeness +
            0.30 * evidence_density
        )

        logger.info(
            f"Bug payload generated — Confidence: {overall_confidence:.3f} "
            f"(sim: {avg_similarity:.3f}, comp: {field_completeness:.3f})"
        )

        return {
            "success": True,
            "payload": payload,
            "evidence_chunk_ids": cited_chunks,
            "confidence_score": round(overall_confidence, 4),
            "field_confidence": field_conf,
            "warnings": payload.get("warnings", []),
        }

    except Exception as e:
        logger.error(f"Bug generation failed: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "generation_status": "failed",
        }
