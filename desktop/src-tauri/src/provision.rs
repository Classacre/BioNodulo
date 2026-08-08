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
            let e = format!("{e}\n\n{}", diagnostics(app));
            progress(app, "error", e.clone(), None);
            Err(e)
        }
    }
}

/// What a report of a provisioning failure has to contain to be actionable.
///
/// Three rounds of this bug were spent guessing at facts only the machine had.
/// Which build is installed was assumed twice and wrong at least once; whether
/// the recorded interpreter existed had to be asked for; that a *directory*
/// survived while the interpreter inside it did not was discovered by asking a
/// third time. All of it is one paste away if the app simply says so.
fn diagnostics(app: &AppHandle) -> String {
    let venv = paths::venv_path(app);
    let bundled = paths::embedded_python_exe(&paths::embedded_python_dir(app));
    let mark = |p: &std::path::Path| if p.exists() { "present" } else { "MISSING" };

    let mut out = format!(
        "BioNodulo {} ({})\n  venv:    {}\n  bundled: {} [{}]",
        env!("CARGO_PKG_VERSION"),
        paths::os_key(),
        venv.display(),
        bundled.display(),
        mark(&bundled),
    );
    let recorded = paths::recorded_interpreters(&venv);
    if recorded.is_empty() {
        out.push_str("\n  recorded: none (no pyvenv.cfg)");
    }
    for path in recorded {
        out.push_str(&format!("\n  recorded: {} [{}]", path.display(), mark(&path)));
    }
    // Stripped before uv runs, but worth naming: a report where one of these is
    // set explains a failure that otherwise looks impossible.
    for key in HOSTILE_TO_INHERIT {
        if let Ok(value) = std::env::var(key) {
            out.push_str(&format!("\n  inherited: {key}={value} (ignored)"));
        }
    }
    out
}

async fn run_setup(app: &AppHandle) -> Result<(), String> {
    create_venv(app).await?;
    install_with_recovery(app, false).await?;
    verify(app).await
}

async fn create_venv(app: &AppHandle) -> Result<(), String> {
    let venv = paths::venv_path(app);
    if paths::venv_exists(&venv) && paths::venv_is_usable(app, &venv) {
        return Ok(());
    }
    rebuild_venv(app).await
}

