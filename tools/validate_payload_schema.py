"""
Tool: Validate Payload Schema
Validates the generated bug payload against the Jira Issue Create API schema.
Deterministic — no LLM involvement.
"""

import os
import sys
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from loguru import logger

INSUFFICIENT_EVIDENCE_MSG = "Insufficient evidence provided to generate this section."

VALID_PRIORITIES = {"Highest", "High", "Medium", "Low", "Lowest"}


def validate_payload(payload: dict) -> dict:
    """
    Validate the generated bug payload against the Jira API schema.

    Checks:
    1. Required fields present
    2. Summary length (≤ 255 chars, non-empty)
    3. At least description OR steps_to_reproduce has content
    4. Priority is a valid Jira value (or insufficient evidence)
    5. Evidence trace is present

    Args:
        payload: The generated bug payload dict

    Returns:
        dict with 'valid', 'errors', and 'warnings'
    """
    errors = []
    warnings = []

    # --- Check required fields ---
    required_fields = [
        "summary", "description", "steps_to_reproduce",
        "actual_result", "expected_result", "priority",
    ]

    for field in required_fields:
        if field not in payload:
            errors.append(f"Missing required field: '{field}'")

    # --- Validate summary ---
    summary = payload.get("summary", "")
    if not summary or summary == INSUFFICIENT_EVIDENCE_MSG:
        errors.append(
            "Summary cannot be empty or 'Insufficient evidence'. "
            "A bug must have a title."
        )
    elif len(summary) > 255:
        errors.append(f"Summary exceeds 255 characters ({len(summary)} chars)")

    # --- Check that at least one content field has evidence ---
    content_fields = ["description", "steps_to_reproduce"]
    has_content = any(
        payload.get(f, INSUFFICIENT_EVIDENCE_MSG) != INSUFFICIENT_EVIDENCE_MSG
        for f in content_fields
    )
    if not has_content:
        errors.append(
            "At least 'description' or 'steps_to_reproduce' must have "
            "evidence-backed content"
        )

    # --- Validate priority ---
    priority = payload.get("priority", INSUFFICIENT_EVIDENCE_MSG)
    if priority != INSUFFICIENT_EVIDENCE_MSG and priority not in VALID_PRIORITIES:
        warnings.append(
            f"Priority '{priority}' is not a standard Jira value. "
            f"Valid: {', '.join(sorted(VALID_PRIORITIES))}"
        )

    # --- Check for hallucination markers ---
    hallucination_markers = [
        "likely", "probably", "may ", "could ", "might ",
        "possibly", "presumably", "it seems", "appears to",
    ]
    for field in required_fields:
        value = payload.get(field, "")
        if value and value != INSUFFICIENT_EVIDENCE_MSG:
            for marker in hallucination_markers:
                if marker.lower() in value.lower():
                    warnings.append(
                        f"Potential hallucination in '{field}': "
                        f"contains speculative language '{marker.strip()}'"
                    )

    # --- Check evidence trace ---
    evidence_ids = payload.get("evidence_chunk_ids", [])
    if not evidence_ids:
        warnings.append(
            "No evidence_chunk_ids provided. "
            "Evidence traceability cannot be verified."
        )

    is_valid = len(errors) == 0

    if is_valid:
        logger.info("Payload validation passed")
    else:
        logger.warning(f"Payload validation failed: {len(errors)} errors")

    if warnings:
        logger.info(f"Payload warnings: {len(warnings)}")

    return {
        "valid": is_valid,
        "errors": errors,
        "warnings": warnings,
        "field_count": len([
            f for f in required_fields
            if payload.get(f, INSUFFICIENT_EVIDENCE_MSG) != INSUFFICIENT_EVIDENCE_MSG
        ]),
        "total_fields": len(required_fields),
    }


def build_jira_adf(payload: dict, confidence_score: float = 0.0, evidence_trace: list = None) -> dict:
    """
    Convert the internal bug payload to Jira ADF (Atlassian Document Format).

    This is the format required by Jira REST API v3 for the description field.

    Args:
        payload: The validated bug payload
        confidence_score: Overall confidence score
        evidence_trace: List of chunk_ids used

    Returns:
        Jira-compatible issue creation payload
    """
    evidence_trace = evidence_trace or []

    # Build ADF content sections
    adf_content = []

    # Description section
    _add_adf_section(adf_content, "Description", payload.get("description", INSUFFICIENT_EVIDENCE_MSG))

    # Steps to Reproduce
    _add_adf_section(adf_content, "Steps to Reproduce", payload.get("steps_to_reproduce", INSUFFICIENT_EVIDENCE_MSG))

    # Actual Result
    _add_adf_section(adf_content, "Actual Result", payload.get("actual_result", INSUFFICIENT_EVIDENCE_MSG))

    # Expected Result
    _add_adf_section(adf_content, "Expected Result", payload.get("expected_result", INSUFFICIENT_EVIDENCE_MSG))

    # Evidence Trace
    trace_text = ", ".join(evidence_trace) if evidence_trace else "No evidence trace available"
    _add_adf_section(adf_content, "Evidence Trace", trace_text)

    # Confidence Score
    _add_adf_section(adf_content, "Confidence Score", f"{confidence_score:.2%}")

    # Auto-generated notice
    _add_adf_section(
        adf_content,
        "Generation Notice",
        "This bug report was auto-generated by the Jira Auto-Bug Mapping AI Agent. "
        "All content is derived from user-provided evidence with anti-hallucination enforcement."
    )

    # Build the Jira issue payload
    jira_payload = {
        "fields": {
            "summary": payload.get("summary", "Auto-generated Bug Report"),
            "description": {
                "type": "doc",
                "version": 1,
                "content": adf_content,
            },
            "issuetype": {"name": "Bug"},
            "labels": payload.get("labels", ["auto-generated", "ai-agent"]),
        }
    }

    # Add priority if valid
    priority = payload.get("priority", INSUFFICIENT_EVIDENCE_MSG)
    if priority in VALID_PRIORITIES:
        jira_payload["fields"]["priority"] = {"name": priority}

    return jira_payload


def _add_adf_section(content_list: list, heading: str, body: str):
    """Add a heading + paragraph section to the ADF content."""
    # Heading
    content_list.append({
        "type": "heading",
        "attrs": {"level": 3},
        "content": [{"type": "text", "text": heading}],
    })
    # Body paragraph
    content_list.append({
        "type": "paragraph",
        "content": [{"type": "text", "text": body}],
    })
