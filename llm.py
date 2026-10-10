"""Optional structured local-LLM planner for IntelliMaintain.

The model may request only allowlisted analysis tools. The orchestrator validates
the plan and always enforces required tools and the safe execution order.
"""
from __future__ import annotations
import json
import os
import requests

ALLOWED_TOOLS = {
    "validate_sensor_data", "summarize_sensor_data", "detect_anomalies",
    "analyze_trends", "assess_risk", "recommend_actions", "create_report",
}

def try_local_llm_plan(goal: str, available_tools: list[str]) -> dict | None:
    """Return a validated structured plan from Ollama, or None when unavailable.

    Expected JSON: {"tools": ["analyze_trends"], "rationale": "..."}.
    Only optional tool selection is accepted from the model; required stages and
    execution order are enforced by agent.py.
    """
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
    model = os.getenv("OLLAMA_MODEL", "llama3.2")
    allowed = [tool for tool in available_tools if tool in ALLOWED_TOOLS]
    prompt = (
        "You are the planning component of a predictive-maintenance prototype. "
        "Choose which analysis tools would add value for the user's goal. "
        "Return ONLY valid JSON with keys tools and rationale. tools must be a list "
        "containing only names from this allowlist: " + json.dumps(allowed) + ". "
        "Do not include validate_sensor_data, assess_risk, recommend_actions, or "
        "create_report in your tools list because the orchestrator always runs these "
        "required stages when input is valid. Select analyze_trends if the user asks "
        "for trends, changes over time, progression, or if a follow-up trend check is useful. "
        "Never claim a diagnosis or real-world action. User goal: " + goal
    )
    try:
        response = requests.post(
            f"{host}/api/chat",
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "format": "json",
                "options": {"temperature": 0},
            },
            timeout=12,
        )
        response.raise_for_status()
        content = response.json().get("message", {}).get("content", "")
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            return None
        tools = parsed.get("tools", [])
        rationale = parsed.get("rationale", "")
        if not isinstance(tools, list) or not all(isinstance(t, str) for t in tools):
            return None
        # Reject the entire plan if it tries to invoke unknown tools.
        if any(t not in allowed for t in tools):
            return None
        # Deduplicate while preserving model order. Only optional tools are accepted.
        optional = [t for t in tools if t in {"summarize_sensor_data", "detect_anomalies", "analyze_trends"}]
        return {"tools": list(dict.fromkeys(optional)), "rationale": str(rationale)[:600]}
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return None