/// Discard whatever environment is there and build a fresh one.
///
/// The usual reason is an upgrade that replaced or moved the interpreter the
/// venv was created from: the venv lives in the user's roaming data directory,
/// which no installer touches, so it outlives the installation it points at.
/// Rebuilding is the only recovery, and doing it here spares the user deleting
/// a directory they have no reason to know exists.
async fn rebuild_venv(app: &AppHandle) -> Result<(), String> {
    let venv = paths::venv_path(app);
    if venv.exists() {
        progress(app, "venv", "Rebuilding the Python environment…", Some(0.05));
        log::warn!("[provision] discarding the venv at {}", venv.display());
        // Not ignored. A removal that quietly fails -- Windows holds a handle
        // on a running interpreter, and antivirus locks files mid-scan --
        // leaves the old `pyvenv.cfg` in place, so the "rebuilt" environment
        // would still name the dead interpreter and fail exactly as before.
        std::fs::remove_dir_all(&venv).map_err(|e| {
            format!(
                "Could not remove the old Python environment at \"{}\": {e}. \
                 Close BioNodulo and delete that folder, then run setup again.",
                venv.display()
            )
        })?;
    } else {
        progress(app, "venv", "Creating Python environment…", Some(0.1));
    }
    if let Some(parent) = venv.parent() {
        let _ = std::fs::create_dir_all(parent);
    }

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

async fn install_requirements(app: &AppHandle, upgrade: bool) -> Result<(), String> {
    progress(
        app,
        "deps",
        if upgrade {
            "Upgrading dependencies…"
        } else {
            "Installing dependencies (this may take a few minutes)…"
        },
        Some(0.3),
    );
    let backend = paths::backend_path(app);
    let mut args: Vec<String> = vec!["pip".into(), "install".into()];
    if upgrade {
        args.push("--upgrade".into());
    }
    args.extend([
        "-e".into(),
        backend.to_string_lossy().into_owned(),
        "--index-strategy".into(),
        "unsafe-best-match".into(),
    ]);
    run_uv(app, &args, "deps").await
}

/// Install, and if the environment turns out to be dead, rebuild it and retry.
///
/// `venv_is_usable` inspects `pyvenv.cfg` before we get here, so this should
/// not trigger. It exists because that check and uv are two separate readers of
/// the same file, and a user who hits a case where they disagree gets a dead
/// end: an error naming a path they never chose, and no way to recover short of
/// deleting a directory they cannot be expected to find.
///
/// It has earned its place. This class of failure shipped three times, and the
/// third report came from a build where the pre-flight check passed on a venv
/// uv then refused. Load-bearing, not belt-and-braces.
async fn install_with_recovery(app: &AppHandle, upgrade: bool) -> Result<(), String> {
    let Err(err) = install_requirements(app, upgrade).await else {
        return Ok(());
    };
    if !is_dead_environment(&err) {
        return Err(err);
    }
    log::warn!("[provision] environment is unusable, rebuilding and retrying: {err}");
    rebuild_venv(app).await?;
    // Nothing is installed in a freshly built environment, so there is nothing
    // to upgrade.
    let Err(err) = install_requirements(app, false).await else {
        return Ok(());
    };
    if !is_dead_environment(&err) {
        return Err(err);
    }
    // A freshly built environment, from an interpreter this installation ships
    // and has just verified, and uv STILL cannot make a build environment out
    // of it. At that point the fault is not in the venv and rebuilding it again
    // would be superstition, so stop trying to make that step work and stop
    // performing it.
    log::warn!("[provision] build isolation is broken on this machine; installing without it");
    progress(
        app,
        "deps",
        "Retrying without an isolated build environment…",
        Some(0.6),
    );
    install_without_build_isolation(app).await
}

/// The build backends the package needs, when nothing isolates the build.
///
/// Mirrors `[build-system] requires` in the backend's `pyproject.toml`;
/// `build_requirements_match_the_backend` fails if they drift apart.
const BUILD_REQUIREMENTS: [&str; 1] = ["hatchling"];

/// Install with no temporary build environment at all.
///
/// Every report of this failure has been the same line -- `Failed to create
/// temporary virtualenv` -- from a machine whose venv was correct and whose
/// bundled interpreter was present. Three rounds went into making that step
/// succeed. It cannot fail if it does not happen.
///
/// The cost is that the build backend has to live in the environment itself
/// rather than in a throwaway one, which is why this is the last resort and not
/// the default: it is a slightly dirtier environment, in exchange for an
/// install that completes.
async fn install_without_build_isolation(app: &AppHandle) -> Result<(), String> {
    let mut seed: Vec<String> = vec!["pip".into(), "install".into()];
    seed.extend(BUILD_REQUIREMENTS.iter().map(|s| (*s).to_string()));
    seed.extend(["--index-strategy".into(), "unsafe-best-match".into()]);
    run_uv(app, &seed, "deps").await?;

    let backend = paths::backend_path(app);
    run_uv(
        app,
        &[
            "pip".into(),
            "install".into(),
            "-e".into(),
            backend.to_string_lossy().into_owned(),
            "--no-build-isolation".into(),
            "--index-strategy".into(),
            "unsafe-best-match".into(),
        ],
        "deps",
    )
    .await
}

/// Whether a failure means the environment's interpreter is gone.
///
/// uv builds each dependency in a *temporary* virtualenv created from the
/// interpreter the target environment records, so an environment that starts
/// perfectly can still be unable to install anything:
///
///     ├─▶ Failed to create temporary virtualenv
///     ╰─▶ Could not find a suitable Python executable for the virtual
///         environment based on the interpreter: …\python-embedded\python.exe
///
/// The same dead base reports itself differently depending on how far uv gets,
/// and which one you see depends on whether the venv's own interpreter still
/// runs. All three were observed for one cause:
///
///   - it runs           -> uv resolves, then fails building (the report above)
///   - it does not run   -> `No virtual environment found`, before resolving
///   - launched directly -> the Windows stub exits 103 with `No Python at '…'`
///
/// `No virtual environment found` is safe to treat as fatal here only because
/// this runs after the venv has been created and confirmed to exist. Reaching
/// it means the environment is there and unusable, which is precisely the case
/// worth rebuilding for.
///
/// Public so `tests/venv_recovery.rs` can hold real uv output against it rather
/// than a copy of these strings, which would pass while the app still failed.
pub fn is_dead_environment(message: &str) -> bool {
    const SIGNATURES: [&str; 4] = [
        "Failed to create temporary virtualenv",
        "Could not find a suitable Python executable",
        "No virtual environment found",
        "No Python at",
    ];
    SIGNATURES.iter().any(|s| message.contains(s))
}

pub async fn update_dependencies(app: &AppHandle) -> Result<(), String> {
    let venv = paths::venv_path(app);
    if !paths::venv_exists(&venv) {
        return Err("Environment not set up yet.".into());
    }
    // Upgrading into an environment whose base interpreter is gone fails in the
    // build step, not here, and reports a path the user never chose. Setup
    // already refuses to use such an environment; this path has to as well.
    if !paths::venv_is_usable(app, &venv) {
        rebuild_venv(app).await?;
    }
    install_with_recovery(app, true).await?;
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
        // Ignore any uv.toml on the machine. The app's environment is not the
        // user's Python project, and a setting meant for their work should not
        // decide how the bundled backend installs.
        ("UV_NO_CONFIG", "1".into()),
        // A cache of our own, beside the venv it describes. uv caches
        // interpreter metadata keyed by executable path, and this app rebuilds
        // to the SAME path every time; a shared cache therefore carries
        // knowledge of environments belonging to installations that are gone.
        // Costs one re-download after upgrading, and buys a machine whose past
        // cannot reach into this install.
        (
            "UV_CACHE_DIR",
            paths::data_root(app)
                .join("uv-cache")
                .to_string_lossy()
                .into_owned(),
        ),
    ];
    run_stream(app, uv.to_string_lossy().as_ref(), args, phase, &extra).await
}

