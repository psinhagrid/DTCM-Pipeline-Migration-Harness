# Example: Complex Pipeline

**Task context:** Multi-file pipeline with UDFs, window functions, and downstream consumers.

**Skill used:** complexity_classification

**Input signals:**
- 8 tables → +8
- 3 UDFs → +6
- 1 window function → +3
- 2 subqueries → +4
- 1 downstream consumer → +1
- Total score: 22

**Expected output:**
- Band: COMPLEX
- Effort: 2+ weeks
- Risk flags: UDFs > 3 (verify conversion), window function semantics
