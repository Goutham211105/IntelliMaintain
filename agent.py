"""Agent orchestration with validated planning and observable tool selection."""
from dataclasses import dataclass
from typing import Any
import pandas as pd
from tools import (
    validate_sensor_data, summarize_sensor_data, detect_anomalies,
    analyze_trends, assess_risk, recommend_actions, create_report
)
from llm import try_local_llm_plan

@dataclass
class AgentEvent:
    step: str
    status: str
    details: str

class IntelliMaintainAgent:
    """A bounded agent: planner proposes optional tools; Python enforces policy.

    Required validation, risk, recommendation, and reporting stages cannot be
    skipped by the LLM. Trend analysis is invoked when anomalies exist or when
    a validated plan selects it for the user's goal.
    """
    def __init__(self, max_steps: int = 9):
        self.max_steps = max_steps

    def run(self, data: pd.DataFrame, goal: str = "Assess machine condition") -> dict[str, Any]:
        trace: list[dict[str, str]] = []
        def log(step, status, details):
            trace.append({"step": step, "status": status, "details": details})

        log("Understand goal", "complete", f"Goal received: {goal}")
        available_tools = [
            "validate_sensor_data", "summarize_sensor_data", "detect_anomalies",
            "analyze_trends", "assess_risk", "recommend_actions", "create_report"
        ]
        llm_plan = try_local_llm_plan(goal, available_tools)
        if llm_plan:
            planned_tools = llm_plan.get("tools", [])
            rationale = llm_plan.get("rationale", "No rationale supplied.")
            plan_source = "Ollama structured plan"
            log("Plan and select tools", "complete",
                f"Planner: {plan_source}. Optional tools selected: {planned_tools or 'none'}. "
                f"Rationale: {rationale}. Safety policy: validation, risk assessment, "
                "recommendations, and report generation remain mandatory; unknown tools are rejected.")
        else:
            planned_tools = []
            plan_source = "deterministic offline fallback"
            log("Plan and select tools", "complete",
                "Planner: deterministic offline fallback. The agent will validate input, "
                "summarize readings, detect anomalies, run trend analysis if anomalies are "
                "found, then assess risk, recommend actions, and generate a report. "
                "Ollama is optional; no paid API is required.")

        validation = validate_sensor_data(data)
        if not validation["valid"]:
            log("Validate input", "blocked", validation["message"])
            assessment = {
                "risk_level": "UNKNOWN", "anomaly_count": 0,
                "recommended_action": "Fix input data",
                "summary": validation["message"], "recommendations": [validation["message"]]
            }
            report = create_report(goal, validation, {}, [], assessment)
            return {"trace": trace, "validation": validation, "assessment": assessment,
                    "report": report, "planner_source": plan_source, "selected_tools": planned_tools}

        log("Validate input", "complete", validation["message"])
        summary = summarize_sensor_data(data)
        log("Summarize sensor data", "complete",
            f"summarize_sensor_data ran because valid input is required for assessment. "
            f"Analyzed {summary['row_count']} records; available sensors: {', '.join(summary['sensors'])}.")
        anomalies = detect_anomalies(data)
        log("Detect anomalies", "complete",
            f"detect_anomalies ran. Found {len(anomalies)} anomaly flag(s) using configured "
            "thresholds and robust-deviation checks.")

        # Policy-driven dynamic tool selection: anomaly evidence forces follow-up;
        # otherwise the validated LLM plan may request trend analysis for the goal.
        anomaly_sensors = sorted({a["sensor"] for a in anomalies})
        if anomalies:
            run_trends = True
            trend_reason = f"required by policy because anomalies were found in: {', '.join(anomaly_sensors)}"
        elif "analyze_trends" in planned_tools:
            run_trends = True
            trend_reason = "selected by the validated planner to investigate changes over time"
        else:
            run_trends = False
            trend_reason = "skipped: no anomalies were found and the planner did not select trend analysis"

        trend_results = []
        if run_trends and len(trace) < self.max_steps:
            trend_results = analyze_trends(data, anomalies, sensors=None if anomalies else summary["sensors"])
            log("Investigate trends", "complete",
                f"analyze_trends was invoked ({trend_reason}). Returned {len(trend_results)} sensor trend result(s).")
        else:
            log("Investigate trends", "skipped", trend_reason)

        assessment = assess_risk(summary, anomalies, trend_results)
        log("Evaluate risk", "complete",
            f"Risk level: {assessment['risk_level']}; anomaly flags: {assessment['anomaly_count']}; "
            f"increasing trends: {sum(t['direction'] == 'increasing' for t in trend_results)}.")
        assessment["recommendations"] = recommend_actions(assessment, anomalies, trend_results)
        log("Select actions", "complete",
            f"recommend_actions selected {len(assessment['recommendations'])} recommendation(s) "
            "using risk level, flagged sensors, and trend evidence.")
        report = create_report(goal, validation, summary, anomalies, assessment, trend_results)
        log("Generate report", "complete", "create_report combined input status, evidence, risk, recommendations, and limitations.")
        return {
            "trace": trace, "validation": validation, "summary": summary,
            "anomalies": anomalies, "trends": trend_results, "assessment": assessment,
            "report": report, "planner_source": plan_source, "selected_tools": planned_tools,
        }
