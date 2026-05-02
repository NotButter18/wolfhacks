import json
from datetime import datetime, timedelta
from pathlib import Path

import requests
from flask import Flask, render_template, request, jsonify


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

# ── OSRM route cache ──
_route_cache: dict[str, list] = {}
OSRM_BASE = "https://router.project-osrm.org/route/v1/driving"


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
            "capacity_share": 0.30,
            "kind": "hospital",
        },
        {
            "id": "north_urgent",
            "name": "North Urgent Site",
            "lat": 43.7736,
            "lng": -79.7301,
            "capacity_share": 0.20,
            "kind": "urgent",
        },
        {
            "id": "west_popup",
            "name": "West Pop-up Clinic",
            "lat": 43.6668,
            "lng": -79.8187,
            "capacity_share": 0.16,
            "kind": "popup",
        },
        {
            "id": "east_medical",
            "name": "East Brampton Medical",
            "lat": 43.7200,
            "lng": -79.6950,
            "capacity_share": 0.18,
            "kind": "hospital",
        },
        {
            "id": "south_urgent",
            "name": "South Brampton Urgent Care",
            "lat": 43.6450,
            "lng": -79.7500,
            "capacity_share": 0.16,
            "kind": "urgent",
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

    base_time = datetime(2030, 5, 2, 8, 0)
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

    # Cars + ambulances only (no foot traffic)
    # Exponential spawn rate: Low ≈ 1.5, Normal ≈ 4, Crisis ≈ 12+
    load_ratio = inflow / max(1, capacity)
    spawn_rate = round(1.0 + load_ratio * 18 + behavior["panic_surge"] * 5, 2)
    # Ambulance share rises sharply in crisis
    ambulance_share = round(min(0.35, 0.08 + behavior["panic_surge"] * 0.15 + load_ratio * 0.2), 2)
    car_share = round(1.0 - ambulance_share, 2)

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
            "dot_spawn_rate": spawn_rate,
            "ambulance_share": ambulance_share,
            "car_share": car_share,
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


SOLUTIONS = [
    {
        "id": "patient_redirection",
        "name": "Patient Redirection",
        "icon": "↗",
        "description": "Redirect non-urgent patients away from the most overloaded ED to less crowded facilities. Reduces Central ED load by 50% and distributes patients to surrounding sites.",
        "effect": "Rebalances patient flow across all 5 facilities, preventing single-point overload.",
        "spawn_multiplier": 0.85,
        "capacity_override": {
            "central_ed": 0.12,
            "north_urgent": 0.28,
            "west_popup": 0.22,
            "east_medical": 0.22,
            "south_urgent": 0.16,
        },
        "diagram_html": """
        <div class="mini-diagram">
          <div class="md-col">
            <div class="md-node">Inbound<br>Traffic</div>
          </div>
          <div class="md-arrow">→</div>
          <div class="md-col">
            <div class="md-node highlight">Surrounding Clinics<br><small>Redirect 50%</small></div>
            <div class="md-node">Central ED<br><small>Emergencies Only</small></div>
          </div>
        </div>
        """
    },
    {
        "id": "popup_clinics",
        "name": "Pop-up Clinics",
        "icon": "⛺",
        "description": "Deploy 2 temporary pop-up clinics in high-demand zones (Bramalea and Mount Pleasant) to absorb overflow before patients reach the hospital.",
        "effect": "Adds 2 new care points, absorbing ~30% of inbound traffic before it reaches hospitals.",
        "spawn_multiplier": 0.70,
        "extra_hospitals": [
            {"id": "popup_bramalea", "name": "Pop-up Bramalea", "lat": 43.7100, "lng": -79.7100, "capacity_share": 0.14, "kind": "popup"},
            {"id": "popup_mount_pleasant", "name": "Pop-up Mt Pleasant", "lat": 43.6950, "lng": -79.8200, "capacity_share": 0.14, "kind": "popup"},
        ],
        "capacity_override": {
            "central_ed": 0.20,
            "north_urgent": 0.16,
            "west_popup": 0.12,
            "east_medical": 0.14,
            "south_urgent": 0.10,
        },
        "diagram_html": """
        <div class="mini-diagram">
          <div class="md-col">
            <div class="md-node">Patient<br>Origin</div>
          </div>
          <div class="md-arrow">→</div>
          <div class="md-col">
            <div class="md-node highlight">Pop-up Clinics<br><small>Absorb 30%</small></div>
            <div class="md-node">Main Hospitals<br><small>Remaining</small></div>
          </div>
        </div>
        """
    },
    {
        "id": "public_health_alerts",
        "name": "Public Health Alerts",
        "icon": "📢",
        "description": "Issue public health alerts via SMS, social media, and local news advising non-emergency patients to use telehealth or wait. Reduces unnecessary ED visits by up to 45%.",
        "effect": "Dramatic reduction in incoming vehicle volume. Only genuine emergencies arrive.",
        "spawn_multiplier": 0.45,
        "capacity_override": None,
        "diagram_html": """
        <div class="mini-diagram">
          <div class="md-col">
            <div class="md-node">Public<br>Alerts</div>
          </div>
          <div class="md-arrow">→</div>
          <div class="md-col">
            <div class="md-node highlight">Telehealth / Home<br><small>Divert 45%</small></div>
            <div class="md-node">Hospitals<br><small>Emergencies</small></div>
          </div>
        </div>
        """
    },
    {
        "id": "resource_redistribution",
        "name": "Resource Redistribution",
        "icon": "🔄",
        "description": "Redistribute doctors, nurses, and equipment from lower-demand sites to the overloaded Central ED. Increases throughput without adding new facilities.",
        "effect": "Central ED processes patients 40% faster, reducing queue buildup and ambulance wait.",
        "spawn_multiplier": 0.75,
        "capacity_override": {
            "central_ed": 0.38,
            "north_urgent": 0.18,
            "west_popup": 0.14,
            "east_medical": 0.16,
            "south_urgent": 0.14,
        },
        "diagram_html": """
        <div class="mini-diagram">
          <div class="md-col">
            <div class="md-node">Lower-demand Sites<br><small>Staff & Equip</small></div>
          </div>
          <div class="md-arrow">→</div>
          <div class="md-col">
            <div class="md-node highlight">Central ED<br><small>+40% Throughput</small></div>
          </div>
        </div>
        """
    },
]


@app.get("/solutions")
def solutions_page():
    scenario = get_scenario()
    snapshot = load_snapshot(scenario)
    behavior = build_behavior_engine(snapshot)
    prediction = build_prediction_engine(snapshot, behavior)

    # Build per-solution simulation configs
    solution_configs = []
    for sol in SOLUTIONS:
        hospitals = list(prediction["simulation"]["hospitals"])
        if sol.get("extra_hospitals"):
            hospitals = hospitals + sol["extra_hospitals"]

        if sol["capacity_override"]:
            for h in hospitals:
                if h["id"] in sol["capacity_override"]:
                    h = dict(h)
                    h["capacity_share"] = sol["capacity_override"][h["id"]]
                    # Replace in list
                    hospitals = [h if x["id"] == h["id"] else x for x in hospitals]

        sol_sim = {
            "city": "Brampton",
            "map_center": prediction["simulation"]["map_center"],
            "map_zoom": prediction["simulation"]["map_zoom"],
            "hospitals": hospitals,
            "origins": prediction["simulation"]["origins"],
            "dot_spawn_rate": round(prediction["simulation"]["dot_spawn_rate"] * sol["spawn_multiplier"], 2),
            "ambulance_share": prediction["simulation"]["ambulance_share"],
            "car_share": prediction["simulation"]["car_share"],
        }

        solution_configs.append({
            **sol,
            "simulation": sol_sim,
        })

    # ── Smart recommendation engine ──
    # Score each solution against the current crisis conditions
    capacity = snapshot["hospital_capacity"]
    inflow = snapshot["patient_inflow"]
    wait_time = snapshot["wait_time_hours"]
    load_ratio = inflow / max(1, capacity)
    proximity = behavior["proximity_bias"]
    panic = behavior["panic_surge"]

    scores = {}

    # Patient Redirection — best when traffic is high (high inflow + proximity bias)
    scores["patient_redirection"] = (
        load_ratio * 0.45 + proximity * 0.35 + (wait_time / 10) * 0.20
    )

    # Pop-up Clinics — best when overcrowding (capacity nearly full, long waits)
    scores["popup_clinics"] = (
        load_ratio * 0.55 + (wait_time / 10) * 0.30 + panic * 0.15
    )

    # Public Health Alerts — best when panic is high (unnecessary visits flooding)
    scores["public_health_alerts"] = (
        panic * 0.50 + (wait_time / 10) * 0.25 + load_ratio * 0.25
    )

    # Resource Redistribution — best when load is moderate but uneven
    scores["resource_redistribution"] = (
        proximity * 0.40 + load_ratio * 0.30 + panic * 0.30
    )

    best_id = max(scores, key=scores.get)
    recommended_index = next(
        i for i, sol in enumerate(solution_configs) if sol["id"] == best_id
    )

    reasons = {
        "patient_redirection": f"High traffic detected — inflow is {inflow} patients/hr with strong proximity bias ({proximity}). Redirecting patients to less crowded facilities is the most effective response.",
        "popup_clinics": f"Overcrowding detected — hospitals are at {round(load_ratio * 100)}% capacity with {wait_time}hr waits. Deploying pop-up clinics adds immediate overflow capacity.",
        "public_health_alerts": f"Panic surge is high ({panic}) — many non-urgent patients are arriving unnecessarily. Public alerts can reduce volume by up to 45%.",
        "resource_redistribution": f"Uneven load distribution — proximity bias is {proximity} and demand is growing. Shifting resources to overloaded sites increases throughput fastest.",
    }

    return render_template(
        "solutions.html",
        hospital=HOSPITAL,
        snapshot=snapshot,
        prediction=prediction,
        solutions=solution_configs,
        scenario=scenario,
        recommended_index=recommended_index,
        recommended_reason=reasons[best_id],
    )


@app.get("/api/route")
def api_route():
    """Proxy to OSRM for real road geometry between two coordinates."""
    try:
        olat = float(request.args["origin_lat"])
        olng = float(request.args["origin_lng"])
        dlat = float(request.args["dest_lat"])
        dlng = float(request.args["dest_lng"])
    except (KeyError, ValueError):
        return jsonify({"error": "Missing or invalid coordinates"}), 400

    cache_key = f"{olat},{olng}->{dlat},{dlng}"
    if cache_key in _route_cache:
        return jsonify({"coordinates": _route_cache[cache_key]})

    url = f"{OSRM_BASE}/{olng},{olat};{dlng},{dlat}?overview=full&geometries=geojson"
    try:
        resp = requests.get(url, timeout=8)
        data = resp.json()
        if data.get("code") != "Ok" or not data.get("routes"):
            return jsonify({"error": "No route found"}), 404
        coords = data["routes"][0]["geometry"]["coordinates"]
        # OSRM returns [lng, lat] — convert to [lat, lng]
        latlngs = [[c[1], c[0]] for c in coords]
        _route_cache[cache_key] = latlngs
        return jsonify({"coordinates": latlngs})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 502


if __name__ == "__main__":
    app.run(debug=True)
