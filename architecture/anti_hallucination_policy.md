# Anti-Hallucination Policy — Enforcement Document

## Classification: MANDATORY — No Exceptions

## Definition
Hallucination is any output from the LLM that:
- Is not directly supported by the provided evidence chunks
- Infers information not explicitly stated in the evidence
- Creates synthetic data, steps, or results
- Guesses or assumes values for any field

## Enforcement Rules

### RULE 1: EVIDENCE_ONLY
Every field in the generated bug report MUST be traceable to a specific evidence chunk.
If a chunk_id cannot be cited for a field → field value MUST be:
`"Insufficient evidence provided to generate this section."`

### RULE 2: NO_INFERENCE
The LLM MUST NOT infer, extrapolate, or synthesize information beyond explicit evidence.
Prohibited language: "likely", "probably", "may", "could", "might", "possibly"

### RULE 3: NO_SYNTHETIC_STEPS
Steps to reproduce MUST come directly from the evidence.
The system MUST NOT create logical step sequences not present in source material.

### RULE 4: NO_PRIORITY_GUESSING
Priority MUST be explicitly stated or clearly derivable from evidence.
If not → "Insufficient evidence provided to generate this section."

### RULE 5: NO_FABRICATION
Expected and actual results MUST be directly quoted or closely paraphrased from evidence.
No creative interpretation or elaboration allowed.

### RULE 6: RETRIEVAL_GATE
LLM MUST NOT generate any output without retrieval context.
- 0 retrieved chunks → ABORT generation entirely
- Status: "insufficient_data"

### RULE 7: CONFIDENCE_GATE
- confidence_score < 0.7 → DO NOT auto-submit
- confidence_score < 0.5 → ABORT generation
- Require explicit user approval for low-confidence reports

## Enforcement Checkpoints
1. **Pre-Generation**: Verify RAG pipeline returned chunks above threshold
2. **During Generation**: System prompt enforces rules (cannot be overridden)
3. **Post-Generation**: Validate fields, calculate confidence, check for hallucination markers
4. **Pre-Submission**: Final schema validation and confidence gate

## Violation Handling
If any rule is violated:
1. Generation is rejected
2. Error is logged with rule identifier
3. User is notified with specific violation details
4. No data is sent to Jira
