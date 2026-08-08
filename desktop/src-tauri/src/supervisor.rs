use std::collections::VecDeque;
use std::process::Stdio;
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

use tauri::{AppHandle, Emitter};
use tokio::io::{AsyncBufReadExt, BufReader};
use tokio::process::{Child, Command};

use crate::{paths, port};

const MAX_LOG_LINES: usize = 2000;
const FORCE_KILL_GRACE: Duration = Duration::from_secs(10);
const HEALTH_TIMEOUT: Duration = Duration::from_secs(60);
const HEALTH_REQ_TIMEOUT: Duration = Duration::from_secs(2);

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum PythonStatus {
    Starting,
    Running,
    Stopping,
    Stopped,
    Error,
}

impl PythonStatus {
    pub fn as_str(self) -> &'static str {
        match self {
            PythonStatus::Starting => "starting",
            PythonStatus::Running => "running",
            PythonStatus::Stopping => "stopping",
            PythonStatus::Stopped => "stopped",
            PythonStatus::Error => "error",
        }
    }
}

struct Inner {
    status: PythonStatus,
    logs: VecDeque<String>,
    server_url: String,
    port: u16,
    child_pid: Option<u32>,
}

pub struct Supervisor {
    inner: Arc<Mutex<Inner>>,
    child: Arc<tokio::sync::Mutex<Option<Child>>>,
}

impl Default for Supervisor {
    fn default() -> Self {
        Supervisor {
            inner: Arc::new(Mutex::new(Inner {
                status: PythonStatus::Stopped,
                logs: VecDeque::with_capacity(MAX_LOG_LINES),
                server_url: String::new(),
                port: 0,
                child_pid: None,
            })),
            child: Arc::new(tokio::sync::Mutex::new(None)),
        }
    }
}

impl Supervisor {
    pub fn status(&self) -> PythonStatus {
        self.inner.lock().unwrap().status
    }

    pub fn server_url(&self) -> String {
        self.inner.lock().unwrap().server_url.clone()
    }

    pub fn logs(&self) -> Vec<String> {
        let inner = self.inner.lock().unwrap();
        let n = inner.logs.len().min(500);
        inner
            .logs
            .iter()
            .skip(inner.logs.len() - n)
            .cloned()
            .collect()
    }

    fn set_status(&self, app: &AppHandle, status: PythonStatus) {
        {
            let mut inner = self.inner.lock().unwrap();
            if inner.status == status {
                return;
            }
            inner.status = status;
        }
        let _ = app.emit("python:status-change", status.as_str());
    }

