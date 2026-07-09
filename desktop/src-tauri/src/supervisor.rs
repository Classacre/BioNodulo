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
        if !main_script.exists() {
            self.set_status(app, PythonStatus::Error);
            return Err(format!(
                "Backend entry script not found at \"{}\".",
                main_script.display()
            ));
        }

        let free = port::find_free_port(8188).map_err(|e| e.to_string())?;
        let url = format!("http://127.0.0.1:{free}");
        {
            let mut inner = self.inner.lock().unwrap();
            inner.port = free;
            inner.server_url = url.clone();
        }

        let _ = std::fs::create_dir_all(&workspace);
        let _ = std::fs::create_dir_all(&logs);

        let cors_origins = format!("{},https://cloud.bionodulo.com", url);
        let cf = crate::paths::cloudflared_path(app);
        let mut cmd = Command::new(&python);
        cmd.arg(&main_script)
            .arg("--host")
            .arg("127.0.0.1")
            .arg("--port")
            .arg(free.to_string())
            .arg("--project-root")
            .arg(&workspace)
            .current_dir(&backend)
            .env("PYTHONPATH", &backend)
            .env("PYTHONUNBUFFERED", "1")
            .env("VIRTUAL_ENV", &venv)
            .env("BIONODULO_HOST", "127.0.0.1")
            .env("BIONODULO_PORT", free.to_string())
            .env("BIONODULO_CORS_ORIGINS", &cors_origins)
            .env("BIONODULO_CORS_ALLOW_LOOPBACK", "1")
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .kill_on_drop(false);
        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            const CREATE_NO_WINDOW: u32 = 0x0800_0000;
            cmd.creation_flags(CREATE_NO_WINDOW);
        }
        if cf.exists() {
            cmd.env("BIONODULO_CLOUDFLARED", cf.to_string_lossy().to_string());
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

        match self.wait_for_ready(&url).await {
            Ok(()) => {
                self.set_status(app, PythonStatus::Running);
                Ok(())
            }
            Err(e) => {
                self.set_status(app, PythonStatus::Error);
                Err(e)
            }
        }
    }

    async fn wait_for_ready(&self, base: &str) -> Result<(), String> {
        let client = reqwest::Client::builder()
            .timeout(HEALTH_REQ_TIMEOUT)
            .build()
            .map_err(|e| e.to_string())?;
        let endpoints = [
            format!("{base}/api/health"),
            format!("{base}/health"),
            format!("{base}/"),
        ];
        let start = Instant::now();
        while start.elapsed() < HEALTH_TIMEOUT {
            // Bail if the child already exited.
            {
                let mut guard = self.child.lock().await;
                if let Some(c) = guard.as_mut() {
                    if let Ok(Some(_)) = c.try_wait() {
                        return Err("Backend exited before becoming ready. Check the logs.".into());
                    }
                }
            }
            for url in &endpoints {
                if let Ok(resp) = client.get(url).send().await {
                    if resp.status().is_success() {
                        return Ok(());
                    }
                }
            }
            tokio::time::sleep(Duration::from_millis(500)).await;
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
