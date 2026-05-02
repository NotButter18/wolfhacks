from pathlib import Path

from flask import Flask, jsonify, render_template, request

from .simulation import ScenarioConfig, build_scenario, simulate


BASE_DIR = Path(__file__).resolve().parent.parent
app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "templates"),
    static_folder=str(BASE_DIR / "static"),
)


@app.get("/")
def index():
    return render_template(
        "index.html",
        default_config=ScenarioConfig(),
    )


@app.post("/simulate")
def run_simulation():
    payload = request.get_json(silent=True) or {}
    scenario = build_scenario(payload)
    result = simulate(scenario)
    return jsonify(result)
