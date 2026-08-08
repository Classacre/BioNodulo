// First-run wizard. Uses the global Tauri API (withGlobalTauri) so this page
// needs no bundler. All privileged work goes through guarded Rust commands.
const { invoke } = window.__TAURI__.core;
const { listen } = window.__TAURI__.event;

const api = {
  getPaths: () => invoke("get_paths"),
  selectDirectory: () => invoke("select_directory"),
  setSetting: (key, value) => invoke("set_setting", { key, value }),
  runSetup: () => invoke("run_setup"),
  completeSetup: () => invoke("complete_setup"),
  onSetupProgress: (cb) => listen("setup:progress", (e) => cb(e.payload)),
  getLocalExecutionStatus: () => invoke("get_local_execution_status"),
  setupLocalExecution: () => invoke("setup_local_execution"),
};

const $ = (id) => document.getElementById(id);
const steps = {
  welcome: $("step-welcome"),
  install: $("step-install"),
  local: $("step-local"),
  done: $("step-done"),
};
function show(name) {
  for (const k of Object.keys(steps)) steps[k].classList.toggle("active", k === name);
}

function errText(err) {
  if (err && typeof err.message === "string") return err.message;
  if (typeof err === "string") return err;
  try { return JSON.stringify(err); } catch { return "An error occurred."; }
}

// ---- elapsed timer ----
// Shown next to the phase message for operations that may feel stuck.
// Reassures the user that something is happening even when the log is quiet.
let elapsedTimer = null;
let elapsedStart = 0;

function startElapsed() {
  stopElapsed();
  elapsedStart = Date.now();
  elapsedTimer = setInterval(updateElapsed, 1000);
  updateElapsed();
}

function stopElapsed() {
  if (elapsedTimer !== null) { clearInterval(elapsedTimer); elapsedTimer = null; }
  const el = $("elapsed");
  if (el) el.textContent = "";
}

function updateElapsed() {
  const el = $("elapsed");
  if (!el) return;
  const secs = Math.floor((Date.now() - elapsedStart) / 1000);
  el.textContent = secs < 5 ? "" : `${secs}s`;
}

// ---- hint messages ----
// For known-slow phases, rotate through hints so the screen never looks frozen.
const PHASE_HINTS = {
  "Downloading Linux userland":
    "Downloading a small Linux system for running bioinformatics tools (~200 MB). " +
    "This happens once.",
  "Importing the Linux environment":
    "Registering the Linux environment with Windows. Usually under a minute.",
  "Preparing the environment":
    "Configuring the Linux environment. Should finish shortly.",
  "Installing Python":
    "Setting up Python inside the Linux environment. This usually takes 1–3 minutes.",
  "Installing the workflow engine":
    "Installing BioNodulo's backend into the Linux environment. Usually under a minute.",
  "Installing dependencies":
    "Downloading and installing workflow dependencies with uv. " +
    "This is a one-time install — future launches start immediately.",
  "Locking dependencies":
    "Resolving the exact set of compatible packages. Usually under a minute.",
  "Creating Python environment":
    "Setting up an isolated Python environment. Under a minute.",
  "Rebuilding the Python environment":
    "The Python environment needs to be rebuilt after an upgrade. Under a minute.",
};

let currentHintKey = null;
let hintTimeout = null;

function showHint(message) {
  // Find the most specific hint key that matches the current message
  const key = Object.keys(PHASE_HINTS).find((k) => message.includes(k));
  if (!key || key === currentHintKey) return;
  currentHintKey = key;
  clearTimeout(hintTimeout);
  // Show the hint after 4 seconds — short operations don't need it
  hintTimeout = setTimeout(() => {
    const el = $("hint");
    if (el) el.textContent = PHASE_HINTS[key] || "";
  }, 4000);
}

function clearHint() {
  currentHintKey = null;
  clearTimeout(hintTimeout);
  const el = $("hint");
  if (el) el.textContent = "";
}

// ---- progress events ----
api.onSetupProgress((p) => {
  if (!p) return;
  const msg = p.message || "";

  $("phase").textContent = msg;

  if (typeof p.fraction === "number") {
    $("bar").style.width = Math.round(p.fraction * 100) + "%";
  }

  // Start the elapsed timer when we hit a phase known to be slow
  const slowPhases = [
    "Downloading", "Installing", "Locking", "Resolving",
    "Rebuilding", "Preparing", "Importing",
  ];
  if (slowPhases.some((s) => msg.includes(s))) {
    if (elapsedTimer === null) startElapsed();
  } else {
    stopElapsed();
  }

  showHint(msg);

  const logEl = $("log");
  logEl.appendChild(document.createTextNode(msg + "\n"));
  logEl.scrollTop = logEl.scrollHeight;
});

// ---- wizard flow ----
(async () => {
  try {
    const paths = await api.getPaths();
    $("dataDir").value = paths.userData || "";
  } catch (e) { /* ignore */ }
})();

$("browse").addEventListener("click", async () => {
  const dir = await api.selectDirectory();
  if (dir) {
    $("dataDir").value = dir;
    await api.setSetting("dataDirectory", dir);
  }
});

function finish(title, message, { error = false, retry = false } = {}) {
  stopElapsed();
  clearHint();
  $("doneTitle").textContent = title;
  $("doneTitle").classList.toggle("error", error);
  $("doneMsg").textContent = message;
  $("retry").style.display = retry ? "" : "none";
  $("launch").style.display = retry ? "none" : "";
  show("done");
}

async function setUpLocalExecution() {
  let status;
  try {
    status = await api.getLocalExecutionStatus();
  } catch {
    return false; // Not a Windows build, or the command is unavailable.
  }
  if (!status || !status.requiresWsl || status.state === "ready") return false;

  if (!status.userFixable) {
    $("localDetail").textContent = status.message || "";
    show("local");
    return true;
  }

  try {
    $("phase").textContent = "Setting up local execution…";
    startElapsed();
    await api.setupLocalExecution();
    stopElapsed();
    return false;
  } catch (err) {
    stopElapsed();
    $("localDetail").textContent = errText(err);
    show("local");
    return true;
  }
}

async function runSetup() {
  show("install");
  clearHint();
  $("bar").style.width = "5%";
  $("phase").textContent = "Preparing…";
  startElapsed();
  try {
    await api.runSetup();
    $("bar").style.width = "100%";
    stopElapsed();
    clearHint();
    if (await setUpLocalExecution()) return;
    finish("Setup complete", "BioNodulo is ready to launch.");
  } catch (err) {
    stopElapsed();
    finish("Setup failed", errText(err), { error: true, retry: true });
  }
}

$("skipLocal").addEventListener("click", () => {
  finish("Setup complete", "BioNodulo is ready to launch. Workflows will run on the cloud.");
});

$("retryLocal").addEventListener("click", async () => {
  $("retryLocal").disabled = true;
  show("install");
  clearHint();
  $("phase").textContent = "Setting up local execution…";
  startElapsed();
  if (!(await setUpLocalExecution())) {
    finish("Setup complete", "Local execution is ready. Workflows will run on this PC.");
  }
  $("retryLocal").disabled = false;
});

$("start").addEventListener("click", runSetup);
$("retry").addEventListener("click", runSetup);
$("launch").addEventListener("click", async () => {
  $("launch").disabled = true;
  await api.completeSetup();
});
