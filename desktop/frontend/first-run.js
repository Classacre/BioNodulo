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

// Windows cannot run these tools natively: they are published for Linux and
// macOS only. Offer the choice rather than silently leaving the app unable to
// run anything locally -- but only on Windows, and only when WSL is a route
// the user can actually take.
async function offerLocalExecution() {
  let status;
  try {
    status = await api.getLocalExecutionStatus();
  } catch {
    return false;
  }
  if (!status || !status.requiresWsl || status.state === "ready") return false;

  if (!status.userFixable) {
    // Enabling WSL needs administrator rights, which we cannot grant. Show the
    // exact command and let the user continue on the cloud meanwhile.
    $("localBlocked").textContent = status.message || "";
    $("localBlocked").style.display = "";
    $("setupLocal").disabled = true;
  }
  show("local");
  return true;
}

async function runSetup() {
  show("install");
  $("bar").style.width = "5%";
  try {
    await api.runSetup();
    $("bar").style.width = "100%";
    if (await offerLocalExecution()) return;
    finish("Setup complete", "BioNodulo is ready to launch.");
  } catch (err) {
    finish("Setup failed", errText(err), { error: true, retry: true });
  }
}

$("skipLocal").addEventListener("click", () => {
  finish("Setup complete", "BioNodulo is ready to launch. Workflows will run on the cloud.");
});

$("setupLocal").addEventListener("click", async () => {
  $("setupLocal").disabled = true;
  $("skipLocal").disabled = true;
  show("install");
  $("bar").style.width = "5%";
  try {
    await api.setupLocalExecution();
    $("bar").style.width = "100%";
    finish("Setup complete", "Local execution is ready. Workflows will run on this PC.");
  } catch (err) {
    // Local execution is optional, so a failure here is not a failed setup:
    // the app still works on the cloud.
    finish(
      "Setup complete, without local execution",
      errText(err) + " You can run workflows on the cloud, and retry local setup in Settings.",
    );
  }
});

$("start").addEventListener("click", runSetup);
$("retry").addEventListener("click", runSetup);
$("launch").addEventListener("click", async () => {
  $("launch").disabled = true;
  await api.completeSetup();
});
