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
    meta.innerHTML =
      '<span class="log-time">' + e.time + '</span>' +
      '<span class="log-tag">' + (e.type === "qa" ? "Q&A" : "CALLOUT") + '</span>';
    const textEl = document.createElement("div");
    textEl.className = "log-text";
    textEl.textContent = text;
    div.appendChild(meta);
    div.appendChild(textEl);
    logEl.appendChild(div);
  }
  logEl.scrollTop = logEl.scrollHeight;
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

  document.getElementById("pitCard").classList.toggle("placeholder", data.pit_rejoin_position == null);
  document.getElementById("weatherCard").classList.toggle("placeholder", data.weather == null);

  renderLog(data.log || []);
}

poll();
setInterval(poll, 500);
