use serde::Serialize;
use std::collections::VecDeque;
use std::process::Stdio;
use std::sync::Arc;
use tauri::{AppHandle, Emitter};
use tokio::io::{AsyncBufReadExt, BufReader};
use tokio::process::Command;
use tokio::sync::Mutex;

use crate::paths;

const PYTHON_VERSION: &str = "3.12";

/// How much stderr to quote back in a failure. Enough to carry a resolver
/// error and its context; not so much that the dialog becomes a log file.
const STDERR_TAIL_LINES: usize = 12;

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
    // Kept so the failure message can say WHY. Without this the user gets
    // `"…\uv.exe pip" exited with code Some(1)` and nothing else -- a report
    // nobody can act on, which is exactly what happened.
    let tail = Arc::new(Mutex::new(VecDeque::<String>::new()));
    let mut drained = None;
    if let Some(err) = child.stderr.take() {
        let app2 = app.clone();
        let ph = phase_owned.clone();
        let tail = Arc::clone(&tail);
        drained = Some(tokio::spawn(async move {
            let mut lines = BufReader::new(err).lines();
            while let Ok(Some(l)) = lines.next_line().await {
                let l = l.trim_end().to_string();
                if !l.is_empty() {
                    {
                        let mut t = tail.lock().await;
                        t.push_back(l.clone());
                        // Bounded: a resolver failure can print thousands of
                        // lines, and the last few are the ones that explain it.
                        while t.len() > STDERR_TAIL_LINES {
                            t.pop_front();
                        }
                    }
                    progress(&app2, &ph, l, None);
                }
            }
        }));
    }

    let status = child.wait().await.map_err(|e| e.to_string())?;
    if status.success() {
        return Ok(());
    }

    // Wait for the reader before quoting it. `wait()` can return while the
    // pipe still holds buffered output, which would leave the tail empty in
    // exactly the case it exists for. The pipe is closed once the process is
    // gone, so this cannot hang.
    if let Some(handle) = drained {
        let _ = handle.await;
    }

    let lines: Vec<String> = tail.lock().await.iter().cloned().collect();
    Err(format_failure(exe, args, status.code(), &lines))
}

/// Assemble the message a user actually sees when provisioning fails.
///
/// It used to be `"<exe> <args[0]>" exited with code Some(1)` and nothing else.
/// A real report read `"\\?\C:\Program Files\BioNodulo\uv\uv.exe pip" exited
/// with code Some(1)`, which does not say which of several uv invocations ran,
/// what path it was given, or why it failed -- and the reason had already been
/// captured and thrown away.
pub(crate) fn format_failure(
    exe: &str,
    args: &[String],
    code: Option<i32>,
    stderr_tail: &[String],
) -> String {
    let rendered = std::iter::once(exe.to_string())
        .chain(args.iter().cloned())
        .map(|a| if a.contains(' ') { format!("\"{a}\"") } else { a })
        .collect::<Vec<_>>()
        .join(" ");

    let code = match code {
        Some(c) => c.to_string(),
        // Killed by a signal, or by antivirus.
        None => "unknown (terminated by a signal)".to_string(),
    };

    if stderr_tail.is_empty() {
        format!("{rendered} exited with code {code}, and printed nothing to explain why")
    } else {
        format!("{rendered} exited with code {code}:\n{}", stderr_tail.join("\n"))
    }
}

#[cfg(test)]
mod tests {
    use super::format_failure;

    fn args(list: &[&str]) -> Vec<String> {
        list.iter().map(|s| s.to_string()).collect()
    }

    #[test]
    fn quotes_the_reason_the_command_failed() {
        // The whole point: the cause was captured and then discarded.
        let msg = format_failure(
            "uv.exe",
            &args(&["pip", "install"]),
            Some(1),
            &args(&["error: Failed to fetch: https://pypi.org/simple/fastapi/"]),
        );

        assert!(msg.contains("error: Failed to fetch"), "{msg}");
    }

    #[test]
    fn names_the_whole_command_not_just_the_subcommand() {
        // "uv.exe pip" does not distinguish install from upgrade, nor say
        // which path was passed.
        let msg = format_failure("uv.exe", &args(&["pip", "install", "-e", "C:/app"]), Some(1), &[]);

        assert!(msg.contains("pip install -e C:/app"), "{msg}");
    }

    #[test]
    fn quotes_arguments_containing_spaces() {
        // Otherwise the message is ambiguous about where the path ends —
        // "Program Files" reads as two arguments.
        let msg = format_failure(
            "uv.exe",
            &args(&["pip", "install", "-e", r"C:\Program Files\BioNodulo"]),
            Some(1),
            &[],
        );

        assert!(msg.contains(r#""C:\Program Files\BioNodulo""#), "{msg}");
    }

    #[test]
    fn says_so_when_there_was_no_output() {
        // Silence is itself a clue (antivirus, OOM), so do not imply a cause.
        let msg = format_failure("uv.exe", &args(&["pip"]), Some(1), &[]);

        assert!(msg.contains("printed nothing"), "{msg}");
    }

    #[test]
    fn reports_a_signal_kill_as_such() {
        // `Some(1)` and `None` mean very different things; "code None" told
        // the user nothing.
        let msg = format_failure("uv.exe", &args(&["pip"]), None, &[]);

        assert!(msg.contains("terminated by a signal"), "{msg}");
        assert!(!msg.contains("None"), "{msg}");
    }

    #[test]
    fn keeps_every_captured_line_in_order() {
        let msg = format_failure(
            "uv.exe",
            &args(&["pip"]),
            Some(2),
            &args(&["first", "second", "third"]),
        );

        let body = msg.split_once(":\n").expect("no reason section").1;
        assert_eq!(body, "first\nsecond\nthird");
    }
}
