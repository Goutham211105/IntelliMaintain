"""Deterministic, inspectable tools used by the IntelliMaintain agent."""
from __future__ import annotations
import pandas as pd
import numpy as np

REQUIRED_ANY = ["vibration_mm_s", "temperature_c", "rpm", "current_a"]
LIMITS = {
    "vibration_mm_s": {"high": 7.1, "unit": "mm/s"},
    "temperature_c": {"high": 85.0, "unit": "°C"},
    "rpm": {"low": 500.0, "high": 4000.0, "unit": "rpm"},
    "current_a": {"high": 18.0, "unit": "A"},
}

def generate_demo_data(n: int = 120, seed: int = 17) -> pd.DataFrame:
    """Generate reproducible synthetic sensor readings with a late vibration rise."""
    rng = np.random.default_rng(seed)
    timestamps = pd.date_range("2026-01-01", periods=n, freq="h")
    vibration = rng.normal(3.0, 0.35, n)
    temperature = rng.normal(66.0, 2.2, n)
    rpm = rng.normal(1780, 35, n)
    current = rng.normal(10.2, 0.7, n)
    if n >= 20:
        vibration[-20:] += np.linspace(0.5, 5.5, 20)
        temperature[-8:] += np.linspace(2, 12, 8)
    return pd.DataFrame({
        "timestamp": timestamps,
        "vibration_mm_s": np.round(vibration, 2),
        "temperature_c": np.round(temperature, 2),
        "rpm": np.round(rpm, 1),
        "current_a": np.round(current, 2),
    })

def validate_sensor_data(df: pd.DataFrame) -> dict:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return {"valid": False, "message": "Input is empty or is not a pandas DataFrame."}
    available = [c for c in REQUIRED_ANY if c in df.columns]
    if not available:
        return {"valid": False, "message": "No recognized sensor columns found. Include at least one of: " + ", ".join(REQUIRED_ANY)}
    if len(df) < 5:
        return {"valid": False, "message": "At least 5 readings are required for a meaningful preliminary analysis."}
    non_numeric = [c for c in available if not pd.api.types.is_numeric_dtype(df[c])]
    if non_numeric:
        return {"valid": False, "message": f"Sensor columns must be numeric: {', '.join(non_numeric)}"}
    if df[available].isna().all().all():
        return {"valid": False, "message": "Recognized sensor columns contain no usable numeric values."}
    return {"valid": True, "message": f"Input validated: {len(df)} rows; recognized sensors: {', '.join(available)}."}

def summarize_sensor_data(df: pd.DataFrame) -> dict:
    sensors = [c for c in REQUIRED_ANY if c in df.columns]
    stats = {}
    for col in sensors:
        s = pd.to_numeric(df[col], errors="coerce").dropna()
        stats[col] = {
            "mean": float(s.mean()) if len(s) else None,
            "min": float(s.min()) if len(s) else None,
            "max": float(s.max()) if len(s) else None,
            "latest": float(s.iloc[-1]) if len(s) else None,
        }
    return {"row_count": int(len(df)), "sensors": sensors, "stats": stats}

def detect_anomalies(df: pd.DataFrame) -> list[dict]:
    """Flag threshold violations and large deviations from the sensor median."""
    found = []
    for col, limits in LIMITS.items():
        if col not in df.columns:
            continue
        s = pd.to_numeric(df[col], errors="coerce").dropna()
        if s.empty:
            continue
        # Use physical-style configured limits plus robust MAD outlier detection.
        for idx, value in s.items():
            reason = None
            if "high" in limits and value > limits["high"]:
                reason = f"above configured high threshold ({limits['high']} {limits['unit']})"
            elif "low" in limits and value < limits["low"]:
                reason = f"below configured low threshold ({limits['low']} {limits['unit']})"
            med = float(s.median())
            mad = float((s - med).abs().median())
            robust_z = 0.6745 * (float(value) - med) / mad if mad > 1e-9 else 0.0
            if reason is None and abs(robust_z) >= 4.5:
                reason = f"large robust deviation (robust z-score {robust_z:.1f})"
            if reason:
                found.append({
                    "sensor": col, "row_index": int(idx), "value": float(value),
                    "unit": limits["unit"], "reason": reason,
                })
    return found

