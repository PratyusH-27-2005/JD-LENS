Model `gemini-2.5-flash`, prompt `extract_v1`, 3 run(s) per posting.

**98/99 checks passed.**

| Check | acme | kasparro | zeta |
|---|---|---|---|
| status | ✓ | ✓ | ✓ |
| company | ✓ | ✓ | ✓ |
| role_title | ✓ | ✓ | ✓ |
| location | ✓ | ✓ | ✗ 2/3 (value 'India') |
| work_mode | ✓ | ✓ | ✓ |
| stipend | ✓ | ✓ | ✓ |
| ctc | ✓ | ✓ | ✓ |
| eligibility | ✓ | ✓ | ✓ |
| application_deadline | ✓ | ✓ | ✓ |
| apply_instructions | ✓ | ✓ | ✓ |
| required_skills | ✓ | ✓ | ✓ |

- Evidence rejection rate: 0/102 quoted mentions (0%) were not found in the posting.
- Retries: 0/9 extractions needed the second attempt; 0 ended in needs_review.
- Latency per call: median 7.2 s, max 19.6 s.
- Tokens per call: ~833 in, ~578 out.
