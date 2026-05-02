from flask import Flask, render_template, request, jsonify


app = Flask(__name__)


@app.get("/")
def home():
    return render_template("index.html")


@app.post("/api/variables")
def variables():
    data = request.get_json(force=True)
    hospital_capacity = int(data.get("hospital_capacity", 220))
    patient_inflow = int(data.get("patient_inflow", 42))
    wait_time = float(data.get("wait_time", 3.0))

    return jsonify(
        {
            "hospital_capacity": hospital_capacity,
            "patient_inflow": patient_inflow,
            "wait_time": wait_time,
        }
    )


if __name__ == "__main__":
    app.run(debug=True)
