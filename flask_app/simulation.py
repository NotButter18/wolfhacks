from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass
class ScenarioConfig:
    hospital_capacity: int = 220
    normal_inflow: int = 42
    wait_time_hours: float = 3.0
    crisis_multiplier: float = 1.8
    panic_surge: float = 1.4
    proximity_bias: float = 0.75
    wait_time_neglect: float = 0.65
    redirection_compliance: float = 0.35
    pop_up_clinic_capacity: int = 30
    resource_boost: int = 24


def build_scenario(payload: dict[str, Any]) -> ScenarioConfig:
    defaults = ScenarioConfig()
    return ScenarioConfig(
        hospital_capacity=int(payload.get("hospital_capacity", defaults.hospital_capacity)),
        normal_inflow=int(payload.get("normal_inflow", defaults.normal_inflow)),
        wait_time_hours=float(payload.get("wait_time_hours", defaults.wait_time_hours)),
        crisis_multiplier=float(payload.get("crisis_multiplier", defaults.crisis_multiplier)),
        panic_surge=float(payload.get("panic_surge", defaults.panic_surge)),
        proximity_bias=float(payload.get("proximity_bias", defaults.proximity_bias)),
        wait_time_neglect=float(payload.get("wait_time_neglect", defaults.wait_time_neglect)),
        redirection_compliance=float(payload.get("redirection_compliance", defaults.redirection_compliance)),
        pop_up_clinic_capacity=int(payload.get("pop_up_clinic_capacity", defaults.pop_up_clinic_capacity)),
        resource_boost=int(payload.get("resource_boost", defaults.resource_boost)),
    )


def score_label(score: float) -> str:
    if score >= 0.75:
        return "High"
    if score >= 0.4:
        return "Moderate"
    return "Low"


def risk_label(risk: float) -> str:
    if risk >= 0.75:
        return "Critical"
    if risk >= 0.4:
        return "Elevated"
    return "Stable"


def simulate(scenario: ScenarioConfig) -> dict[str, Any]:
    hours = np.arange(0, 13)

    baseline = np.full_like(hours, scenario.normal_inflow, dtype=float)
    crisis_wave = scenario.normal_inflow * scenario.crisis_multiplier * np.exp(-0.22 * hours)
    panic_wave = scenario.normal_inflow * scenario.panic_surge * np.exp(-0.12 * hours)
    total_demand = baseline + crisis_wave + panic_wave

    behavior_pressure = (
        0.45 * scenario.proximity_bias
        + 0.35 * scenario.wait_time_neglect
        + 0.20 * scenario.redirection_compliance
    )
    behavior_multiplier = 0.75 + behavior_pressure
    wait_stress = 1 + (0.06 * scenario.wait_time_hours)
    behavior_adjusted_demand = total_demand * behavior_multiplier * wait_stress

    diversion_effect = scenario.pop_up_clinic_capacity * np.exp(-0.18 * hours)
    staffing_effect = scenario.resource_boost * np.exp(-0.1 * hours)

    mitigated_demand = np.maximum(
        behavior_adjusted_demand - diversion_effect - staffing_effect * 0.35,
        0,
    )

    effective_capacity = scenario.hospital_capacity + staffing_effect
    load_ratio = mitigated_demand / effective_capacity
    overload_risk = np.clip((load_ratio - 0.85) / 0.45, 0, 1)

    overload_time = None
    for hour, ratio in zip(hours, load_ratio):
        if ratio >= 1.0:
            overload_time = int(hour)
            break

    if overload_time is None:
        overload_message = "No overload predicted in the next 12 hours."
    else:
        overload_message = f"Projected overload begins at hour {overload_time}."

    timeline = []
    for hour, load, capacity, risk in zip(hours, mitigated_demand, effective_capacity, overload_risk):
        timeline.append(
            {
                "hour": int(hour),
                "predicted_demand": round(float(load), 1),
                "capacity": round(float(capacity), 1),
                "load_ratio": round(float(load / capacity), 2),
                "risk": round(float(risk), 2),
                "status": "Overloaded" if load >= capacity else "Stable",
            }
        )

    actions = [
        {
            "name": "Public health alert",
            "why": "Reduces panic-driven visits and encourages lower-acuity alternatives.",
            "score": round(0.22 * scenario.panic_surge + 0.10 * scenario.redirection_compliance, 2),
        },
        {
            "name": "Pop-up clinic",
            "why": "Absorbs non-emergency demand before it reaches the hospital.",
            "score": round(0.28 * scenario.pop_up_clinic_capacity / max(1, scenario.normal_inflow), 2),
        },
        {
            "name": "Resource redistribution",
            "why": "Adds internal capacity and slows overload growth.",
            "score": round(0.18 * scenario.resource_boost / max(1, scenario.hospital_capacity), 2),
        },
    ]
    actions.sort(key=lambda item: item["score"], reverse=True)
    for action in actions:
        action["strength"] = score_label(action["score"])

    return {
        "timeline": timeline,
        "insight": {
            "overload_message": overload_message,
            "peak_demand": round(float(np.max(mitigated_demand)), 1),
            "peak_risk": round(float(np.max(overload_risk)), 2),
            "behavior_multiplier": round(float(behavior_multiplier), 2),
            "wait_stress": round(float(wait_stress), 2),
            "current_risk": round(float(overload_risk[-1]), 2),
            "current_status": risk_label(float(overload_risk[-1])),
            "best_action": actions[0]["name"],
        },
        "actions": actions,
    }

