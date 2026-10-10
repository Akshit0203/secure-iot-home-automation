"use strict";

const tokenKey = "homeauto-token";
const $ = (id) => document.getElementById(id);

function token() {
  try { return sessionStorage.getItem(tokenKey) || ""; } catch { return ""; }
}

async function api(path, body) {
  const res = await fetch(path, {
    method: body ? "POST" : "GET",
    headers: { "Authorization": `Bearer ${token()}`, "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(res.status === 401 ? "Unauthorized - check token" : `HTTP ${res.status}`);
  return res.json();
}

async function refresh() {
  if (!token()) { $("status").textContent = "Enter the API token to connect."; return; }
  try {
    const s = await api("/api/status");
    $("led").textContent = s.led ? "ON" : "OFF";
    $("mode").textContent = s.mode.toUpperCase();
    $("motion").textContent = s.motion ? "Detected" : "None";
    $("climate").textContent = s.temperature_c === null
      ? "n/a" : `${s.temperature_c} °C · ${s.humidity_pct} %`;
    $("status").textContent = s.simulated ? "Connected (simulated GPIO)" : "Connected";
  } catch (e) {
    $("status").textContent = e.message;
  }
}

$("save-token").addEventListener("click", () => {
  try { sessionStorage.setItem(tokenKey, $("token").value.trim()); } catch { /* storage blocked */ }
  $("token").value = "";
  refresh();
});

document.querySelectorAll("[data-led]").forEach((b) =>
  b.addEventListener("click", () => api("/api/led", { state: b.dataset.led }).then(refresh).catch((e) => ($("status").textContent = e.message))));

document.querySelectorAll("[data-mode]").forEach((b) =>
  b.addEventListener("click", () => api("/api/mode", { mode: b.dataset.mode }).then(refresh).catch((e) => ($("status").textContent = e.message))));

refresh();
setInterval(refresh, 2000);
