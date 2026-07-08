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
};

const $ = (id) => document.getElementById(id);
const steps = { welcome: $("step-welcome"), install: $("step-install"), done: $("step-done") };
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

async function runSetup() {
  show("install");
  $("bar").style.width = "5%";
  try {
    await api.runSetup();
    $("bar").style.width = "100%";
    $("doneTitle").textContent = "Setup complete";
    $("doneTitle").classList.remove("error");
    $("doneMsg").textContent = "BioNodulo is ready to launch.";
    $("retry").style.display = "none";
    $("launch").style.display = "";
    show("done");
  } catch (err) {
    $("doneTitle").textContent = "Setup failed";
    $("doneTitle").classList.add("error");
    $("doneMsg").textContent = errText(err);
    $("retry").style.display = "";
    $("launch").style.display = "none";
    show("done");
  }
}

$("start").addEventListener("click", runSetup);
$("retry").addEventListener("click", runSetup);
$("launch").addEventListener("click", async () => {
  $("launch").disabled = true;
  await api.completeSetup();
});
