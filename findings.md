# 🔬 Research Findings — Jira Auto-Bug Mapping AI Agent

---

## 1. Jira REST API Research

### Authentication Methods (2025)
| Method | Recommendation | Notes |
|--------|---------------|-------|
| **API Token + Basic Auth** | ✅ Selected | Base64(`email:api_token`) in Authorization header |
| **OAuth 2.0 (3LO)** | 🔶 Future upgrade | More secure, scoped tokens, recommended for production |
| **Password Auth** | ❌ Deprecated | Do not use |
| **Cookie Auth** | ❌ Not suitable | Browser-session only, security risks |

### Key API Endpoints Required
```
GET  /rest/api/3/myself          → Validate credentials
GET  /rest/api/3/project         → List available projects
GET  /rest/api/3/project/{key}   → Get specific project details
POST /rest/api/3/issue           → Create bug issue
GET  /rest/api/3/issue/{key}     → Fetch existing issue (for story reference)
GET  /rest/api/3/issue/createmeta → Get create metadata (fields, issue types)
POST /rest/api/3/issue/{key}/attachments → Attach files to issue
```

### Jira Issue Create Payload Structure
```json
{
  "fields": {
    "project": { "key": "PROJECT_KEY" },
    "summary": "Bug summary from RAG",
    "description": {
      "type": "doc",
      "version": 1,
      "content": [
        {
          "type": "paragraph",
          "content": [
            { "type": "text", "text": "Description text" }
          ]
        }
      ]
    },
    "issuetype": { "name": "Bug" },
    "priority": { "name": "High" },
    "labels": ["auto-generated", "ai-agent"],
    "customfield_XXXXX": "Custom field values"
  }
}
```

### Important Notes
- Jira Cloud uses ADF (Atlassian Document Format) for description fields — NOT plain text
- API tokens now have enforced lifecycles and expiration (2025 policy)
- Rate limits apply: typically 100 requests per minute for Jira Cloud
- Must handle pagination for large project/issue lists
- Attachment upload requires `X-Atlassian-Token: no-check` header

---

## 2. OCR Engine Research

### Tesseract (pytesseract) — Selected
| Aspect | Detail |
|--------|--------|
| **Version** | Tesseract 5.x with LSTM neural networks |
| **Python Wrapper** | `pytesseract` |
| **Best DPI** | ≥ 300 DPI for optimal accuracy |
| **Accuracy** | ~80% on real-world docs; up to 95% with preprocessing |
| **Cost** | Free, open-source |

### Preprocessing Pipeline (Best Practice)
```
Input Image
  → Grayscale conversion (cv2.cvtColor)
  → Resize to 300+ DPI (cv2.resize)
  → Adaptive thresholding (cv2.adaptiveThreshold)
  → Noise removal (cv2.medianBlur)
  → Deskewing (correct rotation)
  → OCR extraction (pytesseract.image_to_string)
  → Raw text output
```

### Configuration Recommendations
- **PSM**: `--psm 6` (single uniform block) for screenshots, `--psm 3` (auto) for documents
- **OEM**: `--oem 3` (LSTM engine)
- **Language**: `-l eng` (expand as needed)
- Use `tessdata_fast` models for production speed

### Required Python Packages
```
pytesseract>=0.3.10
Pillow>=10.0.0
opencv-python>=4.8.0
```

### Alternative Considered: Azure Computer Vision
- Higher accuracy (~95-99%) especially for complex layouts
- Cloud-based, per-call pricing
- Better for handwriting and degraded scans
- **Decision**: Start with Tesseract (free), option to upgrade to Azure Vision later

---

## 3. RAG Pipeline Research

### Architecture Decision: FAISS (Local Vector Store)
| Feature | FAISS | Pinecone | Weaviate |
|---------|-------|----------|----------|
| **Cost** | Free | Paid | Free (self-hosted) |
| **Setup** | Simple | Cloud service | Complex |
| **Speed** | Very fast | Fast | Fast |
| **Scalability** | Moderate | High | High |
| **Local/Privacy** | ✅ Fully local | ❌ Cloud | ✅ Self-hosted |
| **Decision** | ✅ **Selected** | Future option | Future option |

