"""
Tool: Validate Jira Connection
Validates user credentials by calling Jira REST API v3 endpoints.
Deterministic — no LLM involvement.
"""

import base64
import requests
from loguru import logger

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.config import mask_token


def _build_auth_header(email: str, api_token: str) -> dict:
    """Build Basic Auth header for Jira Cloud API."""
    credentials = f"{email}:{api_token}"
    encoded = base64.b64encode(credentials.encode()).decode()
    return {
        "Authorization": f"Basic {encoded}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def validate_myself(base_url: str, email: str, api_token: str) -> dict:
    """
    Test authentication by calling /rest/api/3/myself.
    Returns user info if successful, error dict if failed.
    """
    url = f"{base_url.rstrip('/')}/rest/api/3/myself"
    headers = _build_auth_header(email, api_token)

    logger.info(f"Testing Jira auth for {email} at {base_url}")
    logger.debug(f"API token: {mask_token(api_token)}")

    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
        logger.info(f"Auth successful — User: {data.get('displayName', 'Unknown')}")
        return {
            "success": True,
            "display_name": data.get("displayName", ""),
            "account_id": data.get("accountId", ""),
            "email": data.get("emailAddress", email),
        }
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response else "Unknown"
        logger.error(f"Jira auth failed with HTTP {status}")
        return {"success": False, "error": f"Authentication failed (HTTP {status})"}
    except requests.exceptions.ConnectionError:
        logger.error(f"Cannot connect to {base_url}")
        return {"success": False, "error": f"Cannot connect to {base_url}"}
    except requests.exceptions.Timeout:
        logger.error("Jira API request timed out")
        return {"success": False, "error": "Connection timed out"}
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return {"success": False, "error": str(e)}


def validate_project(base_url: str, email: str, api_token: str, project_key: str) -> dict:
    """
    Validate that the project exists and user has access.
    """
    url = f"{base_url.rstrip('/')}/rest/api/3/project/{project_key}"
    headers = _build_auth_header(email, api_token)

    logger.info(f"Validating project: {project_key}")

    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
        logger.info(f"Project validated: {data.get('name', project_key)}")
        return {
            "success": True,
            "project_name": data.get("name", ""),
            "project_key": data.get("key", project_key),
            "project_id": data.get("id", ""),
        }
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response else "Unknown"
        logger.error(f"Project validation failed: HTTP {status}")
        return {"success": False, "error": f"Project '{project_key}' not found or no access (HTTP {status})"}
    except Exception as e:
        logger.error(f"Project validation error: {str(e)}")
        return {"success": False, "error": str(e)}


def list_projects(base_url: str, email: str, api_token: str) -> dict:
    """
    List all accessible projects for the authenticated user.
    """
    url = f"{base_url.rstrip('/')}/rest/api/3/project"
    headers = _build_auth_header(email, api_token)

    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        projects = response.json()
        project_list = [
            {"key": p.get("key", ""), "name": p.get("name", "")}
            for p in projects
        ]
        logger.info(f"Found {len(project_list)} projects")
        return {"success": True, "projects": project_list}
    except Exception as e:
        logger.error(f"List projects error: {str(e)}")
        return {"success": False, "error": str(e), "projects": []}


def full_validation(base_url: str, email: str, api_token: str, project_key: str) -> dict:
    """
    Run complete Jira connection validation:
    1. Authenticate user
    2. Validate project access
    3. List available projects
    Returns combined result.
    """
    # Step 1: Auth
    auth_result = validate_myself(base_url, email, api_token)
    if not auth_result.get("success"):
        return {
            "success": False,
            "step_failed": "authentication",
            "error": auth_result.get("error", "Authentication failed"),
        }

    # Step 2: Project
    project_result = validate_project(base_url, email, api_token, project_key)
    if not project_result.get("success"):
        return {
            "success": False,
            "step_failed": "project_validation",
            "error": project_result.get("error", "Project validation failed"),
            "user": auth_result.get("display_name", ""),
        }

    # Step 3: List projects
    projects_result = list_projects(base_url, email, api_token)

    return {
        "success": True,
        "user_display_name": auth_result.get("display_name", ""),
        "project_name": project_result.get("project_name", ""),
        "project_key": project_result.get("project_key", ""),
        "available_projects": projects_result.get("projects", []),
    }
