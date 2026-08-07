use serde::Serialize;
use std::process::Stdio;
use tauri::{AppHandle, Emitter};
use tokio::io::{AsyncBufReadExt, BufReader};
use tokio::process::Command;

use crate::paths;

const PYTHON_VERSION: &str = "3.12";

#[derive(Serialize, Clone)]
pub struct SetupProgress {
    pub phase: String,
    pub message: String,
    pub fraction: Option<f64>,
}

fn progress(app: &AppHandle, phase: &str, message: impl Into<String>, fraction: Option<f64>) {
    let _ = app.emit(
        "setup:progress",
        SetupProgress {
            phase: phase.into(),
            message: message.into(),
            fraction,
        },
    );
}

pub async fn setup(app: &AppHandle) -> Result<(), String> {
    match run_setup(app).await {
        Ok(()) => {
            progress(app, "done", "Environment ready.", Some(1.0));
            Ok(())
        }
        Err(e) => {
            progress(app, "error", e.clone(), None);
            Err(e)
        }
    }
}

async fn run_setup(app: &AppHandle) -> Result<(), String> {
    create_venv(app).await?;
    install_requirements(app).await?;
    verify(app).await
}

async fn create_venv(app: &AppHandle) -> Result<(), String> {
    let venv = paths::venv_path(app);
    if paths::venv_exists(&venv) {
        if paths::venv_is_usable(&venv) {
            return Ok(());
        }
        // Present but broken -- almost always an upgrade that replaced the
        // bundled interpreter the venv still points at. Rebuilding is the only
        // recovery, and doing it here spares the user deleting a directory they
        // have no reason to know exists.
        progress(app, "venv", "Rebuilding the Python environment…", Some(0.05));
        log::warn!("[provision] venv at {} cannot start; rebuilding", venv.display());
        let _ = std::fs::remove_dir_all(&venv);
    }
    if let Some(parent) = venv.parent() {
        let _ = std::fs::create_dir_all(parent);
    }
    progress(app, "venv", "Creating Python environment…", Some(0.1));

    let selector = python_selector(app);
    run_uv(
        app,
        &[
            "venv".into(),
            venv.to_string_lossy().into_owned(),
            "--python".into(),
            selector,
            "--seed".into(),
        ],
        "venv",
    )
    .await
}

async fn install_requirements(app: &AppHandle) -> Result<(), String> {
    progress(
        app,
        "deps",
        "Installing dependencies (this may take a few minutes)…",
        Some(0.3),
    );
    let backend = paths::backend_path(app);
    run_uv(
        app,
        &[
            "pip".into(),
            "install".into(),
            "-e".into(),
            backend.to_string_lossy().into_owned(),
            "--index-strategy".into(),
            "unsafe-best-match".into(),
        ],
        "deps",
    )
    .await
}

pub async fn update_dependencies(app: &AppHandle) -> Result<(), String> {
    let venv = paths::venv_path(app);
    if !paths::venv_exists(&venv) {
        return Err("Environment not set up yet.".into());
    }
    progress(app, "deps", "Upgrading dependencies…", None);
    let backend = paths::backend_path(app);
    run_uv(
        app,
        &[
            "pip".into(),
            "install".into(),
            "--upgrade".into(),
            "-e".into(),
            backend.to_string_lossy().into_owned(),
            "--index-strategy".into(),
            "unsafe-best-match".into(),
        ],
        "deps",
    )
    .await?;
    verify(app).await?;
    progress(app, "done", "Dependencies up to date.", Some(1.0));
    Ok(())
}

async fn verify(app: &AppHandle) -> Result<(), String> {
    progress(app, "verify", "Verifying environment…", Some(0.95));
    let venv = paths::venv_path(app);
    let python = paths::venv_python(&venv);
    if !python.exists() {
        return Err(format!(
            "venv interpreter missing after setup: {}",
            python.display()
        ));
    }
    run_stream(
        app,
        python.to_string_lossy().as_ref(),
        &[
            "-c".into(),
            "import bionodulo, uvicorn, fastapi".into(),
        ],
        "verify",
        &[],
    )
    .await
}

fn python_selector(app: &AppHandle) -> String {
    let embedded = paths::embedded_python_exe(&paths::embedded_python_dir(app));
    if embedded.exists() {
        embedded.to_string_lossy().into_owned()
    } else {
        PYTHON_VERSION.to_string()
    }
}

async fn run_uv(app: &AppHandle, args: &[String], phase: &str) -> Result<(), String> {
    let uv = paths::uv_exe(app);
    if !uv.exists() {
        return Err(format!(
            "Bundled uv binary not found at \"{}\".",
            uv.display()
        ));
    }
    let venv = paths::venv_path(app);
    let extra = [
        ("VIRTUAL_ENV", venv.to_string_lossy().into_owned()),
        ("UV_PYTHON_PREFERENCE", "only-system".into()),
        ("UV_NO_PROGRESS", "1".into()),
    ];
    run_stream(app, uv.to_string_lossy().as_ref(), args, phase, &extra).await
}

async fn run_stream(
    app: &AppHandle,
    exe: &str,
    args: &[String],
    phase: &str,
    extra_env: &[(&str, String)],
) -> Result<(), String> {
    let mut cmd = Command::new(exe);
    cmd.args(args).stdout(Stdio::piped()).stderr(Stdio::piped());
    for (k, v) in extra_env {
        cmd.env(k, v);
    }
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        cmd.creation_flags(0x0800_0000);
    }
    let mut child = cmd
        .spawn()
        .map_err(|e| format!("failed to launch {exe}: {e}"))?;

    let phase_owned = phase.to_string();
    if let Some(out) = child.stdout.take() {
        let app2 = app.clone();
        let ph = phase_owned.clone();
        tokio::spawn(async move {
            let mut lines = BufReader::new(out).lines();
            while let Ok(Some(l)) = lines.next_line().await {
                let l = l.trim_end().to_string();
                if !l.is_empty() {
                    progress(&app2, &ph, l, None);
                }
            }
        });
    }
    if let Some(err) = child.stderr.take() {
        let app2 = app.clone();
        let ph = phase_owned.clone();
        tokio::spawn(async move {
            let mut lines = BufReader::new(err).lines();
            while let Ok(Some(l)) = lines.next_line().await {
                let l = l.trim_end().to_string();
                if !l.is_empty() {
                    progress(&app2, &ph, l, None);
                }
            }
        });
    }

    let status = child.wait().await.map_err(|e| e.to_string())?;
    if status.success() {
        Ok(())
    } else {
        Err(format!(
            "\"{} {}\" exited with code {:?}",
            exe,
            args.first().cloned().unwrap_or_default(),
            status.code()
        ))
    }
}
