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

// Tauri rejects invoke() with the command's error value (a string here), not an
// Error object — normalize so the UI always shows something readable.
function errText(err) {
  if (err && typeof err.message === "string") return err.message;
  if (typeof err === "string") return err;
  try { return JSON.stringify(err); } catch { return "An error occurred."; }
}

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

api.onSetupProgress((p) => {
  if (!p) return;
  $("phase").textContent = p.message || "";
  if (typeof p.fraction === "number") {
    $("bar").style.width = Math.round(p.fraction * 100) + "%";
  }
  const logEl = $("log");
  logEl.appendChild(document.createTextNode((p.message || "") + "\n"));
  logEl.scrollTop = logEl.scrollHeight;
});

function finish(title, message, { error = false, retry = false } = {}) {
  $("doneTitle").textContent = title;
  $("doneTitle").classList.toggle("error", error);
  $("doneMsg").textContent = message;
  $("retry").style.display = retry ? "" : "none";
  $("launch").style.display = retry ? "none" : "";
  show("done");
}

// On Windows the tools cannot run natively, so local execution means a private
// WSL2 distribution. The installer already enabled WSL while it was elevated,
// so this needs no administrator rights and is done without asking: local is
// the default, and the cloud is offered as a suggestion rather than a gate.
//
// Returns true when the wizard has taken over the screen to report a problem.
async function setUpLocalExecution() {
  let status;
  try {
    status = await api.getLocalExecutionStatus();
  } catch {
    return false; // Not a Windows build, or the command is unavailable.
  }
  if (!status || !status.requiresWsl || status.state === "ready") return false;

  if (!status.userFixable) {
    // WSL itself is missing: either the installer could not enable it, or
    // Windows has not been restarted yet. Neither is fixable from here.
    $("localDetail").textContent = status.message || "";
    show("local");
    return true;
  }

  try {
    await api.setupLocalExecution();
    return false;
  } catch (err) {
    $("localDetail").textContent = errText(err);
    show("local");
    return true;
  }
}

async function runSetup() {
  show("install");
  $("bar").style.width = "5%";
  try {
    await api.runSetup();
    $("bar").style.width = "100%";
    $("phase").textContent = "Setting up local execution...";
    if (await setUpLocalExecution()) return;
    finish("Setup complete", "BioNodulo is ready to launch.");
  } catch (err) {
    finish("Setup failed", errText(err), { error: true, retry: true });
  }
}

$("skipLocal").addEventListener("click", () => {
  finish("Setup complete", "BioNodulo is ready to launch. Workflows will run on the cloud.");
});

$("retryLocal").addEventListener("click", async () => {
  $("retryLocal").disabled = true;
  show("install");
  $("phase").textContent = "Setting up local execution...";
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
