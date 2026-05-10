# RAG Retrieval SOP — Standard Operating Procedure

## Purpose
Defines the retrieval-augmented generation pipeline for evidence-based bug generation.

## Pipeline Stages

### Stage 1: Document Ingestion
- Accept raw text from evidence processing
- Validate text is non-empty
- If empty → Abort with "No extractable text found"

### Stage 2: Text Chunking
- Method: Recursive Character Text Splitting
- Chunk Size: 500 tokens
- Overlap: 100 tokens
- Separators: `["\n\n", "\n", ". ", " "]`
- Each chunk receives metadata:
  - `chunk_id`: UUID v4
  - `source_file`: Original filename
  - `source_type`: screenshot | pdf | jira_ticket | document | text
  - `user_id`: Requesting user
  - `timestamp`: ISO 8601
  - `chunk_index`: Position in document

### Stage 3: Embedding Generation
- Model: `text-embedding-3-small`
- Dimensions: 1536
- Batch processing for multiple chunks
- Error handling for API rate limits

### Stage 4: FAISS Indexing
- Index Type: `IndexFlatL2` (exact search)
- Store vectors with metadata mapping
- Persist to disk at `FAISS_INDEX_PATH`
- Per-session indexing (user isolation)

### Stage 5: Query & Retrieval
- Embed user query / evidence description
- FAISS similarity search: Top-K = 5
- Filter results by similarity threshold (0.7)
- Filter by `user_id` for multi-tenant isolation
- Return chunk content + metadata

### Stage 6: Context Assembly
- Concatenate retrieved chunks with separators
- Include chunk_ids for evidence tracing
- Format as structured context block for LLM

## Abort Conditions
- No text extracted from evidence → Abort
- 0 chunks after splitting → Abort
- Embedding API failure → Abort with retry (max 3)
- 0 chunks above similarity threshold → Abort
- Status: `insufficient_data`

## Quality Metrics
- Track retrieval similarity scores
- Track number of chunks retrieved vs threshold
- Log retrieval latency