/// Inherited variables that redirect a Python or uv invocation.
///
/// A user hit a failure naming an interpreter from an installation removed
/// versions ago, on a machine where the venv was correct and the bundled
/// interpreter present -- so something outside both was steering uv. None of
/// these are ours to honour: whatever the user's shell has configured for their
/// own Python work, this install has exactly one interpreter and one
/// environment, and both are decided here.
const HOSTILE_TO_INHERIT: [&str; 6] = [
    "UV_PYTHON",
    "UV_PYTHON_INSTALL_DIR",
    "UV_SYSTEM_PYTHON",
    "PYTHONHOME",
    "PYTHONPATH",
    "__PYVENV_LAUNCHER__",
];

async fn run_stream(
    app: &AppHandle,
    exe: &str,
    args: &[String],
    phase: &str,
    extra_env: &[(&str, String)],
) -> Result<(), String> {
    let mut cmd = Command::new(exe);
    cmd.args(args).stdout(Stdio::piped()).stderr(Stdio::piped());
    for key in HOSTILE_TO_INHERIT {
        cmd.env_remove(key);
    }
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
    use super::{format_failure, is_dead_environment};

    fn args(list: &[&str]) -> Vec<String> {
        list.iter().map(|s| s.to_string()).collect()
    }

    /// The message a user actually received, verbatim.
    const REPORTED_FAILURE: &str = concat!(
        r#""\\?\C:\Program Files\BioNodulo\uv\uv.exe" pip install -e "#,
        r#""\\?\C:\Program Files\BioNodulo\bionodulo-backend" "#,
        "--index-strategy unsafe-best-match exited with code 1:\n",
        "Using Python 3.12.8 environment at: ",
        r"C:\Users\nieuw\AppData\Roaming\com.bionodulo.desktop\venv",
        "\n",
        "Resolved 110 packages in 275ms\n",
        "  × Failed to build bionodulo @ ",
        "file:///C:/Program%20Files/BioNodulo/bionodulo-backend\n",
        "  ├─▶ Failed to create temporary virtualenv\n",
        "  ╰─▶ Could not find a suitable Python executable for the virtual ",
        "environment based on the interpreter: ",
        r"C:\Users\nieuw\AppData\Local\BioNodulo\python-embedded\python.exe",
    );

    /// The fallback install puts the build backend in the environment itself,
    /// so this list has to be whatever the package declares. If they drift, the
    /// fallback fails on a missing backend at the exact moment it is the last
    /// thing standing between the user and a broken install.
    #[test]
    fn build_requirements_match_the_backend() {
        let pyproject = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
            .join("../../pyproject.toml");
        let text = std::fs::read_to_string(&pyproject)
            .unwrap_or_else(|e| panic!("cannot read {}: {e}", pyproject.display()));

        let requires = text
            .split("[build-system]")
            .nth(1)
            .and_then(|s| s.split("requires").nth(1))
            .and_then(|s| s.split('[').nth(1))
            .and_then(|s| s.split(']').next())
            .expect("no [build-system] requires in pyproject.toml");

        let declared: Vec<String> = requires
            .split(',')
            .map(|s| s.trim().trim_matches(['"', '\'']).to_string())
            .filter(|s| !s.is_empty())
            .collect();

        assert_eq!(
            declared,
            super::BUILD_REQUIREMENTS.to_vec(),
            "the fallback install seeds {:?} but the backend declares {declared:?}",
            super::BUILD_REQUIREMENTS
        );
    }

    #[test]
    fn recognises_the_reported_failure_as_a_dead_environment() {
        // If this stops matching, the app stops recovering and the user is
        // back at an error naming a path they never chose.
        assert!(is_dead_environment(REPORTED_FAILURE));
    }

    #[test]
    fn recognises_the_variant_where_the_venv_no_longer_starts() {
        // Observed on Windows CI, from the same cause: with the base gone the
        // venv's own interpreter cannot start, so uv never gets as far as
        // building and reports the environment as absent instead.
        assert!(is_dead_environment(
            "error: No virtual environment found; run `uv venv` to create an \
             environment, or pass `--system` to install into a non-virtual environment"
        ));
    }

    #[test]
    fn recognises_the_launcher_stub_variant() {
        // Same dead base, different reporter: the Windows venv launcher.
        assert!(is_dead_environment(
            r#"Backend exited (exit code: 103) ... No Python at '"C:\x\python.exe'"#
        ));
    }

    #[test]
    fn does_not_rebuild_for_unrelated_failures() {
        // Rebuilding costs minutes and discards a working environment, so a
        // network or resolver failure must not trigger it.
        assert!(!is_dead_environment(
            "error: Failed to fetch: https://pypi.org/simple/fastapi/"
        ));
        assert!(!is_dead_environment(
            "error: No solution found when resolving dependencies"
        ));
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
