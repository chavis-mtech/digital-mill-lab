# Model card: copilot-router@1 (deterministic intent router)

| Field | Value |
|---|---|
| Purpose | Map a TH/EN question to one of 14 answer intents (plus `help`; `no_data` and `explicit_tool` come from rules, `unknown` from low similarity), and extract slots (equipment code, day, period, hours, pp, lot code, explicit tool names). The intent picks which read-only tools the copilot calls |
| Code | `apps/ai-api/app/copilot/router.py` |
| Algorithm | (1) ordered regex rules (TH + EN keywords). (2) Otherwise the nearest neighbour by cosine similarity over TF-IDF character 2-4 grams (`char_wb`, scikit-learn) of labelled exemplars, accepted when cosine >= 0.32, else `unknown`. (3) Follow-up handling: a short message after a stored turn inherits the previous intent and slots ("why?" maps oer_value to oer_why). Input and patterns are NFKC-normalised the same way, because NFKC decomposes Thai SARA AM |
| Training data | The `EXEMPLARS` dict in the same file: 204 hand-written TH/EN questions over 16 labels (incl. forecast). No user data and no external corpus |
| Input features | Character n-grams of the normalised question. Regex keyword hits. The previous intent and slots of the same demo session |
| Synthetic-data assumptions | None about plant values. The router never sees data. Slots are validated again by each tool's Pydantic schema |
| Evaluation (after review fixes) | Second held-out set (46, written before the changes): 25 correct, 16 clarified, 5 wrong (83.3% accurate when it answers; 10.9% wrong overall, down from 65.2%). Confidence gate: weak rules must agree with TF-IDF; grey zone (cos 0.30-0.45 or margin < 0.06; < 0.15 for 1-2-word English queries) -> clarification with top-2 options. Every answer is prefixed "Interpreted as: ..." |
| Evaluation (first run) | `python -m app.copilot.evaluate` (see `docs/ai/COPILOT_EVALUATION.md`). Intent accuracy 106/113 (93.8%), but 80 of the 113 labelled questions are verbatim exemplars. **Held-out paraphrases: 8/15 (53.3%).** Multi-turn: 9/9. Language detection: 113/113 |
| Limitations | Keyword-driven: wording outside the rules and exemplars falls through to the nearest exemplar or to `unknown`. Thai coverage is thinner than English. Causal Thai phrasing ("ต่ำกว่าปกติไหม เพราะอะไร") was missed in the held-out set. Not a language model: it does not understand negation or compound questions (only the first matching rule wins) |
| Known failure modes | Generic words ("summarise", "report") pull questions to daily_summary. "worst condition" routes to equipment_status without a code, which gives no assessment. The no-data keyword list is finite: an out-of-data topic not on the list routes to the nearest exemplar, and the answer then reports real but irrelevant data. It never invents numbers, because the verifier checks every number |
| Safety role | None. Safety does not depend on the router: role allow-lists, read-only tools, input/output pattern checks and the grounding verifier apply whatever intent is chosen |
| Deployment status | Implemented, default mode (no API key needed). An optional LLM can request tools itself (`app/copilot/llm.py`) |
