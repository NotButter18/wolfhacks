const defaults = {
  hospital_capacity: 220,
  normal_inflow: 42,
  wait_time_hours: 3,
  crisis_multiplier: 1.8,
  panic_surge: 1.4,
  proximity_bias: 0.75,
  wait_time_neglect: 0.65,
  redirection_compliance: 0.35,
  pop_up_clinic_capacity: 30,
  resource_boost: 24,
};

const inputIds = Object.keys(defaults);
const simulateBtn = document.getElementById("simulateBtn");
const timelineBody = document.getElementById("timelineBody");
const actionsList = document.getElementById("actionsList");
const currentStatus = document.getElementById("currentStatus");
const overloadMessage = document.getElementById("overloadMessage");
const peakDemand = document.getElementById("peakDemand");
const peakRisk = document.getElementById("peakRisk");
const bestAction = document.getElementById("bestAction");
const behaviorPressure = document.getElementById("behaviorPressure");
const waitStress = document.getElementById("waitStress");
const currentRisk = document.getElementById("currentRisk");

const trendCtx = document.getElementById("trendChart").getContext("2d");
const riskCtx = document.getElementById("riskChart").getContext("2d");

let trendChart;
let riskChart;

function readPayload() {
  return inputIds.reduce((payload, key) => {
    const value = document.getElementById(key).value;
    payload[key] = Number(value);
    return payload;
  }, {});
}

function statusColor(status) {
  if (status === "Critical") return "#d7263d";
  if (status === "Elevated") return "#f4a261";
  return "#2a9d8f";
}

function actionColor(strength) {
  if (strength === "High") return "#d7263d";
  if (strength === "Moderate") return "#f4a261";
  return "#2a9d8f";
}

function renderCharts(timeline) {
  const labels = timeline.map((row) => `Hour ${row.hour}`);
  const demand = timeline.map((row) => row.predicted_demand);
  const capacity = timeline.map((row) => row.capacity);
  const risk = timeline.map((row) => row.risk);

  if (trendChart) trendChart.destroy();
  trendChart = new Chart(trendCtx, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Predicted Demand",
          data: demand,
          borderColor: "#176b87",
          backgroundColor: "rgba(23, 107, 135, 0.15)",
          fill: true,
          tension: 0.35,
        },
        {
          label: "Capacity",
          data: capacity,
          borderColor: "#d7263d",
          backgroundColor: "rgba(215, 38, 61, 0.08)",
          fill: false,
          tension: 0.35,
        },
      ],
    },
    options: {
      responsive: true,
      plugins: {
        legend: { position: "top" },
      },
      scales: {
        y: { beginAtZero: true },
      },
    },
  });

  if (riskChart) riskChart.destroy();
  riskChart = new Chart(riskCtx, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Risk",
          data: risk,
          borderColor: "#176b87",
          backgroundColor: "rgba(23, 107, 135, 0.18)",
          fill: true,
          tension: 0.35,
        },
      ],
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false },
      },
      scales: {
        y: { min: 0, max: 1 },
      },
    },
  });
}

function renderActions(actions) {
  actionsList.innerHTML = actions
    .map(
      (action) => `
        <div class="action-item">
          <div class="action-top">
            <div class="action-name">${action.name}</div>
            <div class="action-pill" style="background:${actionColor(action.strength)}">${action.strength}</div>
          </div>
          <div class="action-why">${action.why}</div>
          <div><strong>Score:</strong> ${action.score.toFixed(2)}</div>
        </div>
      `,
    )
    .join("");
}

function renderTimeline(timeline) {
  timelineBody.innerHTML = timeline
    .map(
      (row) => `
        <tr>
          <td>${row.hour}</td>
          <td>${row.predicted_demand.toFixed(1)}</td>
          <td>${row.capacity.toFixed(1)}</td>
          <td>${row.load_ratio.toFixed(2)}</td>
          <td>${Math.round(row.risk * 100)}%</td>
          <td>${row.status}</td>
        </tr>
      `,
    )
    .join("");
}

function renderInsight(result) {
  const insight = result.insight;
  currentStatus.textContent = insight.current_status;
  currentStatus.style.background = statusColor(insight.current_status);
  overloadMessage.textContent = insight.overload_message;
  peakDemand.textContent = insight.peak_demand.toFixed(0);
  peakRisk.textContent = `${Math.round(insight.peak_risk * 100)}%`;
  bestAction.textContent = insight.best_action;
  behaviorPressure.textContent = `${insight.behavior_multiplier.toFixed(2)}x`;
  waitStress.textContent = `${insight.wait_stress.toFixed(2)}x`;
  currentRisk.textContent = `${Math.round(insight.current_risk * 100)}%`;
  renderCharts(result.timeline);
  renderActions(result.actions);
  renderTimeline(result.timeline);
}

async function simulate() {
  const payload = readPayload();
  const response = await fetch("/simulate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const result = await response.json();
  renderInsight(result);
}

simulateBtn.addEventListener("click", simulate);

renderInsight({
  timeline: [
    { hour: 0, predicted_demand: 55, capacity: 220, load_ratio: 0.25, risk: 0, status: "Stable" },
    { hour: 1, predicted_demand: 60, capacity: 223, load_ratio: 0.27, risk: 0, status: "Stable" },
    { hour: 2, predicted_demand: 63, capacity: 225, load_ratio: 0.28, risk: 0, status: "Stable" },
  ],
  actions: [
    { name: "Public health alert", why: "Reduce panic visits.", score: 0.44, strength: "Moderate" },
    { name: "Pop-up clinic", why: "Absorb non-emergency demand.", score: 0.38, strength: "Moderate" },
    { name: "Resource redistribution", why: "Add internal capacity.", score: 0.22, strength: "Low" },
  ],
  insight: {
    current_status: "Stable",
    overload_message: "Run the simulation to see the forecast.",
    peak_demand: 0,
    peak_risk: 0,
    best_action: "-",
    behavior_multiplier: 1,
    wait_stress: 1,
    current_risk: 0,
  },
});

