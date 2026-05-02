import json
from datetime import datetime, timedelta
from pathlib import Path

from flask import Flask, render_template, request


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "templates"),
    static_folder=str(BASE_DIR / "static"),
)


HOSPITAL = {
    "name": "Brampton Care Network Sample",
    "address": "Synthetic sites mapped onto Brampton for the hackathon demo",
    "source": "Synthetic data only",
}

SCENARIO_FILES = {
    "low": DATA_DIR / "low_status" / "snapshot.json",
    "normal": DATA_DIR / "normal_status" / "snapshot.json",
    "condition_x": DATA_DIR / "condition_x" / "snapshot.json",
}


def get_scenario() -> str:
    scenario = request.args.get("scenario", "normal").strip().lower()
    return scenario if scenario in SCENARIO_FILES else "normal"


def load_snapshot(scenario: str) -> dict:
    path = SCENARIO_FILES[scenario]
    with path.open("r", encoding="utf-8") as handle:
        snapshot = json.load(handle)
    snapshot["scenario_key"] = scenario
    return snapshot


def build_behavior_engine(snapshot: dict) -> dict:
    capacity = snapshot["hospital_capacity"]
    inflow = snapshot["patient_inflow"]
    wait_time = snapshot["wait_time_hours"]

    proximity_bias = round(min(0.96, 0.48 + (inflow / capacity) * 0.4), 2)
    wait_time_neglect = round(min(0.97, 0.34 + (wait_time / 10) * 0.6), 2)
    panic_surge = round(min(0.99, 0.45 + (inflow / max(1, capacity)) * 0.35 + (wait_time / 12) * 0.2), 2)

    return {
        "proximity_bias": proximity_bias,
        "wait_time_neglect": wait_time_neglect,
        "panic_surge": panic_surge,
        "explanation": [
            "Proximity bias rises when the nearest emergency department becomes the default choice.",
            "Wait-time neglect increases when expected delays are already high.",
            "Panic surge grows when arrival pressure rises faster than capacity.",
        ],
        "sources": ["Synthetic sample data"],
    }


