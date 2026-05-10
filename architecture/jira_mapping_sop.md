# Jira Mapping SOP — Standard Operating Procedure

## Purpose
Defines how generated bug payloads are mapped to the Jira Issue Create API schema.

## Field Mapping

| Internal Field | Jira API Path | Type | Notes |
|---------------|---------------|------|-------|
| summary | `fields.summary` | string | Plain text, max 255 chars |
| description | `fields.description` | ADF object | Atlassian Document Format |
| steps_to_reproduce | Appended to description | ADF section | Under "Steps to Reproduce" heading |
| actual_result | Appended to description | ADF section | Under "Actual Result" heading |
| expected_result | Appended to description | ADF section | Under "Expected Result" heading |
| priority | `fields.priority.name` | string | Highest/High/Medium/Low/Lowest |
| labels | `fields.labels` | array | Always includes "auto-generated" |
| project_key | `fields.project.key` | string | From user credentials |
| issue_type | `fields.issuetype.name` | string | Always "Bug" |

## ADF Conversion Rules
1. Description body is structured as ADF (Atlassian Document Format)
2. Each section (Description, Steps, Actual, Expected) gets an H3 heading
3. Content under each heading is a paragraph node
4. Evidence trace and confidence score appended as final sections

## Attachment Handling
1. After issue creation, attach evidence files via separate API call
2. Endpoint: `POST /rest/api/3/issue/{issueKey}/attachments`
3. Header: `X-Atlassian-Token: no-check`
4. Multipart form upload

## Validation Before Submission
1. Summary must be non-empty and ≤ 255 characters
2. At least description OR steps_to_reproduce must have evidence content
3. Priority must be valid Jira value (or omitted if insufficient evidence)
4. Project key must match validated project
5. Issue type "Bug" must exist in project

## Error Handling
- 400: Invalid payload → Log and return error details
- 401: Auth failure → Prompt re-authentication
- 403: Permission denied → Inform user
- 404: Project not found → Inform user
- 429: Rate limit → Retry with exponential backoff (max 3)
