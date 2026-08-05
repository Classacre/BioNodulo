//! End-to-end smoke test for Windows local execution.
//!
//! Everything else about the WSL path is unit-tested pure logic. This is the
//! part that can only be proven by running it: importing the distribution,
//! installing the engine, and launching the backend so it answers on a port
//! reachable from Windows.
//!
//! Ignored by default because it needs a real Windows host with WSL2, takes
//! several minutes, and downloads a Linux userland. CI runs it explicitly:
//!
//!     cargo test --test wsl_smoke -- --ignored --nocapture
//!
//! It exists because two bugs shipped that no unit test could have caught: a
//! Windows path handed to the Linux interpreter, and an environment set on
//! wsl.exe that never reached the process inside the distribution. Both killed
//! the backend instantly, with an empty log.

#![cfg(windows)]

use std::path::{Path, PathBuf};
use std::process::Stdio;
use std::time::{Duration, Instant};

use app_lib::wsl;

/// Repository root: this crate is at desktop/src-tauri.
fn repo_root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("..")
        .canonicalize()
        .expect("repository root")
}

fn wsl_command() -> tokio::process::Command {
    let mut cmd = tokio::process::Command::new("wsl.exe");
    use std::os::windows::process::CommandExt;
    cmd.creation_flags(0x0800_0000);
    cmd
}

#[tokio::test]
#[ignore = "needs a Windows host with WSL2; run with --ignored"]
async fn the_backend_starts_inside_the_distribution_and_answers() {
    let root = repo_root();
    let data = std::env::temp_dir().join("bionodulo-wsl-smoke");
    std::fs::create_dir_all(&data).expect("scratch directory");

    // 1. Provision. Skipped when a previous run already left the distribution
    //    in place, so re-running locally is cheap.
    match wsl::runtime::readiness().await {
        wsl::WslReadiness::Ready => eprintln!("[smoke] distribution already present"),
        state => {
            assert!(
                !matches!(
                    state,
                    wsl::WslReadiness::NotInstalled | wsl::WslReadiness::RebootRequired
                ),
                "WSL2 is not usable on this machine: {}",
                state.message()
            );
            wsl::runtime::provision(&data, |m| eprintln!("[smoke] {m}"))
                .await
                .expect("provision the distribution");
        }
    }

    // 2. Install the engine from the Windows-side checkout, exactly as the app
    //    does from its resources directory.
    wsl::runtime::install_backend(&root, |m| eprintln!("[smoke] {m}"))
        .await
        .expect("install the engine");

    // 3. Launch the backend through the same argument builder the app uses.
    let port = wsl::MIN_FORWARDED_PORT;
    let workdir = wsl::to_wsl_path(&root).expect("translate the repository path");
    let script = wsl::to_wsl_path(&root.join("main.py")).expect("translate the entry script");
    let argv = wsl::backend_argv(
        &workdir,
        &wsl::linux_python(),
        &script,
        &[
            "--host".into(),
            "0.0.0.0".into(),
            "--port".into(),
            port.to_string(),
            "--project-root".into(),
            wsl::linux_workspace(),
        ],
        &[
            ("PYTHONPATH".into(), workdir.clone()),
            ("PYTHONUNBUFFERED".into(), "1".into()),
            ("VIRTUAL_ENV".into(), wsl::venv_path()),
            ("BIONODULO_HOST".into(), "0.0.0.0".into()),
            ("BIONODULO_PORT".into(), port.to_string()),
            ("BIONODULO_CORS_ALLOW_LOOPBACK".into(), "1".into()),
        ],
    );

    let mut child = wsl_command()
        .args(&argv)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .expect("spawn the backend");

    // 4. Reachable from Windows. This is the assertion that matters: a backend
    //    bound only to loopback inside the VM would pass every unit test and
    //    still be invisible here.
    let client = reqwest::Client::builder()
        .timeout(Duration::from_secs(3))
        .build()
        .expect("http client");
    let vm_ip = wsl::runtime::vm_ip().await;
    let urls = wsl::candidate_urls(port, vm_ip.as_deref());

    let deadline = Instant::now() + Duration::from_secs(180);
    let mut reached = None;
    while Instant::now() < deadline && reached.is_none() {
        if let Ok(Some(status)) = child.try_wait() {
            let output = child.wait_with_output().await.expect("collect output");
            panic!(
                "backend exited ({status}) before answering.\nstdout:\n{}\nstderr:\n{}",
                String::from_utf8_lossy(&output.stdout),
                String::from_utf8_lossy(&output.stderr),
            );
        }
        for base in &urls {
            if let Ok(response) = client.get(format!("{base}/api/health")).send().await {
                if response.status().is_success() {
                    reached = Some(base.clone());
                    break;
                }
            }
        }
        tokio::time::sleep(Duration::from_millis(500)).await;
    }

    let _ = child.kill().await;
    let reached = reached.unwrap_or_else(|| {
        panic!("backend never answered on any of {urls:?}");
    });
    eprintln!("[smoke] backend answered on {reached}");
}

#[tokio::test]
#[ignore = "needs a Windows host with WSL2; run with --ignored"]
async fn the_workspace_is_writable_and_lives_on_ext4() {
    // A workspace silently landing on /mnt/c would still work, just ~10x
    // slower on every file operation -- the kind of regression nobody notices
    // until a run takes all afternoon.
    let script = format!(
        "set -e; mkdir -p {0}; touch {0}/.probe; df --output=fstype {0} | tail -1",
        wsl::linux_workspace()
    );
    let output = wsl_command()
        .args(wsl::exec_args("/", "sh", &["-lc".to_string(), script]))
        .output()
        .await
        .expect("run the probe");

    assert!(output.status.success(), "probe failed: {output:?}");
    let fstype = String::from_utf8_lossy(&output.stdout).trim().to_string();
    assert!(
        fstype.contains("ext4"),
        "workspace is on {fstype:?}, expected ext4"
    );
}