### RAG Pipeline Design
```
Evidence Input
  │
  ├── Screenshot → Tesseract OCR → Raw Text
  ├── PDF → PyPDF2/pdfplumber → Raw Text
  ├── Jira Ticket → Jira API GET → Raw Text
  └── Description → Direct Text
  │
  ▼
Text Chunking
  • Window: 500 tokens
  • Overlap: 100 tokens
  • Metadata: chunk_id, source_file, user_id, timestamp
  │
  ▼
Embedding Generation
  • Model: OpenAI text-embedding-3-small (or ada-002)
  • Dimension: 1536
  │
  ▼
FAISS Vector Store
  • Index type: IndexFlatL2 (exact search for small datasets)
  • Upgrade to IVF for large datasets
  • Persist to disk: index.faiss + index.pkl
  │
  ▼
Retrieval
  • Top-K: 5 chunks
  • Similarity threshold: 0.7 (configurable)
  • Return chunk_ids as evidence trace
  │
  ▼
Constrained Generation
  • Model: GPT-4 / GPT-4o
  • System prompt enforces anti-hallucination
  • Output: Strict JSON schema only
  • Missing fields → explicit "Insufficient evidence" message
```

### Embedding Model Comparison
| Model | Dimensions | Cost | Quality |
|-------|-----------|------|---------|
| `text-embedding-3-small` | 1536 | $0.02/1M tokens | Good |
| `text-embedding-3-large` | 3072 | $0.13/1M tokens | Best |
| `text-embedding-ada-002` | 1536 | $0.10/1M tokens | Legacy |
| **Decision** | `text-embedding-3-small` | Cost-effective | Sufficient for bug context |

### Chunking Strategy
```python
# Recommended configuration
CHUNK_SIZE = 500        # tokens per chunk
CHUNK_OVERLAP = 100     # overlap between chunks
SEPARATOR = "\n\n"      # primary separator
FALLBACK_SEPARATORS = ["\n", ". ", " "]
```

### Anti-Hallucination Prompt Template
```
You are a deterministic bug report generator.

RULES:
1. Generate a Jira bug using ONLY the provided context chunks below.
2. If information for any field is missing from the context, state:
   "Insufficient evidence provided to generate this section."
3. Do NOT infer, assume, or generate any information not present in the context.
4. Do NOT create synthetic reproduction steps.
5. Do NOT guess priority levels.
6. Return response in strict JSON format only.

CONTEXT CHUNKS:
{retrieved_chunks}

USER QUERY:
{user_description}

OUTPUT FORMAT:
{json_schema}
```

---

## 4. Security Constraints

### Token Management
- All API tokens stored in `.env` file
- `.env` loaded via `python-dotenv` with optional encryption (`cryptography` package)
- Tokens NEVER logged (masked in all log outputs)
- Per-user token isolation (no shared credentials)

### Session Security
- Evidence files stored in `.tmp/` directory
- Configurable auto-deletion after session ends
- No evidence persisted to permanent storage by default
- User data isolation in FAISS (filter by `user_id`)

### Audit Logging
- All API calls logged with timestamp, user_id, action, status
- Token values masked in logs
- Configurable log rotation and retention
- SOC2-compatible log format

### Environment Variables Required
```env
# LLM Configuration
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o
EMBEDDING_MODEL=text-embedding-3-small

# OCR Configuration
TESSERACT_PATH=C:/Program Files/Tesseract-OCR/tesseract.exe

# RAG Configuration
FAISS_INDEX_PATH=./data/faiss_index
CHUNK_SIZE=500
CHUNK_OVERLAP=100
TOP_K=5
SIMILARITY_THRESHOLD=0.7
CONFIDENCE_THRESHOLD=0.7

# Server Configuration
HOST=0.0.0.0
PORT=8000
DEBUG=false
```

---

## 5. Python Dependencies

### Core Requirements
```
# API Framework
fastapi>=0.104.0
uvicorn>=0.24.0

# Jira Integration
requests>=2.31.0

# OCR
pytesseract>=0.3.10
Pillow>=10.0.0
opencv-python>=4.8.0

# PDF Processing
PyPDF2>=3.0.0
pdfplumber>=0.10.0

# RAG Pipeline
langchain>=0.1.0
langchain-openai>=0.0.5
langchain-community>=0.0.10
faiss-cpu>=1.7.4
tiktoken>=0.5.0

# LLM
openai>=1.10.0

# Data Validation
pydantic>=2.5.0

# Environment & Security
python-dotenv>=1.0.0
cryptography>=41.0.0

# Logging & Monitoring
loguru>=0.7.0
```
