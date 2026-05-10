# Bug Generation SOP — Standard Operating Procedure

## Purpose
Defines the deterministic process for generating a Jira bug ticket from user-provided evidence.

## Trigger
User submits evidence via the UI or API endpoint.

## Pre-Conditions
1. User has valid Jira credentials (validated via `/rest/api/3/myself`)
2. Evidence has been uploaded (screenshot, PDF, document, text, or Jira ticket key)
3. System has active OpenAI API key for embeddings and generation

## Procedure

### Step 1: Evidence Intake
- Accept evidence from user
- Validate file type and size
- Store temporarily in `.tmp/{user_id}/`

### Step 2: Text Extraction
- **Screenshot** → OCR via Tesseract (with preprocessing pipeline)
- **PDF** → Text extraction via pdfplumber
- **Jira Ticket** → Fetch via REST API
- **Document** → Text extraction
- **Text Description** → Direct pass-through

### Step 3: RAG Processing
- Chunk text (500 tokens, 100 overlap)
- Generate embeddings (text-embedding-3-small)
- Store in FAISS index with metadata
- Retrieve Top-K=5 relevant chunks
- Enforce similarity threshold (0.7)

### Step 4: Constrained Generation
- Pass retrieved chunks to GPT-4o with anti-hallucination system prompt
- Generate structured JSON bug payload
- Every field must cite evidence chunk_ids

### Step 5: Validation
- Validate payload against output schema
- Calculate confidence score
- Check all required fields populated or marked "Insufficient evidence"

### Step 6: Review Gate
- If confidence ≥ 0.7 → Present to user for optional edit → Submit
- If confidence < 0.7 → Flag for mandatory manual review
- If confidence < 0.5 → Abort generation

### Step 7: Jira Submission
- Convert payload to Jira ADF format
- POST to `/rest/api/3/issue`
- Attach evidence files if applicable
- Return Jira issue link to user

### Step 8: Cleanup
- Delete temporary files from `.tmp/{user_id}/`
- Log audit entry
- Clear sensitive data from memory

## Post-Conditions
- Jira issue created with all evidence-backed fields
- Evidence trace and confidence score recorded
- Audit log entry created
