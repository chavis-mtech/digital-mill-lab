"""Industrial Operations Copilot (SPEC 4.F, ADR-010). Owner: copilot.

Read-only, tool-based, grounded and cited. Pipeline (app/copilot/engine.py):
question -> input safety -> intent routing (router.py) -> per-role tool allow-list (rbac) -> typed tools over the
EXISTING services (tools.py) -> deterministic composer (composer.py) -> grounding verifier (verifier.py)
-> optional LLM phrasing (llm.py, verified by the same verifier) -> session-scoped storage + audit.
"""