    pub async fn start(&self, app: &AppHandle) -> Result<(), String> {
        match self.status() {
            PythonStatus::Running | PythonStatus::Starting => return Ok(()),
            _ => {}
        }
        self.set_status(app, PythonStatus::Starting);

        let venv = paths::venv_path(app);
        let python = paths::venv_python(&venv);
        let backend = paths::backend_path(app);
        let main_script = paths::backend_entry_script(app);
        let workspace = paths::workspace_path(app);
        let logs = paths::logs_path(app);

        if !python.exists() {
            self.set_status(app, PythonStatus::Error);
            return Err(format!(
                "Python interpreter not found at \"{}\". Run first-run setup.",
                python.display()
            ));
        }
        // Existing is not the same as working. After an upgrade the venv can
        // still point at an interpreter the previous installation owned, and
        // launching it exits 103 with "No Python at ..." -- an error about a
        // path the user never chose. Rebuild instead of spawning it.
        if !paths::venv_is_usable(app, &venv) {
            log::warn!("[supervisor] venv at {} cannot start; rebuilding", venv.display());
            if let Err(err) = crate::provision::setup(app).await {
                self.set_status(app, PythonStatus::Error);
                return Err(format!(
                    "The Python environment could not be rebuilt: {err}"
                ));
            }
        }
        if !main_script.exists() {
            self.set_status(app, PythonStatus::Error);
            return Err(format!(
                "Backend entry script not found at \"{}\".",
                main_script.display()
            ));
        }

        // Local execution on Windows runs the backend inside WSL2, because
        // bioconda publishes no Windows packages. That changes two things: the
        // process is launched through wsl.exe, and the socket has to be
        // reachable across the VM boundary.
        let via_wsl = crate::wsl_mode_enabled(app);
        let base_port = if via_wsl { crate::wsl::MIN_FORWARDED_PORT } else { 8188 };
        let free = port::find_free_port(base_port).map_err(|e| e.to_string())?;
        // Loopback-only would be unreachable from Windows; WSL forwards a
        // listener bound to all interfaces.
        let bind_host = if via_wsl { "0.0.0.0" } else { "127.0.0.1" };
        let url = format!("http://127.0.0.1:{free}");
        {
            let mut inner = self.inner.lock().unwrap();
            inner.port = free;
            inner.server_url = url.clone();
        }

        let _ = std::fs::create_dir_all(&workspace);
        let _ = std::fs::create_dir_all(&logs);

        // Under WSL the workspace lives on ext4 inside the distribution. Runs
        // touch a great many files, and /mnt/c costs roughly 10x each time.
        let project_root: String = if via_wsl {
            crate::wsl_linux_workspace()
        } else {
            workspace.to_string_lossy().into_owned()
        };

        let cors_origins = format!("{},https://cloud.bionodulo.com", url);
        let cf = crate::paths::cloudflared_path(app);

        // Every path handed across the WSL boundary must already be a Linux
        // path, and the environment must travel explicitly: variables set on
        // wsl.exe do not reach the process inside the distribution.
        let to_side = |path: &std::path::Path| -> Result<String, String> {
            if via_wsl {
                crate::wsl::to_wsl_path(path)
            } else {
                Ok(path.to_string_lossy().into_owned())
            }
        };
        let script = to_side(&main_script)?;
        let workdir = to_side(&backend)?;
        let py_path = to_side(&backend)?;
        let venv_dir = if via_wsl {
            crate::wsl::venv_path()
        } else {
            venv.to_string_lossy().into_owned()
        };

        let app_args: Vec<String> = vec![
            "--host".into(),
            bind_host.into(),
            "--port".into(),
            free.to_string(),
            "--project-root".into(),
            project_root.clone(),
        ];
        let mut envs: Vec<(String, String)> = vec![
            ("PYTHONPATH".into(), py_path),
            ("PYTHONUNBUFFERED".into(), "1".into()),
            ("VIRTUAL_ENV".into(), venv_dir),
            ("BIONODULO_HOST".into(), bind_host.into()),
            ("BIONODULO_PORT".into(), free.to_string()),
            ("BIONODULO_CORS_ORIGINS".into(), cors_origins),
            ("BIONODULO_CORS_ALLOW_LOOPBACK".into(), "1".into()),
        ];
        // cloudflared is a Windows executable, so it cannot be launched from
        // inside the distribution. Sharing a workflow falls back to the cloud
        // path there rather than silently pointing at an unrunnable binary.
        if cf.exists() && !via_wsl {
            envs.push((
                "BIONODULO_CLOUDFLARED".into(),
                cf.to_string_lossy().into_owned(),
            ));
        }

        let mut cmd = if via_wsl {
            let mut c = Command::new("wsl.exe");
            c.args(crate::wsl::backend_argv(
                &workdir,
                &crate::wsl::linux_python(),
                &script,
                &app_args,
                &envs,
            ));
            c
        } else {
            let mut c = Command::new(&python);
            c.arg(&script).args(&app_args).current_dir(&backend);
            for (key, value) in &envs {
                c.env(key, value);
            }
            c
        };
        cmd.stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .kill_on_drop(false);
        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            const CREATE_NO_WINDOW: u32 = 0x0800_0000;
            cmd.creation_flags(CREATE_NO_WINDOW);
        }

        let mut child = cmd.spawn().map_err(|e| format!("Failed to spawn backend: {e}"))?;
        let pid = child.id();
        self.inner.lock().unwrap().child_pid = pid;

        // Stream stdout + stderr into the ring buffer / events.
        if let Some(out) = child.stdout.take() {
            let app2 = app.clone();
            let this = self.clone_handles();
            tokio::spawn(async move {
                let mut lines = BufReader::new(out).lines();
                while let Ok(Some(line)) = lines.next_line().await {
                    this.append_log(&app2, line);
                }
            });
        }
        if let Some(err) = child.stderr.take() {
            let app2 = app.clone();
            let this = self.clone_handles();
            tokio::spawn(async move {
                let mut lines = BufReader::new(err).lines();
                while let Ok(Some(line)) = lines.next_line().await {
                    this.append_log(&app2, line);
                }
            });
        }

        *self.child.lock().await = Some(child);

