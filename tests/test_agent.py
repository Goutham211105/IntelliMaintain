import pandas as pd
from agent import IntelliMaintainAgent
from tools import generate_demo_data, validate_sensor_data, detect_anomalies

def test_demo_data_validates():
    df = generate_demo_data()
    assert validate_sensor_data(df)["valid"] is True

def test_agent_runs_and_returns_report():
    result = IntelliMaintainAgent().run(generate_demo_data(), "Assess machine health")
    assert "assessment" in result
    assert "LIMITATIONS" in result["report"]
    assert len(result["trace"]) >= 6
    assert result["assessment"]["risk_level"] == "HIGH"

def test_invalid_input_is_handled():
    result = IntelliMaintainAgent().run(pd.DataFrame({"x": [1,2,3,4,5]}))
    assert result["assessment"]["risk_level"] == "UNKNOWN"
    assert result["validation"]["valid"] is False

def test_threshold_anomaly_detected():
    df = pd.DataFrame({"vibration_mm_s": [2, 2.1, 2.2, 2.0, 12.0]})
    anomalies = detect_anomalies(df)
    assert any(a["sensor"] == "vibration_mm_s" and a["value"] == 12.0 for a in anomalies)

def test_validated_planner_selection_controls_optional_trend_tool(monkeypatch):
    import agent as agent_module
    monkeypatch.setattr(agent_module, "try_local_llm_plan", lambda goal, tools: {
        "tools": ["analyze_trends"], "rationale": "The goal asks for trend analysis."
    })
    df = pd.DataFrame({
        "vibration_mm_s": [3.0] * 10,
        "temperature_c": [65.0] * 10,
    })
    result = IntelliMaintainAgent().run(df, "Review trends over time")
    assert result["anomalies"] == []
    assert result["trends"]
    assert any("selected by the validated planner" in e["details"] for e in result["trace"])

def test_anomalies_force_trend_analysis_even_if_planner_skips_it(monkeypatch):
    import agent as agent_module
    monkeypatch.setattr(agent_module, "try_local_llm_plan", lambda goal, tools: {
        "tools": [], "rationale": "No optional tools requested."
    })
    result = IntelliMaintainAgent().run(generate_demo_data(), "Assess machine condition")
    assert result["anomalies"]
    assert result["trends"]
    assert any("required by policy because anomalies were found" in e["details"] for e in result["trace"])