def build_prediction_engine(snapshot: dict, behavior: dict) -> dict:
    capacity = snapshot["hospital_capacity"]
    inflow = snapshot["patient_inflow"]
    wait_time = snapshot["wait_time_hours"]

    behavior_multiplier = 1 + (behavior["proximity_bias"] * 0.45) + (behavior["wait_time_neglect"] * 0.25) + (behavior["panic_surge"] * 0.55)
    adjusted_demand = round(inflow * behavior_multiplier, 1)
    projected_wait = round(wait_time * (1 + behavior["panic_surge"] * 0.85 + behavior["wait_time_neglect"] * 0.35), 1)

    demand_pressure = adjusted_demand / capacity
    overload_risk = round(min(0.99, demand_pressure), 2)

    if overload_risk >= 0.9:
        status = "Critical"
        horizon = "Immediate action needed"
    elif overload_risk >= 0.7:
        status = "Elevated"
        horizon = "High risk in the next few hours"
    else:
        status = "Stable"
        horizon = "Manageable with intervention"

    actions = [
        {
            "name": "Public health alert",
            "reason": "Best when panic surge is high. It lowers unnecessary arrivals and calms demand.",
            "score": round(min(0.99, behavior["panic_surge"] * 0.78 + behavior["wait_time_neglect"] * 0.12), 2),
        },
        {
            "name": "Redirect non-urgent patients",
            "reason": "Best when proximity bias is strong. It pushes lower-acuity cases to other care options.",
            "score": round(min(0.99, behavior["proximity_bias"] * 0.72 + behavior["wait_time_neglect"] * 0.18), 2),
        },
        {
            "name": "Activate pop-up support",
            "reason": "Best when demand is above capacity. It creates an overflow buffer outside the main ED.",
            "score": round(min(0.99, demand_pressure * 0.82), 2),
        },
        {
            "name": "Redistribute resources",
            "reason": "Best when overload is near or above capacity. It adds internal resilience fast.",
            "score": round(min(0.99, demand_pressure * 0.7 + behavior["panic_surge"] * 0.15), 2),
        },
    ]
    actions.sort(key=lambda item: item["score"], reverse=True)

    timeline = []
    base_hourly_growth = 1 + (behavior["panic_surge"] * 0.08)
    mitigation = 1 - (actions[0]["score"] * 0.15)
    for hour in range(0, 7):
        forecast_demand = round(adjusted_demand * (base_hourly_growth ** hour) * mitigation, 1)
        forecast_ratio = round(forecast_demand / capacity, 2)
        timeline.append(
            {
                "hour": hour,
                "forecast_demand": forecast_demand,
                "capacity": capacity,
                "ratio": forecast_ratio,
                "status": "Critical" if forecast_ratio >= 1 else "Elevated" if forecast_ratio >= 0.85 else "Stable",
            }
        )

    hospitals = [
        {
            "id": "central_ed",
            "name": "Central ED",
            "lat": 43.7317,
            "lng": -79.7624,
            "capacity_share": 0.48,
            "kind": "hospital",
        },
        {
            "id": "north_urgent",
            "name": "North Urgent Site",
            "lat": 43.7736,
            "lng": -79.7301,
            "capacity_share": 0.28,
            "kind": "urgent",
        },
        {
            "id": "west_popup",
            "name": "West Pop-up Clinic",
            "lat": 43.6668,
            "lng": -79.8187,
            "capacity_share": 0.24,
            "kind": "popup",
        },
    ]

    origins = [
        {"name": "Mount Pleasant", "lat": 43.7041, "lng": -79.8316, "weight": 0.18},
        {"name": "Downtown Brampton", "lat": 43.6865, "lng": -79.7613, "weight": 0.17},
        {"name": "Bramalea", "lat": 43.7153, "lng": -79.7215, "weight": 0.22},
        {"name": "Springdale", "lat": 43.7577, "lng": -79.7362, "weight": 0.20},
        {"name": "Heart Lake", "lat": 43.7452, "lng": -79.7748, "weight": 0.12},
        {"name": "Creditview", "lat": 43.6495, "lng": -79.8078, "weight": 0.11},
    ]

    base_time = datetime(2026, 5, 2, 8, 0)
    time_windows = []
    hourly_growth = 1 + (behavior["panic_surge"] * 0.05)
    for index in range(4):
        window_start = base_time + timedelta(hours=index)
        window_end = window_start + timedelta(hours=1)
        window_demand = round(adjusted_demand * (hourly_growth ** index), 1)
        window_pressure = round(window_demand / capacity, 2)
        time_windows.append(
            {
                "id": f"window_{index}",
                "label": window_start.strftime("%b %d"),
                "time_range": f"{window_start.strftime('%I:%M %p')} - {window_end.strftime('%I:%M %p')}",
                "timestamp": window_start.isoformat(),
                "spawn_multiplier": round(0.9 + (index * 0.28) + behavior["panic_surge"] * 0.18, 2),
                "pressure": window_pressure,
                "forecast_demand": window_demand,
                "status": "Critical" if window_pressure >= 1 else "Elevated" if window_pressure >= 0.85 else "Stable",
            }
        )

    crisis_threshold = round(capacity * 0.92, 1)

    return {
        "adjusted_demand": adjusted_demand,
        "projected_wait": projected_wait,
        "overload_risk": overload_risk,
        "status": status,
        "horizon": horizon,
        "actions": actions,
        "timeline": timeline,
        "simulation": {
            "city": "Brampton",
            "map_center": {"lat": 43.7315, "lng": -79.7624},
            "map_zoom": 12,
            "hospitals": hospitals,
            "origins": origins,
            "time_windows": time_windows,
            "crisis_threshold": crisis_threshold,
            "dot_spawn_rate": round(2 + behavior["panic_surge"] * 3, 2),
            "ambulance_share": round(0.08 + behavior["panic_surge"] * 0.05, 2),
            "car_share": round(0.52 + behavior["proximity_bias"] * 0.12, 2),
            "foot_share": round(0.40 - behavior["panic_surge"] * 0.04, 2),
        },
    }


@app.get("/")
def home():
    scenario = get_scenario()
    snapshot = load_snapshot(scenario)
    return render_template(
        "index.html",
        hospital=HOSPITAL,
        snapshot=snapshot,
        scenario=scenario,
    )


@app.get("/behavior-engine")
def behavior_engine():
    scenario = get_scenario()
    snapshot = load_snapshot(scenario)
    behavior = build_behavior_engine(snapshot)
    return render_template(
        "behavior_engine.html",
        hospital=HOSPITAL,
        snapshot=snapshot,
        behavior=behavior,
        scenario=scenario,
    )


@app.get("/prediction-engine")
def prediction_engine():
    scenario = get_scenario()
    snapshot = load_snapshot(scenario)
    behavior = build_behavior_engine(snapshot)
    prediction = build_prediction_engine(snapshot, behavior)
    return render_template(
        "prediction_engine.html",
        hospital=HOSPITAL,
        snapshot=snapshot,
        behavior=behavior,
        prediction=prediction,
        scenario=scenario,
    )


if __name__ == "__main__":
    app.run(debug=True)
