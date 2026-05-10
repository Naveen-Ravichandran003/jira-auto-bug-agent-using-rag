"""
Tool: Create Jira Issue
Submits the validated bug payload to Jira via REST API v3.
Deterministic — LLM never calls this directly.
"""

import os
import sys
import base64
import requests
from typing import Optional, List

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from loguru import logger
from src.config import mask_token
from tools.validate_payload_schema import build_jira_adf, validate_payload


def create_issue(
    base_url: str,
    email: str,
    api_token: str,
    project_key: str,
    bug_payload: dict,
    confidence_score: float = 0.0,
    evidence_trace: list = None,
) -> dict:
    """
    Create a Jira bug issue from the validated payload.

    SECURITY: This tool is the ONLY way to write to Jira.
    The LLM never directly calls the Jira API.

    Args:
        base_url: Jira Cloud instance URL
        email: User's Atlassian email
        api_token: User's API token (never logged)
        project_key: Target project key
        bug_payload: Generated and validated bug payload
        confidence_score: Overall confidence score
        evidence_trace: List of evidence chunk_ids

    Returns:
        dict with issue key, URL, and status
    """
    evidence_trace = evidence_trace or []

    # Step 1: Validate payload before submission
    validation = validate_payload(bug_payload)
    if not validation["valid"]:
        logger.error(f"Payload validation failed: {validation['errors']}")
        return {
            "success": False,
            "error": "Payload validation failed",
            "validation_errors": validation["errors"],
        }

    # Step 2: Convert to Jira ADF format
    jira_payload = build_jira_adf(
        payload=bug_payload,
        confidence_score=confidence_score,
        evidence_trace=evidence_trace,
    )

    # Add project key
    jira_payload["fields"]["project"] = {"key": project_key}

    # Step 3: Submit to Jira
    url = f"{base_url.rstrip('/')}/rest/api/3/issue"
    credentials = f"{email}:{api_token}"
    encoded = base64.b64encode(credentials.encode()).decode()
    headers = {
        "Authorization": f"Basic {encoded}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    logger.info(
        f"Creating Jira issue in project {project_key} "
        f"(confidence: {confidence_score:.2%})"
    )
    logger.debug(f"API token: {mask_token(api_token)}")

    try:
        response = requests.post(url, headers=headers, json=jira_payload, timeout=30)
        response.raise_for_status()

        data = response.json()
        issue_key = data.get("key", "")
        issue_id = data.get("id", "")
        issue_url = f"{base_url.rstrip('/')}/browse/{issue_key}"

        logger.info(f"✅ Jira issue created: {issue_key} — {issue_url}")

        return {
            "success": True,
            "issue_key": issue_key,
            "issue_id": issue_id,
            "issue_url": issue_url,
            "message": f"Bug '{issue_key}' created successfully",
        }

    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response else "Unknown"
        error_body = ""
        try:
            error_body = e.response.json() if e.response else {}
        except Exception:
            error_body = e.response.text if e.response else ""

        logger.error(f"Jira issue creation failed: HTTP {status}")
        logger.debug(f"Error body: {error_body}")

        error_msgs = {
            400: "Invalid payload — check field formats",
            401: "Authentication failed — check credentials",
            403: "Permission denied — insufficient Jira permissions",
            404: f"Project '{project_key}' not found",
            429: "Rate limited — too many requests, retry later",
        }

        return {
            "success": False,
            "error": error_msgs.get(status, f"HTTP {status} error"),
            "status_code": status,
            "details": error_body,
        }

    except requests.exceptions.Timeout:
        logger.error("Jira API request timed out")
        return {"success": False, "error": "Jira API request timed out"}

    except Exception as e:
        logger.error(f"Unexpected error creating issue: {str(e)}")
        return {"success": False, "error": str(e)}


def attach_file_to_issue(
    base_url: str,
    email: str,
    api_token: str,
    issue_key: str,
    file_path: str,
) -> dict:
    """
    Attach an evidence file to a Jira issue.

    Args:
        base_url: Jira Cloud URL
        email: User email
        api_token: API token
        issue_key: Created issue key (e.g., PROJ-123)
        file_path: Path to the file to attach

    Returns:
        dict with attachment status
    """
    if not os.path.exists(file_path):
        return {"success": False, "error": f"File not found: {file_path}"}

    url = f"{base_url.rstrip('/')}/rest/api/3/issue/{issue_key}/attachments"
    credentials = f"{email}:{api_token}"
    encoded = base64.b64encode(credentials.encode()).decode()
    headers = {
        "Authorization": f"Basic {encoded}",
        "Accept": "application/json",
        "X-Atlassian-Token": "no-check",  # Required for attachment upload
    }

    logger.info(f"Attaching file to {issue_key}: {os.path.basename(file_path)}")

    try:
        with open(file_path, "rb") as f:
            files = {"file": (os.path.basename(file_path), f)}
            response = requests.post(url, headers=headers, files=files, timeout=60)
            response.raise_for_status()

        logger.info(f"✅ File attached to {issue_key}")
        return {
            "success": True,
            "message": f"File attached to {issue_key}",
            "filename": os.path.basename(file_path),
        }

    except Exception as e:
        logger.error(f"Attachment failed: {str(e)}")
        return {"success": False, "error": str(e)}
