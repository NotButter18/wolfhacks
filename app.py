from dataclasses import dataclass

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st


st.set_page_config(
    page_title="Synapse",
    page_icon="S",
    layout="wide",
    initial_sidebar_state="expanded",
)


@dataclass
class ScenarioConfig:
    hospital_capacity: int
    normal_inflow: int
    wait_time_hours: float
    crisis_multiplier: float
    panic_surge: float
    proximity_bias: float
    wait_time_neglect: float
    redirection_compliance: float
    pop_up_clinic_capacity: int
    resource_boost: int


def build_scenario(
    hospital_capacity: int,
    normal_inflow: int,
    wait_time_hours: float,
    crisis_multiplier: float,
    panic_surge: float,
    proximity_bias: float,
    wait_time_neglect: float,
    redirection_compliance: float,
    pop_up_clinic_capacity: int,
    resource_boost: int,
) -> ScenarioConfig:
    return ScenarioConfig(
        hospital_capacity=hospital_capacity,
        normal_inflow=normal_inflow,
        wait_time_hours=wait_time_hours,
        crisis_multiplier=crisis_multiplier,
        panic_surge=panic_surge,
        proximity_bias=proximity_bias,
        wait_time_neglect=wait_time_neglect,
        redirection_compliance=redirection_compliance,
        pop_up_clinic_capacity=pop_up_clinic_capacity,
        resource_boost=resource_boost,
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


def risk_color(risk: float) -> str:
    if risk >= 0.75:
        return "#d7263d"
    if risk >= 0.4:
        return "#f4a261"
    return "#2a9d8f"


def simulate(scenario: ScenarioConfig) -> tuple[pd.DataFrame, dict]:
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

    rows = []
    for hour, load, capacity, risk in zip(hours, mitigated_demand, effective_capacity, overload_risk):
        rows.append(
            {
                "Hour": int(hour),
                "Predicted Demand": round(float(load), 1),
                "Capacity": round(float(capacity), 1),
                "Load Ratio": round(float(load / capacity), 2),
                "Risk": round(float(risk), 2),
                "Status": "Overloaded" if load >= capacity else "Stable",
            }
        )

    df = pd.DataFrame(rows)

    action_scores = [
        (
            "Public health alert",
            max(0.0, 0.22 * scenario.panic_surge + 0.10 * scenario.redirection_compliance),
            "Reduces panic-driven visits and encourages lower-acuity alternatives.",
        ),
        (
            "Pop-up clinic",
            max(0.0, 0.28 * scenario.pop_up_clinic_capacity / max(1, scenario.normal_inflow)),
            "Absorbs non-emergency demand before it reaches the hospital.",
        ),
        (
            "Resource redistribution",
            max(0.0, 0.18 * scenario.resource_boost / max(1, scenario.hospital_capacity)),
            "Adds internal capacity and slows overload growth.",
        ),
    ]
    action_scores.sort(key=lambda item: item[1], reverse=True)

    insight = {
        "overload_message": overload_message,
        "peak_demand": float(df["Predicted Demand"].max()),
        "peak_risk": float(df["Risk"].max()),
        "best_action": action_scores[0][0],
        "best_action_score": action_scores[0][1],
        "behavior_multiplier": behavior_multiplier,
        "wait_stress": wait_stress,
    }
    return df, insight


st.markdown(
    """
    <style>
        .block-container { padding-top: 1.0rem; padding-bottom: 2rem; }
        .stApp {
            background:
                radial-gradient(circle at top left, rgba(0, 180, 216, 0.12), transparent 35%),
                radial-gradient(circle at top right, rgba(76, 201, 240, 0.10), transparent 28%),
                linear-gradient(180deg, #07121f 0%, #0b1826 22%, #f6f8fb 22%, #f6f8fb 100%);
        }
        .hero {
            padding: 1.4rem 1.5rem;
            border-radius: 1.2rem;
            background: linear-gradient(135deg, #071f33 0%, #12324d 45%, #176b87 100%);
            color: white;
            border: 1px solid rgba(255,255,255,0.12);
            box-shadow: 0 18px 40px rgba(3, 11, 21, 0.28);
        }
        .hero h1 { margin-bottom: 0.2rem; }
        .hero p { margin-top: 0.35rem; font-size: 1rem; opacity: 0.94; max-width: 920px; }
        .hero-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 0.9rem;
            margin-top: 1rem;
        }
        .glass-card {
            background: rgba(255,255,255,0.10);
            border: 1px solid rgba(255,255,255,0.15);
            border-radius: 1rem;
            padding: 0.9rem 1rem;
            backdrop-filter: blur(8px);
        }
        .glass-card h3 {
            margin: 0 0 0.2rem 0;
            font-size: 0.95rem;
            color: #dff7ff;
        }
        .glass-card p {
            margin: 0;
            color: rgba(255,255,255,0.92);
            font-size: 0.9rem;
        }
        .section-note {
            background: #ffffff;
            border: 1px solid #dce5ee;
            border-left: 6px solid #176b87;
            padding: 0.9rem 1rem;
            border-radius: 0.9rem;
            margin: 0.25rem 0 1rem 0;
        }
        .status-row {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 0.75rem;
            margin-top: 0.75rem;
        }
        .status-card {
            background: white;
            border: 1px solid #d9e2ec;
            border-radius: 0.95rem;
            padding: 0.95rem;
            box-shadow: 0 10px 25px rgba(15, 23, 42, 0.05);
        }
        .status-card .label {
            font-size: 0.82rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: #6b7b8c;
        }
        .status-card .value {
            font-size: 1.4rem;
            font-weight: 700;
            margin-top: 0.2rem;
            color: #0f172a;
        }
        .status-card .sub {
            margin-top: 0.25rem;
            color: #52616b;
            font-size: 0.88rem;
        }
        .action-card {
            background: white;
            border: 1px solid #d9e2ec;
            border-radius: 1rem;
            padding: 0.95rem 1rem;
            margin-bottom: 0.75rem;
            box-shadow: 0 10px 25px rgba(15, 23, 42, 0.05);
        }
        .action-title {
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-weight: 700;
            color: #0f172a;
            margin-bottom: 0.35rem;
        }
        .pill {
            padding: 0.22rem 0.55rem;
            border-radius: 999px;
            font-size: 0.75rem;
            font-weight: 700;
            color: white;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


st.markdown(
    """
    <div class="hero">
        <h1>Synapse</h1>
        <p>Behavior-aware healthcare overload prediction for Brampton’s single main hospital during Condition X.</p>
        <div class="hero-grid">
            <div class="glass-card">
                <h3>Problem</h3>
                <p>One emergency site, rising demand, and stress-driven patient decisions.</p>
            </div>
            <div class="glass-card">
                <h3>Core Model</h3>
                <p>Behavior engine predicts how proximity bias and panic amplify arrivals.</p>
            </div>
            <div class="glass-card">
                <h3>Outcome</h3>
                <p>Forecast overload early and recommend the best offloading action.</p>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.write("")

st.markdown(
    """
    <div class="section-note">
        <strong>Why this matches the problem:</strong> Brampton has limited emergency capacity, so the challenge is not
        just showing a wait time. Synapse simulates how people react under stress and predicts when the system will tip
        from manageable to overloaded.
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Scenario Controls")
    st.caption("Tune the crisis and behavior assumptions for the demo.")
    hospital_capacity = st.slider("Hospital capacity", 50, 500, 220, 10)
    normal_inflow = st.slider("Normal patient inflow / hour", 10, 120, 42, 1)
    wait_time_hours = st.slider("Current wait time (hours)", 0.0, 12.0, 3.0, 0.5)
    crisis_multiplier = st.slider("Condition X demand spike", 0.0, 4.0, 1.8, 0.1)
    panic_surge = st.slider("Panic surge strength", 0.0, 4.0, 1.4, 0.1)
    proximity_bias = st.slider("Proximity bias", 0.0, 1.0, 0.75, 0.05)
    wait_time_neglect = st.slider("Wait-time neglect", 0.0, 1.0, 0.65, 0.05)
    redirection_compliance = st.slider("Redirection compliance", 0.0, 1.0, 0.35, 0.05)
    pop_up_clinic_capacity = st.slider("Pop-up clinic relief", 0, 150, 30, 5)
    resource_boost = st.slider("Resource redistribution gain", 0, 120, 24, 3)
    run = st.button("Simulate Condition X", use_container_width=True)


scenario = build_scenario(
    hospital_capacity=hospital_capacity,
    normal_inflow=normal_inflow,
    wait_time_hours=wait_time_hours,
    crisis_multiplier=crisis_multiplier,
    panic_surge=panic_surge,
    proximity_bias=proximity_bias,
    wait_time_neglect=wait_time_neglect,
    redirection_compliance=redirection_compliance,
    pop_up_clinic_capacity=pop_up_clinic_capacity,
    resource_boost=resource_boost,
)

if "result" not in st.session_state or run:
    df, insight = simulate(scenario)
    st.session_state["result"] = df
    st.session_state["insight"] = insight

df = st.session_state["result"]
insight = st.session_state["insight"]

col1, col2, col3, col4 = st.columns(4)
col1.metric("Peak demand", f"{insight['peak_demand']:.0f}", help="Highest predicted inflow in the 12-hour window.")
col2.metric("Peak risk", f"{insight['peak_risk']:.0%}", help="Highest overload risk score.")
col3.metric("Behavior pressure", f"{insight['behavior_multiplier']:.2f}x", help="How strongly patient behavior amplifies demand.")
col4.metric("Best action", insight["best_action"], help="Highest-scoring mitigation recommendation.")

st.write("")

left, right = st.columns([1.35, 0.9])

with left:
    st.subheader("Prediction Over Time")
    fig = px.line(
        df,
        x="Hour",
        y=["Predicted Demand", "Capacity"],
        markers=True,
        title="Demand vs Capacity",
        color_discrete_map={
            "Predicted Demand": "#176b87",
            "Capacity": "#d7263d",
        },
    )
    fig.update_layout(
        legend_title_text="",
        paper_bgcolor="white",
        plot_bgcolor="white",
        margin=dict(l=10, r=10, t=50, b=10),
        title_font=dict(size=18),
    )
    st.plotly_chart(fig, use_container_width=True)

    risk_fig = px.area(
        df,
        x="Hour",
        y="Risk",
        title="Overload Risk Forecast",
        color_discrete_sequence=["#176b87"],
    )
    risk_fig.update_yaxes(range=[0, 1])
    risk_fig.update_layout(
        paper_bgcolor="white",
        plot_bgcolor="white",
        margin=dict(l=10, r=10, t=50, b=10),
        title_font=dict(size=18),
    )
    st.plotly_chart(risk_fig, use_container_width=True)

with right:
    st.subheader("System Status")
    current_risk = float(df["Risk"].iloc[-1])
    st.markdown(
        f"""
        <div class="status-card" style="border-left: 6px solid {risk_color(current_risk)};">
            <div class="label">Current status</div>
            <div class="value">{risk_label(current_risk)}</div>
            <div class="sub">{insight['overload_message']}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div class="status-row">
            <div class="status-card">
                <div class="label">Wait stress</div>
                <div class="value">{insight['wait_stress']:.2f}x</div>
                <div class="sub">Longer waits push more people into stress-driven decisions.</div>
            </div>
            <div class="status-card">
                <div class="label">Peak demand</div>
                <div class="value">{insight['peak_demand']:.0f}</div>
                <div class="sub">Highest simulated arrivals in the next 12 hours.</div>
            </div>
            <div class="status-card">
                <div class="label">Peak risk</div>
                <div class="value">{insight['peak_risk']:.0%}</div>
                <div class="sub">Chance the hospital enters overload territory.</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("### Recommended Actions")
    actions = [
        {
            "Action": "Public health alert",
            "Why": "Reduces panic-driven visits and encourages lower-acuity alternatives.",
            "Score": round(0.22 * scenario.panic_surge + 0.10 * scenario.redirection_compliance, 2),
        },
        {
            "Action": "Pop-up clinic",
            "Why": "Absorbs non-emergency demand before it reaches the hospital.",
            "Score": round(0.28 * scenario.pop_up_clinic_capacity / max(1, scenario.normal_inflow), 2),
        },
        {
            "Action": "Resource redistribution",
            "Why": "Adds internal capacity and slows overload growth.",
            "Score": round(0.18 * scenario.resource_boost / max(1, scenario.hospital_capacity), 2),
        },
    ]
    for row in actions:
        row["Strength"] = score_label(row["Score"])
    actions = sorted(actions, key=lambda item: item["Score"], reverse=True)

    for row in actions:
        color = {"High": "#d7263d", "Moderate": "#f4a261", "Low": "#2a9d8f"}[row["Strength"]]
        st.markdown(
            f"""
            <div class="action-card">
                <div class="action-title">
                    <span>{row["Action"]}</span>
                    <span class="pill" style="background:{color};">{row["Strength"]}</span>
                </div>
                <div style="color:#475569; margin-bottom:0.45rem;">{row["Why"]}</div>
                <div style="font-size:0.9rem; color:#0f172a;">Score: <strong>{row["Score"]:.2f}</strong></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.write("")
st.subheader("Hourly Simulation Table")
styled_df = df.style.background_gradient(subset=["Risk"], cmap="RdYlGn_r").format({"Risk": "{:.0%}", "Load Ratio": "{:.2f}"})
st.dataframe(styled_df, hide_index=True, use_container_width=True)

st.write("")
st.subheader("System Flow")
st.markdown(
    """
    ```mermaid
    flowchart LR
        A[Inputs] --> B[Behavior Engine]
        B --> C[Prediction]
        C --> D[Action System]
        D --> E[Dashboard]
    ```
    """
)

st.caption(
    "Synapse is a decision-support prototype for hackathon use. It demonstrates how behavior-aware "
    "prediction can help an operations lead respond before a healthcare system overloads."
)
