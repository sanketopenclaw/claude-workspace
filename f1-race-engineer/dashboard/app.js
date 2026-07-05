function fmtLap(ms) {
  if (!ms) return "--:--.---";
  const m = Math.floor(ms / 60000);
  const s = Math.floor((ms % 60000) / 1000);
  const mm = ms % 1000;
  return m + ":" + String(s).padStart(2, "0") + "." + String(mm).padStart(3, "0");
}

function fmtGap(ms) {
  if (ms == null) return "--.---";
  return "+" + (ms / 1000).toFixed(3);
}

function tyreColorClass(wear) {
  const life = Math.max(0, Math.round(100 - wear));
  if (life <= 20) return "red";
  if (life <= 50) return "yellow";
  return "green";
}

function renderLog(entries) {
  const logEl = document.getElementById("log");
  logEl.innerHTML = "";
  for (const e of entries) {
    const div = document.createElement("div");
    div.className = "log-entry " + (e.type === "qa" ? "log-qa" : "log-callout");
    const text = e.type === "qa" && e.q ? '"' + e.q + '" — ' + e.text : e.text;
    const meta = document.createElement("div");
    meta.className = "log-meta";
    const timeSpan = document.createElement("span");
    timeSpan.className = "log-time";
    timeSpan.textContent = e.time;
    const tagSpan = document.createElement("span");
    tagSpan.className = "log-tag";
    tagSpan.textContent = e.type === "qa" ? "Q&A" : "CALLOUT";
    meta.appendChild(timeSpan);
    meta.appendChild(tagSpan);
    const textEl = document.createElement("div");
    textEl.className = "log-text";
    textEl.textContent = text;
    div.appendChild(meta);
    div.appendChild(textEl);
    logEl.appendChild(div);
  }
  logEl.scrollTop = logEl.scrollHeight;
}

function renderLeaderboard(entries, playerPosition) {
  const boardEl = document.getElementById("leaderboard");
  boardEl.innerHTML = "";
  for (const entry of entries) {
    const row = document.createElement("div");
    row.className = "board-row" + (entry.car_position === playerPosition ? " board-row-player" : "");
    const posEl = document.createElement("span");
    posEl.className = "board-pos";
    posEl.textContent = "P" + entry.car_position;
    const nameEl = document.createElement("span");
    nameEl.className = "board-name";
    nameEl.textContent = entry.name;
    const gapEl = document.createElement("span");
    gapEl.className = "board-gap";
    gapEl.textContent = entry.gap_to_leader_ms === 0 ? "LEADER" : fmtGap(entry.gap_to_leader_ms);
    row.appendChild(posEl);
    row.appendChild(nameEl);
    row.appendChild(gapEl);
    boardEl.appendChild(row);
  }
}

async function poll() {
  let data;
  try {
    const res = await fetch("/api/state", { cache: "no-store" });
    if (!res.ok) return;
    data = await res.json();
  } catch (e) {
    return; // keep showing last known values on a fetch failure
  }

  document.getElementById("lapNum").textContent = data.current_lap_num ?? 0;
  document.getElementById("curLap").textContent = fmtLap(data.current_lap_time_ms);

  const deltaEl = document.getElementById("deltaText");
  if (data.last_lap_time_ms && data.best_lap_time_ms) {
    const d = data.last_lap_time_ms - data.best_lap_time_ms;
    if (d <= 0) {
      deltaEl.textContent = d === 0 ? "PURPLE" : "-" + (Math.abs(d) / 1000).toFixed(3);
      deltaEl.style.color = "#b249f8";
    } else {
      deltaEl.textContent = "+" + (d / 1000).toFixed(3);
      deltaEl.style.color = "#e5484d";
    }
  } else {
    deltaEl.textContent = "--.---";
    deltaEl.style.color = "";
  }

  document.getElementById("position").textContent = data.car_position ?? "--";
  document.getElementById("gapAhead").textContent = fmtGap(data.gap_ahead_ms);
  document.getElementById("gapBehind").textContent = fmtGap(data.gap_behind_ms);

  const wear = data.tyres_wear || [0, 0, 0, 0];
  const wheelIds = ["tyreFL", "tyreFR", "tyreRL", "tyreRR"];
  wheelIds.forEach((id, i) => {
    const el = document.getElementById(id);
    const life = Math.max(0, Math.round(100 - wear[i]));
    el.textContent = life + "%";
    el.className = "tyre-pct " + tyreColorClass(wear[i]);
  });

  const fuelEl = document.getElementById("fuel");
  if (data.fuel_in_tank == null || data.fuel_remaining_laps == null) {
    fuelEl.textContent = "--kg · -- laps";
  } else {
    fuelEl.textContent = data.fuel_in_tank.toFixed(1) + "kg · " + data.fuel_remaining_laps.toFixed(1) + " laps";
  }

  const pitTextEl = document.getElementById("pitStatusText");
  const hasPitData = data.pit_window_ideal_lap != null || data.pit_rejoin_position != null;
  if (!hasPitData) {
    pitTextEl.textContent = "Awaiting data";
  } else {
    const parts = [];
    if (data.pit_window_ideal_lap != null) parts.push("Lap " + data.pit_window_ideal_lap + "-" + data.pit_window_latest_lap);
    if (data.pit_rejoin_position != null) parts.push("Rejoin P" + data.pit_rejoin_position);
    pitTextEl.textContent = parts.join(" · ");
  }
  document.getElementById("pitCard").classList.toggle("placeholder", !hasPitData);

  const weatherTextEl = document.getElementById("weatherStatusText");
  if (data.weather == null) {
    weatherTextEl.textContent = "Awaiting data";
  } else {
    weatherTextEl.textContent = data.weather.name + " · " + data.weather.track_temp + "°C track";
  }
  document.getElementById("weatherCard").classList.toggle("placeholder", data.weather == null);

  const hasSetup = data.car_setup != null;
  document.getElementById("setupPanel").classList.toggle("placeholder", !hasSetup);
  document.getElementById("setupPlaceholderBody").style.display = hasSetup ? "none" : "flex";
  document.getElementById("setupGrid").style.display = hasSetup ? "grid" : "none";
  document.getElementById("setupDot").className = "dot " + (hasSetup ? "dot-green" : "dot-dim");
  document.getElementById("setupLabel").className = "label" + (hasSetup ? "" : " label-dim");
  if (hasSetup) {
    const s = data.car_setup;
    document.getElementById("setupFrontWing").textContent = s.front_wing;
    document.getElementById("setupRearWing").textContent = s.rear_wing;
    document.getElementById("setupBrakeBias").textContent = s.brake_bias + "%";
    document.getElementById("setupTyrePressures").textContent =
      s.front_left_tyre_pressure.toFixed(1) + " / " + s.rear_left_tyre_pressure.toFixed(1);
  }

  renderLeaderboard(data.leaderboard || [], data.car_position);
  renderLog(data.log || []);
}

poll();
setInterval(poll, 500);
