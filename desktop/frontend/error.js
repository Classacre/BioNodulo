// Error screen. `?message=` is set by Rust when the backend fails to start.
const { invoke } = window.__TAURI__.core;

const msg = new URLSearchParams(location.search).get("message");
if (msg) document.getElementById("message").textContent = msg;

document.getElementById("logs").addEventListener("click", () => invoke("show_logs"));
document.getElementById("restart").addEventListener("click", async () => {
  try {
    await invoke("restart_python");
    location.reload();
  } catch (e) {
    /* stay on the error page */
  }
});
