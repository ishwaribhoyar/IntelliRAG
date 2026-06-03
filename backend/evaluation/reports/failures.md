# Failure Analysis

**6 failures** / 60 queries (Dataset A)

| Category | Count |
|:---|:---:|
| hallucination_risk | 1 |
| retrieval_miss | 2 |
| false_positive | 3 |

## Examples

### F07: What does MRO stand for in Python?
- Type: factual | Category: hallucination_risk
- Semantic Sim: 0.2493 | Coverage: 0.0
- Confidence: 0.632 (medium)

### F18: What happens when you append to a list that is referenced by
- Type: factual | Category: retrieval_miss
- Semantic Sim: 0.4971 | Coverage: 0.25
- Confidence: 0.74 (high)

### C01: Why is Python called an interpreted language?
- Type: conceptual | Category: retrieval_miss
- Semantic Sim: 0.6085 | Coverage: 0.333
- Confidence: 0.973 (high)

### A02: How does React handle state management?
- Type: adversarial | Category: false_positive
- Semantic Sim: 0 | Coverage: 0.4
- Confidence: 0.597 (medium)

### A04: Explain quantum computing error correction.
- Type: adversarial | Category: false_positive
- Semantic Sim: 0 | Coverage: 0.4
- Confidence: 0.59 (medium)

### A09: How do you train a GPT model from scratch?
- Type: adversarial | Category: false_positive
- Semantic Sim: 0 | Coverage: 0.4
- Confidence: 0.537 (medium)

