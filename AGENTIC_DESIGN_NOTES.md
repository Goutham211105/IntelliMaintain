# Agentic design notes

## What is agentic in this prototype?
- Goal intake from the user.
- Planner proposes optional tools (local Ollama JSON mode when available).
- Allowlist validation and orchestrator policy guardrails.
- Tools return structured findings.
- Conditional decision: anomalies force trend analysis; otherwise a validated plan may select it.
- Risk assessment and recommendations are evidence/rule based.
- Trace explains why a tool ran or was skipped.

## What this does not claim
- It does not autonomously operate machinery or create work orders.
- It does not train a predictive model or prove real-world failure prediction accuracy.
- When Ollama is unavailable, the offline fallback is deterministic.
- Thresholds are illustrative and require asset-specific validation.

## Evidence to collect for the assignment
1. Screenshot of the plan-and-tool-selection trace with Ollama disabled (fallback).
2. If Ollama is installed, screenshot showing `Ollama structured plan` and its selected tools.
3. Screenshot of anomaly-triggered trend analysis.
4. Test output showing all tests pass.
5. Architecture and workflow from `SCHEMA.md`.
