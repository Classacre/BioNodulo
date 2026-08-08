// Loading screen shown while the backend boots. Navigates away automatically
// once the backend is healthy (Rust calls window.location.replace from Tauri).
//
// Three sources of information:
//   startup:progress — emitted by supervisor.rs at each startup phase
//   setup:progress   — emitted by provision.rs when a venv rebuild is needed
//   python:log       — stdout/stderr from the Python backend process
const { listen } = window.__TAURI__.event;

// ---- step state machine ----
// Each step is: pending → active → done | error
// Steps are keyed by the "step" field in startup:progress events.
const STEP_ORDER = ["check_env", "start_process", "health_wait"];

function stepEl(key) { return document.getElementById("s-" + key); }
function detailEl(key) { return document.getElementById("d-" + key); }

function setStepState(key, state) {
  const el = stepEl(key);
  if (!el) return;
  el.classList.remove("pending", "active", "done", "error");
  el.classList.add(state);
  const icon = el.querySelector(".step-icon");
  if (state === "done")  icon.textContent = "✓";
  else if (state === "error") icon.textContent = "✕";
  else icon.textContent = "";
}

function setStepDetail(key, text) {
  const d = detailEl(key);
  if (d) d.textContent = text || "";
}

// On first progress event for a step, activate all earlier steps as done
// (catches cases where we missed an earlier event or startup skipped them).
const seenActive = new Set();
function activateStep(key) {
  if (seenActive.has(key)) return;
  seenActive.add(key);
  const idx = STEP_ORDER.indexOf(key);
  for (let i = 0; i < idx; i++) {
    const k = STEP_ORDER[i];
    if (!seenActive.has(k)) {
      seenActive.add(k);
      setStepState(k, "done");
    }
  }
  setStepState(key, "active");
}

// ---- event handlers ----
listen("startup:progress", (e) => {
  const { step, label, done, error } = e.payload || {};
  if (!step) return;
  if (error) {
    setStepState(step, "error");
    setStepDetail(step, label || "");
  } else if (done) {
    setStepState(step, "done");
    setStepDetail(step, "");
  } else {
    activateStep(step);
    setStepDetail(step, label || "");
  }
});

// provision.rs emits setup:progress when a venv rebuild is triggered at
// startup (e.g. after an upgrade moved the bundled interpreter). Show it
// under the check_env step so the user knows why startup is taking longer.
listen("setup:progress", (e) => {
  const { phase, message } = e.payload || {};
  if (!phase || !message) return;
  activateStep("check_env");
  setStepDetail("check_env", message);
  appendLog("[setup] " + message);
});

// Backend stdout/stderr — stream into the collapsible log area.
listen("python:log", (e) => {
  appendLog(e.payload);
});

// python:status-change is coarse ("starting" / "running") but still useful
// as a fallback if startup:progress events didn't arrive.
listen("python:status-change", (e) => {
  const status = e.payload;
  if (status === "starting") {
    // Activate the furthest unfinished step
    for (const k of STEP_ORDER) {
      if (!seenActive.has(k)) { activateStep(k); break; }
    }
  }
});

// ---- log area ----
const logEl = document.getElementById("log");
function appendLog(text) {
  if (!text) return;
  logEl.appendChild(document.createTextNode(text + "\n"));
  logEl.scrollTop = logEl.scrollHeight;
}

function toggleLog(btn) {
  const body = document.getElementById("log-body");
  const arrow = document.getElementById("log-arrow");
  const open = body.classList.toggle("open");
  if (arrow) arrow.textContent = open ? "▾" : "▸";
}