def analyze_trends(df: pd.DataFrame, anomalies: list[dict], sensors: list[str] | None = None) -> list[dict]:
    """Analyze flagged sensors, or selected sensors when the planner requests a trend review."""
    results = []
    selected_sensors = sorted({a["sensor"] for a in anomalies}) if anomalies else sorted(set(sensors or []))
    for sensor in selected_sensors:
        if sensor not in df.columns:
            continue
        s = pd.to_numeric(df[sensor], errors="coerce").dropna()
        if len(s) < 5:
            continue
        window = max(3, len(s) // 5)
        first = float(s.iloc[:window].mean())
        last = float(s.iloc[-window:].mean())
        delta = last - first
        pct = (delta / abs(first) * 100.0) if abs(first) > 1e-9 else None
        results.append({
            "sensor": sensor, "early_window_mean": first, "recent_window_mean": last,
            "change": delta, "change_percent": pct,
            "direction": "increasing" if delta > 0 else ("decreasing" if delta < 0 else "stable"),
        })
    return results

def assess_risk(summary: dict, anomalies: list[dict], trends: list[dict]) -> dict:
    count = len(anomalies)
    rising = [t for t in trends if t["direction"] == "increasing"]
    severe = any(a["sensor"] == "vibration_mm_s" and a["value"] > 10 for a in anomalies)
    if severe or count >= 10 or (count >= 4 and rising):
        level, action = "HIGH", "Priority inspection"
    elif count > 0:
        level, action = "MEDIUM", "Schedule inspection"
    else:
        level, action = "LOW", "Continue routine monitoring"
    return {
        "risk_level": level,
        "anomaly_count": count,
        "recommended_action": action,
        "summary": f"Preliminary rule-based assessment: {count} anomaly flag(s); {len(rising)} flagged sensor trend(s) increasing. Risk is {level}.",
    }

def recommend_actions(assessment: dict, anomalies: list[dict], trends: list[dict]) -> list[str]:
    recs = []
    sensors = sorted({a["sensor"] for a in anomalies})
    if assessment["risk_level"] == "HIGH":
        recs.append("Arrange a priority inspection and follow site safety/lockout procedures before intrusive work.")
    elif assessment["risk_level"] == "MEDIUM":
        recs.append("Schedule a maintenance inspection and verify the readings with a calibrated instrument.")
    else:
        recs.append("Continue routine monitoring and compare future readings against the established baseline.")
    for sensor in sensors:
        if sensor == "vibration_mm_s":
            recs.append("Inspect vibration-related causes such as imbalance, misalignment, looseness, and bearing condition.")
        elif sensor == "temperature_c":
            recs.append("Check cooling, lubrication, load, and temperature sensor calibration.")
        elif sensor == "current_a":
            recs.append("Review motor load, supply conditions, and electrical connections.")
        elif sensor == "rpm":
            recs.append("Verify speed sensor readings and compare RPM with the intended operating range.")
    if any(t["direction"] == "increasing" for t in trends):
        recs.append("Review the time trend; an increasing signal warrants follow-up rather than relying on a single reading.")
    recs.append("Confirm recommendations against equipment manuals, operating context, and qualified maintenance personnel.")
    return recs

def create_report(goal: str, validation: dict, summary: dict, anomalies: list, assessment: dict, trends: list | None = None) -> str:
    trends = trends or []
    lines = [
        "INTELLIMAINTAIN — PRELIMINARY MAINTENANCE REPORT",
        "=" * 52,
        f"User goal: {goal}",
        f"Input status: {validation.get('message', 'Not available')}",
        "",
        "ASSESSMENT",
        f"Risk level: {assessment['risk_level']}",
        f"Anomaly flags: {assessment['anomaly_count']}",
        f"Recommended action: {assessment['recommended_action']}",
        assessment["summary"],
        "",
        "ANOMALY EVIDENCE",
    ]
    if anomalies:
        for a in anomalies[:50]:
            lines.append(f"- {a['sensor']} at row {a['row_index']}: {a['value']} {a['unit']} ({a['reason']})")
        if len(anomalies) > 50:
            lines.append(f"- ... plus {len(anomalies) - 50} additional flags")
    else:
        lines.append("- No anomaly flags detected by the configured prototype rules.")
    lines += ["", "TREND FOLLOW-UP"]
    if trends:
        for t in trends:
            lines.append(f"- {t['sensor']}: {t['direction']}; change {t['change']:.3f} ({t['change_percent']:.1f}% where defined).")
    else:
        lines.append("- No follow-up trend analysis was required or available.")
    lines += ["", "RECOMMENDATIONS"]
    for rec in assessment.get("recommendations", []):
        lines.append(f"- {rec}")
    lines += [
        "",
        "LIMITATIONS",
        "- Prototype decision support only; configured thresholds are illustrative, not universal engineering limits.",
        "- Synthetic/demo data may not represent a real asset or failure mechanism.",
        "- This report is not a substitute for equipment-specific standards or qualified engineering judgement.",
    ]
    return "\n".join(lines)
