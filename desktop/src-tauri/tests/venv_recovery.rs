//! Prove the app's own decision about a stale venv matches what uv does.
//!
//! A user upgraded and hit:
//!
//!     "\\?\C:\Program Files\BioNodulo\uv\uv.exe" pip install -e
//!     "\\?\C:\Program Files\BioNodulo\bionodulo-backend" ... exited with code 1:
//!     Using Python 3.12.8 environment at: …\Roaming\com.bionodulo.desktop\venv
//!     × Failed to build bionodulo @ file:///C:/Program%20Files/BioNodulo/…
//!     ├─▶ Failed to create temporary virtualenv
//!     ╰─▶ Could not find a suitable Python executable for the virtual
//!         environment based on the interpreter:
//!         C:\Users\…\AppData\Local\BioNodulo\python-embedded\python.exe
//!
//! `%LOCALAPPDATA%\BioNodulo` is where the per-user installer put the app
//! before the switch to `perMachine`. The venv lives in the roaming data
//! directory, which no upgrade touches, so it kept naming an interpreter that
//! belonged to an installation replaced several versions ago.
//!
//! `paths::venv_is_usable` is supposed to catch exactly that. Its unit tests
//! assert against hand-written `pyvenv.cfg` files, which proves the parser and
//! nothing else: whether the key uv actually writes on Windows is the key uv
//! later reads back was still an assumption. This test removes it by building a
//! real venv with the bundled uv, deleting the interpreter it came from, and
//! requiring that the path uv refuses to build from is the same path the app
//! tests for.
//!
//! Ignored by default -- it needs the staged assets and talks to the network.
//!
//!     cargo test --test venv_recovery -- --ignored --nocapture

#![cfg(windows)]

use std::path::{Path, PathBuf};
use std::process::Command;

use app_lib::paths;

/// Repository root: this crate is at desktop/src-tauri.
fn repo_root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("..")
        .canonicalize()
        .expect("repository root")
}

fn assets() -> PathBuf {
    repo_root().join("desktop").join("assets")
}

fn staged(kind: &str, exe: &str) -> PathBuf {
    let path = assets().join(kind).join("windows").join(exe);
    assert!(
        path.exists(),
        "{} not staged at {} -- run `npm run prepare:assets` in desktop/",
        exe,
        path.display()
    );
    path
}

fn scratch(name: &str) -> PathBuf {
    let dir = std::env::temp_dir().join(format!("bn-venv-recovery-{name}"));
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).expect("scratch dir");
    dir
}

fn copy_tree(from: &Path, to: &Path) {
    std::fs::create_dir_all(to).expect("create destination");
    for entry in std::fs::read_dir(from).expect("read source") {
        let entry = entry.expect("dir entry");
        let dest = to.join(entry.file_name());
        if entry.file_type().expect("file type").is_dir() {
            copy_tree(&entry.path(), &dest);
        } else {
            std::fs::copy(entry.path(), &dest).expect("copy file");
        }
    }
}

fn uv(args: &[&str], venv: &Path) -> std::process::Output {
    Command::new(staged("uv", "uv.exe"))
        .args(args)
        .env("VIRTUAL_ENV", venv)
        .env("UV_PYTHON_PREFERENCE", "only-system")
        .env("UV_NO_PROGRESS", "1")
        .output()
        .expect("run uv")
}

fn starts(python: &Path) -> bool {
    matches!(Command::new(python).arg("--version").output(), Ok(o) if o.status.success())
}

/// The whole failure and its recovery, against real uv.
///
/// Run as one test because each step is the setup for the next and the venv
/// creation costs real time; splitting them would triple the runtime to
/// re-derive identical state.
#[test]
#[ignore = "needs staged assets and network; run explicitly on Windows CI"]
fn a_venv_whose_base_interpreter_is_gone_is_rejected_and_rebuildable() {
    let bundled = staged("python-embedded", "python.exe");
    let work = scratch("case");
    let venv = work.join("venv");

    // Stand in for the interpreter a previous installation owned. Copying it
    // rather than using the bundled one directly is what makes it removable.
    let owned_by_old_install = work.join("python-embedded");
    copy_tree(
        bundled.parent().expect("python-embedded dir"),
        &owned_by_old_install,
    );
    let old_python = owned_by_old_install.join("python.exe");

    let out = uv(
        &[
            "venv",
            &venv.to_string_lossy(),
            "--python",
            &old_python.to_string_lossy(),
            "--seed",
        ],
        &venv,
    );
    assert!(
        out.status.success(),
        "uv venv failed: {}",
        String::from_utf8_lossy(&out.stderr)
    );

    // What uv actually recorded. Printed because the entire question is which
    // key it writes, and a future uv could change it.
    let cfg = std::fs::read_to_string(venv.join("pyvenv.cfg")).expect("pyvenv.cfg");
    println!("=== pyvenv.cfg as written by uv ===\n{cfg}");

    let recorded = paths::recorded_base_interpreter(&venv)
        .expect("uv wrote no interpreter this app can read");
    assert_eq!(
        recorded, old_python,
        "the app reads a different interpreter than uv was given"
    );

    // A healthy venv must not be rebuilt: doing so on every launch costs the
    // user minutes and is how an over-eager check gets reverted.
    assert!(
        paths::venv_is_usable(&venv),
        "a freshly created venv was judged unusable"
    );

    // The upgrade: the old installation's interpreter goes away.
    std::fs::remove_dir_all(&owned_by_old_install).expect("remove old interpreter");

    // The trap that let this ship twice. Whether the venv still starts depends
    // on how it was built -- a launcher stub exits 103, a self-contained copy
    // runs fine -- so starting is not the property that decides anything.
    println!(
        "venv python still starts after the base was removed: {}",
        starts(&paths::venv_python(&venv))
    );

    assert!(
        !paths::venv_is_usable(&venv),
        "a venv whose base interpreter is gone was judged usable"
    );

    // And uv agrees, for the same reason and about the same path. Without this
    // the check could be testing a path uv never consults.
    let out = uv(
        &[
            "pip",
            "install",
            "-e",
            &repo_root()
                .join("desktop")
                .join("assets")
                .join("bionodulo-backend")
                .to_string_lossy(),
            "--index-strategy",
            "unsafe-best-match",
        ],
        &venv,
    );
    let stderr = String::from_utf8_lossy(&out.stderr).to_string();
    println!("=== uv pip install into the stale venv ===\n{stderr}");
    assert!(
        !out.status.success(),
        "installing into a venv with a dead base unexpectedly succeeded"
    );
    assert!(
        stderr.contains(&old_python.to_string_lossy().to_string()),
        "uv failed for some other reason than the dead base:\n{stderr}"
    );

    // Recovery, exactly as provisioning performs it: drop the venv and rebuild
    // from the interpreter this installation ships.
    std::fs::remove_dir_all(&venv).expect("remove stale venv");
    let out = uv(
        &[
            "venv",
            &venv.to_string_lossy(),
            "--python",
            &bundled.to_string_lossy(),
            "--seed",
        ],
        &venv,
    );
    assert!(
        out.status.success(),
        "rebuild failed: {}",
        String::from_utf8_lossy(&out.stderr)
    );
    assert!(
        paths::venv_is_usable(&venv),
        "the rebuilt venv is still judged unusable"
    );

    let _ = std::fs::remove_dir_all(&work);
}
