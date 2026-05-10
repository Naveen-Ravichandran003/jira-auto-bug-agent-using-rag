# 📋 Task Plan — Jira Auto-Bug Mapping AI Agent

## B.L.A.S.T. Protocol Blueprint

---

## 🎯 North Star

> Automatically generate structured, hallucination-free Jira bug tickets from user-uploaded evidence (screenshots, PDFs, documents, or existing Jira tickets) and map them into the correct Jira board — with zero assumptions.

---

## 📐 Blueprint

### System Identity
- **Name**: Jira Auto-Bug Mapping AI Agent
- **Architecture**: A.N.T. 3-Layer (Architecture → Navigation → Tools)
- **Protocol**: B.L.A.S.T. (Blueprint → Link → Architect → Stylize → Trigger)
- **Core Principle**: Anti-hallucination RAG enforcement — NO generation without evidence

### Core Capabilities
1. Accept evidence from multiple sources (screenshot, PDF, Jira ticket, text description)
2. Process evidence through OCR/text extraction
3. Chunk, embed, and store evidence in vector database
4. Retrieve relevant context with confidence scoring
5. Generate structured bug payloads in strict Jira format
6. Validate payload against Jira Issue Create API schema
7. Create Jira issue via authenticated API call
8. Return evidence trace and confidence score

### Constraints (Non-Negotiable)
- ❌ No assumptions or inferred data
- ❌ No synthetic reproduction steps
- ❌ No guessed priority levels
- ❌ No fabricated expected/actual results
- ❌ No internet search or external knowledge
- ❌ No generic bug templates
- ❌ LLM never writes directly to Jira
- ✅ If data missing → "Insufficient evidence provided to generate this section."
- ✅ If confidence < 0.7 → Require manual approval
- ✅ If retrieval confidence < threshold → Abort generation

---

## 🏁 Milestones

### Milestone 1: Phase 0 — Initialization ✅ (Current)
- [x] Analyze BLAST.md specification
- [x] Create `task_plan.md` (this document)
- [ ] Create `findings.md` (research findings)
- [ ] Create `progress.md` (testing/validation log)
- [ ] Create `gemini.md` (project constitution)
- [ ] Blueprint review & approval

### Milestone 2: Phase 1 — Blueprint Finalization
- [ ] Define complete input/output schemas (Pydantic models)
- [ ] Establish Jira bug format contract
- [ ] Map all integration points
- [ ] Define source of truth hierarchy
- [ ] Create delivery payload specification

### Milestone 3: Phase 2 — Jira Connectivity (Link)
- [ ] Build `validate_jira_connection.py`
- [ ] Implement multi-user credential management
- [ ] Test API handshake: `/rest/api/3/myself`
- [ ] Test API handshake: `/rest/api/3/project`
- [ ] Test API handshake: `/rest/api/3/issue`
- [ ] Implement connection abort on validation failure
- [ ] Create `.env` template with encrypted token support

### Milestone 4: Phase 3 — Architecture Build (Architect)
#### Layer 1: SOPs
- [ ] `bug_generation_sop.md`
- [ ] `rag_retrieval_sop.md`
- [ ] `jira_mapping_sop.md`
- [ ] `anti_hallucination_policy.md`
- [ ] `confidence_scoring_model.md`

#### Layer 2: AI Navigation
- [ ] Build FastAPI application (`main.py`)
- [ ] Build AI agent orchestrator (`agent.py`)
- [ ] Build RAG pipeline coordinator (`rag_pipeline.py`)
- [ ] Build configuration manager (`config.py`)
- [ ] Build Pydantic schemas (`schemas.py`)

#### Layer 3: Tools
- [ ] `extract_text_from_image.py` — OCR processing
- [ ] `chunk_document.py` — Text chunking (500 tokens, 100 overlap)
- [ ] `embed_chunks.py` — Embedding generation + FAISS indexing
- [ ] `retrieve_context.py` — Vector similarity search (Top-K=5)
- [ ] `generate_bug_payload.py` — Constrained LLM generation
- [ ] `validate_payload_schema.py` — Schema compliance check
- [ ] `create_jira_issue.py` — Deterministic Jira API call

#### RAG Pipeline
- [ ] Evidence processing (OCR/PDF/API fetch)
- [ ] Chunking engine (500 token windows, 100 token overlap)
- [ ] Embedding pipeline (with metadata: chunk_id, source, user_id, timestamp)
- [ ] FAISS vector store setup
- [ ] Retrieval engine (Top-K=5, similarity threshold)
- [ ] Constrained generation with anti-hallucination prompt

### Milestone 5: Phase 4 — Enterprise UI (Stylize)
- [ ] Design enterprise dark/neutral theme
- [ ] Build Jira Configuration Panel
- [ ] Build Evidence Upload Panel
- [ ] Build Generated Bug Preview Panel
- [ ] Build Submission Panel
- [ ] Implement editable preview toggle
- [ ] Display confidence score & evidence trace
- [ ] Connect UI to FastAPI backend

### Milestone 6: Phase 5 — Trigger Activation
- [ ] Manual submission flow (end-to-end test)
- [ ] API webhook endpoint
- [ ] Slack integration (optional)
- [ ] CI/CD failure hook (optional)
- [ ] Security audit (token handling, no persistence)
- [ ] Audit logging

---

## ✅ Enterprise Checklist

### Security
- [ ] Per-user encrypted API tokens
- [ ] No token logging in any layer
- [ ] No evidence persistence beyond session (configurable)
- [ ] Audit logs enabled
- [ ] SOC2-compatible architecture design
- [ ] HTTPS for all external API calls
- [ ] `.env` file with encryption support

### Data Integrity
- [ ] All bug fields map to Jira Issue Create API schema
- [ ] Evidence trace IDs attached to every generated bug
- [ ] Confidence score calculated and enforced
- [ ] Schema validation before Jira submission

### Anti-Hallucination
- [ ] RAG pipeline enforced for all generations
- [ ] Retrieval confidence threshold enforced
- [ ] Missing fields explicitly marked (not guessed)
- [ ] Constrained generation prompt template active
- [ ] LLM output validated against evidence chunks

### Quality Assurance
- [ ] Unit tests for each atomic tool
- [ ] Integration tests for RAG pipeline
- [ ] End-to-end test for bug creation flow
- [ ] API handshake validation tests
- [ ] Schema compliance tests

---

## 📊 Priority Matrix

| Priority | Task | Phase |
|----------|------|-------|
| 🔴 P0 | Phase 0 documents (task_plan, findings, progress, gemini) | 0 |
| 🔴 P0 | Jira API connection & validation | 2 |
| 🔴 P0 | Anti-hallucination policy enforcement | 3 |
| 🟡 P1 | RAG pipeline (full flow) | 3 |
| 🟡 P1 | Atomic tools (8 scripts) | 3 |
| 🟡 P1 | Enterprise UI (4 panels) | 4 |
| 🟢 P2 | Webhook & Slack triggers | 5 |
| 🟢 P2 | CI/CD failure hook | 5 |
