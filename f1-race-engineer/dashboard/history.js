function fmtLap(ms) {
  if (!ms) return "--:--.---";
  const m = Math.floor(ms / 60000);
  const s = Math.floor((ms % 60000) / 1000);
  const mm = ms % 1000;
  return m + ":" + String(s).padStart(2, "0") + "." + String(mm).padStart(3, "0");
}

async function loadSessions() {
  const container = document.getElementById("sessions");
  let sessions;
  try {
    const res = await fetch("/api/sessions");
    sessions = await res.json();
  } catch (e) {
    container.innerHTML = "";
    const errEl = document.createElement("div");
    errEl.className = "empty-state";
    errEl.textContent = "Could not load session history.";
    container.appendChild(errEl);
    return;
  }

  container.innerHTML = "";
  if (!sessions.length) {
    const emptyEl = document.createElement("div");
    emptyEl.className = "empty-state";
    emptyEl.textContent = "No completed sessions yet.";
    container.appendChild(emptyEl);
    return;
  }

  for (const session of sessions.slice().reverse()) {
    const card = document.createElement("div");
    card.className = "session-card";

    const dateEl = document.createElement("div");
    dateEl.className = "session-date";
    dateEl.textContent = session.ended_at;
    card.appendChild(dateEl);

    const stats = [
      ["LAPS", session.summary.lap_count ?? "--"],
      ["BEST", fmtLap(session.summary.best_lap_ms)],
      ["AVG", fmtLap(Math.round(session.summary.avg_lap_ms || 0))],
    ];
    for (const [label, val] of stats) {
      const statEl = document.createElement("div");
      statEl.className = "session-stat";
      const valEl = document.createElement("div");
      valEl.className = "val";
      valEl.textContent = val;
      const labelEl = document.createElement("div");
      labelEl.className = "label";
      labelEl.textContent = label;
      statEl.appendChild(valEl);
      statEl.appendChild(labelEl);
      card.appendChild(statEl);
    }
    container.appendChild(card);
  }
}

loadSessions();