        let candidates = crate::wsl_candidate_urls(via_wsl, url, free).await;
        match self.wait_for_ready_any(&candidates).await {
            Ok(reachable) => {
                // Adopt whichever address answered: under WSL that may be the
                // distribution's own IP rather than loopback.
                self.inner.lock().unwrap().server_url = reachable;
                self.set_status(app, PythonStatus::Running);
                Ok(())
            }
            Err(e) => {
                self.set_status(app, PythonStatus::Error);
                Err(e)
            }
        }
    }

    /// Last few captured lines, for embedding in a startup failure.
    fn recent_output(&self) -> String {
        let inner = self.inner.lock().unwrap();
        let tail: Vec<&str> = inner
            .logs
            .iter()
            .rev()
            .take(8)
            .map(String::as_str)
            .collect();
        if tail.is_empty() {
            return " It produced no output at all, which usually means the command \
                     itself could not run."
                .to_string();
        }
        let mut lines: Vec<&str> = tail;
        lines.reverse();
        format!("\n\n{}", lines.join("\n"))
    }

    /// Probe every candidate address until one serves health, returning it.
    ///
    /// All candidates are tried on each pass rather than one being given the
    /// full timeout first: when WSL loopback forwarding is broken, waiting out
    /// the whole budget on 127.0.0.1 before trying the reachable address would
    /// look like a dead backend for a minute.
    async fn wait_for_ready_any(&self, candidates: &[String]) -> Result<String, String> {
        let client = reqwest::Client::builder()
            .timeout(HEALTH_REQ_TIMEOUT)
            .build()
            .map_err(|e| e.to_string())?;
        let endpoints: Vec<(String, String)> = candidates
            .iter()
            .flat_map(|base| {
                ["/api/health", "/health", "/"]
                    .into_iter()
                    .map(move |path| (base.clone(), format!("{base}{path}")))
            })
            .collect();

        let start = Instant::now();
        while start.elapsed() < HEALTH_TIMEOUT {
            {
                let mut guard = self.child.lock().await;
                if let Some(c) = guard.as_mut() {
                    if let Ok(Some(status)) = c.try_wait() {
                        // "Check the logs" is useless advice when the backend
                        // died before writing any: quote what it actually
                        // printed, which is where the real cause is.
                        return Err(format!(
                            "Backend exited ({status}) before becoming ready.{}",
                            self.recent_output()
                        ));
                    }
                }
            }
            for (base, url) in &endpoints {
                if let Ok(resp) = client.get(url).send().await {
                    if resp.status().is_success() {
                        return Ok(base.clone());
                    }
                }
            }
            tokio::time::sleep(Duration::from_millis(150)).await;
        }
        Err(format!(
            "Backend did not become ready within {}s.",
            HEALTH_TIMEOUT.as_secs()
        ))
    }

    pub async fn stop(&self) -> Result<(), String> {
        let mut guard = self.child.lock().await;
        let Some(mut child) = guard.take() else {
            self.force_status(PythonStatus::Stopped);
            return Ok(());
        };
        self.force_status(PythonStatus::Stopping);

        // Graceful SIGTERM (Unix) then SIGKILL after grace; on Windows, kill().
        #[cfg(unix)]
        {
            if let Some(pid) = child.id() {
                use nix::sys::signal::{kill, Signal};
                use nix::unistd::Pid;
                let _ = kill(Pid::from_raw(pid as i32), Signal::SIGTERM);
            }
        }
        #[cfg(windows)]
        {
            let _ = child.start_kill();
        }

        let killed = tokio::time::timeout(FORCE_KILL_GRACE, child.wait()).await;
        if killed.is_err() {
            let _ = child.start_kill(); // SIGKILL on Unix
            let _ = child.wait().await;
        }
        self.force_status(PythonStatus::Stopped);
        Ok(())
    }

    pub async fn restart(&self, app: &AppHandle) -> Result<String, String> {
        self.stop().await?;
        self.start(app).await?;
        Ok(self.server_url())
    }

    fn force_status(&self, status: PythonStatus) {
        self.inner.lock().unwrap().status = status;
    }

    // Cheap handle clone for the reader tasks (shares the Arcs).
    fn clone_handles(&self) -> SupervisorHandles {
        SupervisorHandles {
            inner: self.inner.clone(),
        }
    }
}

#[derive(Clone)]
struct SupervisorHandles {
    inner: Arc<Mutex<Inner>>,
}

impl SupervisorHandles {
    fn append_log(&self, app: &AppHandle, line: String) {
        {
            let mut inner = self.inner.lock().unwrap();
            if inner.logs.len() >= MAX_LOG_LINES {
                inner.logs.pop_front();
            }
            inner.logs.push_back(line.clone());
        }
        let _ = app.emit("python:log", line);
    }
}
