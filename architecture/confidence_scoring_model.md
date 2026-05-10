# Confidence Scoring Model

## Purpose
Defines how the system calculates and uses confidence scores for bug report quality.

## Formula
```
confidence_score = (
    0.30 × retrieval_similarity_score +
    0.40 × field_completeness_ratio +
    0.30 × evidence_density
)
```

## Components

### Retrieval Similarity Score (Weight: 30%)
```
retrieval_similarity_score = mean(top_k_similarity_scores)
```
- Average similarity score of all Top-K retrieved chunks
- Range: 0.0 to 1.0
- Higher = better match between evidence and query

### Field Completeness Ratio (Weight: 40%)
```
field_completeness_ratio = fields_with_evidence / total_required_fields
```
- Required fields: summary, description, steps_to_reproduce, actual_result, expected_result, priority
- Total: 6 fields
- Field counts only if it has evidence content (not "Insufficient evidence")
- Range: 0.0 to 1.0

### Evidence Density (Weight: 30%)
```
evidence_density = min(1.0, unique_chunks_cited / (top_k × 0.6))
```
- How many retrieved chunks were actually used in generation
- Normalized to 0.0 to 1.0
- Top-K default = 5, so threshold = 3 chunks for full density score

## Threshold Actions

| Score Range | Level | Action |
|-------------|-------|--------|
| 0.85 – 1.00 | 🟢 High | Auto-submit eligible |
| 0.70 – 0.84 | 🟡 Medium | Auto-submit with confidence warning |
| 0.50 – 0.69 | 🟠 Low | Manual approval required |
| 0.00 – 0.49 | 🔴 Critical | Generation aborted |

## Per-Field Confidence
Each field also receives individual confidence:
- 1.0 = Field fully populated from evidence
- 0.5 = Field partially derived (some evidence, some uncertainty)
- 0.0 = Field marked as "Insufficient evidence"

## Reporting
Every generated bug includes:
- `confidence_score`: Overall score
- `field_confidence`: Per-field breakdown
- `warnings`: Array of fields with low confidence
