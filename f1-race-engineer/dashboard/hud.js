function fmtGap(ms) {
  if (ms == null) return "--.---";
  return "+" + (ms / 1000).toFixed(3);
}

async function poll() {
  let data;
  try {
    const res = await fetch("/api/state", { cache: "no-store" });
    if (!res.ok) return;
    data = await res.json();
  } catch (e) {
    return;
  }

  const deltaEl = document.getElementById("hudDelta");
  if (data.last_lap_time_ms && data.best_lap_time_ms) {
    const d = data.last_lap_time_ms - data.best_lap_time_ms;
    deltaEl.textContent = (d <= 0 ? "-" : "+") + (Math.abs(d) / 1000).toFixed(3);
    deltaEl.style.color = d <= 0 ? "#b249f8" : "#e5484d";
  } else {
    deltaEl.textContent = "--.---";
    deltaEl.style.color = "";
  }

  document.getElementById("hudPos").textContent = "P" + (data.car_position ?? "--");
  document.getElementById("hudGapAhead").textContent = fmtGap(data.gap_ahead_ms);
  document.getElementById("hudGapBehind").textContent = fmtGap(data.gap_behind_ms);

  const fuelEl = document.getElementById("hudFuel");
  fuelEl.textContent = data.fuel_remaining_laps == null ? "--kg" : data.fuel_remaining_laps.toFixed(1) + " laps";

  const wear = data.tyres_wear || [0, 0, 0, 0];
  document.getElementById("hudTyres").textContent = wear.map((w) => Math.max(0, Math.round(100 - w)) + "%").join("/");
}

poll();
setInterval(poll, 500);
