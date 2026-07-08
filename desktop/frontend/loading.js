// Loading screen shown while the backend boots; navigates away automatically
// (from Rust) once the backend is healthy.
const { listen } = window.__TAURI__.event;

const statusEl = document.getElementById("status");
const logEl = document.getElementById("log");

listen("python:status-change", (e) => {
  statusEl.textContent = "Backend status: " + e.payload;
});
listen("python:log", (e) => {
  logEl.appendChild(document.createTextNode(e.payload + "\n"));
  logEl.scrollTop = logEl.scrollHeight;
});
