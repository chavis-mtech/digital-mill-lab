# Designing an AI-Driven Industrial Intelligence Platform for Palm Oil Manufacturing

> **Pointer file.** The full technical case study lives in **[`docs/TECHNICAL_CASE_STUDY.md`](../TECHNICAL_CASE_STUDY.md)**
> so that there is one copy to keep accurate. This page exists because the portfolio folder lists
> `technical-case-study.md` (SPEC section 14).
>
> Independent concept demo on **synthetic data**. Not an official system of any company. Status of every claim:
> [`CAPABILITY_MATRIX.md`](CAPABILITY_MATRIX.md).

## Abstract

A palm oil mill is a chain of connected steps (weighbridge, sterilisation, digestion, pressing, clarification, storage)
in which small percentage changes matter. This case study describes how an evidence-first intelligence layer for such a
mill was designed and tested on a physically consistent synthetic dataset: a deterministic data engine with 58 passing
consistency checks, a typed Python service (KPIs, equipment health from explicit criteria, a human-confirmed work-order
loop with a hash-chained audit trail, an ROI simulator with no double counting), and eight classical ML models
evaluated on a later held-out period against naive baselines.

The honest results are part of the story. The hourly OER forecast, the energy forecast and the arrival forecast did not
beat their simple baselines, and the report says so. A press-bearing anomaly detector flagged the fault about 148 hours
before the rule-based critical alarm, but only on a degradation curve that the generator prescribes, so it proves the
pipeline rather than the physics.

## Sections in the full document

1. Summary and at-a-glance evidence table
2. Objective
3. Why it matters
4. Industrial context (process chain, mass balance, OER pitfalls)
5. Solution architecture (diagram, layers, request lifecycle)
6. Design decisions (linked to ADRs in `docs/DECISIONS.md`)
7. Data engineering and reliability (method, scenario episodes, validator, limits)
8. AI modelling approach (protocol, honest results, leakage audit, what the results teach, press-bearing lead time,
   health and risk, computer vision, Copilot design)
9. Human-in-the-loop workflow
10. Business-impact method (ROI formulas, calibration story, disclaimer)
11. Software engineering practices and delivery lessons
12. Security (demo grade)
13. Testing methodology: what was actually run, and what was not
14. Challenges and trade-offs
15. Demo limitations
16. What production adoption would require
17. Future expansion
18. Evidence index

Items not yet verified (Docker and CI, a real LLM provider, public deployment) are labelled in the full document.
