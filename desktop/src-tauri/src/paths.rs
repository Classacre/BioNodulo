use std::path::{Path, PathBuf};
use tauri::{AppHandle, Manager};

pub fn os_key() -> &'static str {
    if cfg!(target_os = "windows") {
        "windows"
    } else if cfg!(target_os = "macos") {
        "macos"
    } else {
        "linux"
    }
}

/// Interpreter inside the runtime venv (what actually runs the backend).
pub fn venv_python(venv: &Path) -> PathBuf {
    if cfg!(target_os = "windows") {
        venv.join("Scripts").join("python.exe")
    } else {
        venv.join("bin").join("python")
    }
}

/// Embedded/standalone interpreter used to *bootstrap* the venv via uv.
pub fn embedded_python_exe(dir: &Path) -> PathBuf {
    if cfg!(target_os = "windows") {
        return dir.join("python.exe");
    }
    let candidates = [
        dir.join("bin").join("python3"),
        dir.join("python3"),
        dir.join("bin").join("python3.12"),
        dir.join("bin").join("python3.11"),
    ];
    for c in &candidates {
        if c.exists() {
            return c.clone();
        }
    }
    candidates[0].clone()
}

pub fn venv_exists(venv: &Path) -> bool {
    venv_python(venv).exists()
}

/// Whether the venv's interpreter can actually start.
///
/// Existing is not enough. On Windows `Scripts/python.exe` is a launcher stub
/// that resolves its real interpreter from `home` in `pyvenv.cfg`; upgrading
/// the app replaces the bundled interpreter while the venv, which lives in the
/// user's data directory, survives untouched. The stub is then left pointing at
/// a path its own installation no longer owns and exits 103 with
/// "No Python at '<path>'" -- a backend that never starts, on every launch,
/// with no way for the user to recover short of deleting a folder they have no
/// reason to know about.
///
/// Starting is necessary but not sufficient. `pyvenv.cfg` also records the BASE
/// interpreter the venv was built from, and every dependency build isolates
/// into a temporary venv created from that one. An upgrade that moves the
/// bundled interpreter leaves a venv that starts perfectly and cannot build
/// anything:
///
///   Failed to create temporary virtualenv
///   Could not find a suitable Python executable for the virtual environment
///   based on the interpreter: …\AppData\Local\BioNodulo\python-embedded\python.exe
///
/// So the recorded base is checked too, and a venv naming one that is gone is
/// rebuilt rather than used.
pub fn venv_is_usable(venv: &Path) -> bool {
    let python = venv_python(venv);
    if !python.exists() {
        return false;
    }
    if !base_interpreter_present(venv) {
        return false;
    }
    let mut cmd = std::process::Command::new(&python);
    cmd.arg("--version");
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        cmd.creation_flags(0x0800_0000); // CREATE_NO_WINDOW
    }
    matches!(cmd.output(), Ok(out) if out.status.success())
}

/// The base interpreter a venv was created from, as recorded in `pyvenv.cfg`.
///
/// `base-executable` names the interpreter directly; `home` names its directory
/// and is the older key, and the one the Windows launcher stub reads.
pub fn recorded_base_interpreter(venv: &Path) -> Option<PathBuf> {
    let cfg = std::fs::read_to_string(venv.join("pyvenv.cfg")).ok()?;

    let value_of = |key: &str| -> Option<String> {
        cfg.lines().find_map(|line| {
            // Split on the FIRST `=` only: a Windows path contains no `=`, but
            // "C:\Program Files\..." must survive intact.
            let (k, v) = line.split_once('=')?;
            (k.trim() == key).then(|| v.trim().to_string())
        })
    };

    if let Some(exe) = value_of("base-executable").filter(|v| !v.is_empty()) {
        return Some(PathBuf::from(exe));
    }
    let home = value_of("home").filter(|v| !v.is_empty())?;
    Some(PathBuf::from(home).join(if cfg!(target_os = "windows") {
        "python.exe"
    } else {
        "python"
    }))
}

/// Whether the interpreter this venv was built from is still on disk.
///
/// A venv with no `pyvenv.cfg`, or one recording nothing, is treated as fine:
/// missing metadata is not evidence of a dead base, and needlessly rebuilding a
/// working environment costs the user minutes every launch.
pub fn base_interpreter_present(venv: &Path) -> bool {
    match recorded_base_interpreter(venv) {
        Some(base) => base.exists(),
        None => true,
    }
}

fn is_dev() -> bool {
    // tauri::is_dev() is compiled in for `tauri dev`; env override for staged tests.
    tauri::is_dev() || std::env::var("BIONODULO_DEV").as_deref() == Ok("1")
}

/// Dev assets tree (apps/desktop/assets), used when running unbundled.
fn dev_assets_root() -> PathBuf {
    // CARGO_MANIFEST_DIR = apps/desktop/src-tauri ; assets live one level up.
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("assets")
}

pub fn resources_root(app: &AppHandle) -> PathBuf {
    app.path().resource_dir().expect("resource_dir unavailable")
}

pub fn data_root(app: &AppHandle) -> PathBuf {
    app.path().app_data_dir().expect("app_data_dir unavailable")
}

pub fn backend_path(app: &AppHandle) -> PathBuf {
    if is_dev() {
        dev_assets_root().join("bionodulo-backend")
    } else {
        resources_root(app).join("bionodulo-backend")
    }
}

pub fn backend_entry_script(app: &AppHandle) -> PathBuf {
    backend_path(app).join("main.py")
}

pub fn embedded_python_dir(app: &AppHandle) -> PathBuf {
    if is_dev() {
        dev_assets_root().join("python-embedded").join(os_key())
    } else {
        resources_root(app).join("python-embedded")
    }
}

pub fn uv_exe(app: &AppHandle) -> PathBuf {
    let dir = if is_dev() {
        dev_assets_root().join("uv").join(os_key())
    } else {
        resources_root(app).join("uv")
    };
    dir.join(if cfg!(target_os = "windows") {
        "uv.exe"
    } else {
        "uv"
    })
}

fn cloudflared_bin_name() -> &'static str {
    if cfg!(target_os = "windows") {
        "cloudflared.exe"
    } else {
        "cloudflared"
    }
}

pub fn cloudflared_path(app: &AppHandle) -> PathBuf {
    let dir = if is_dev() {
        dev_assets_root().join("cloudflared").join(os_key())
    } else {
        resources_root(app).join("cloudflared")
    };
    dir.join(cloudflared_bin_name())
}

pub fn venv_path(app: &AppHandle) -> PathBuf {
    data_root(app).join("venv")
}

pub fn workspace_path(app: &AppHandle) -> PathBuf {
    data_root(app).join("workspace")
}

pub fn logs_path(app: &AppHandle) -> PathBuf {
    data_root(app).join("logs")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn os_key_is_known() {
        assert!(matches!(os_key(), "windows" | "macos" | "linux"));
    }

    /// A venv whose recorded base interpreter is gone is not usable, even
    /// though its own python starts.
    ///
    /// A user upgraded and hit:
    ///   Failed to build bionodulo @ file:///C:/Program%20Files/BioNodulo/...
    ///   ├─▶ Failed to create temporary virtualenv
    ///   ╰─▶ Could not find a suitable Python executable ... based on the
    ///       interpreter: C:\Users\...\AppData\Local\BioNodulo\python-embedded\python.exe
    ///
    /// The venv in the roaming data directory survived an upgrade that moved
    /// the bundled interpreter, so `pyvenv.cfg` still named the old location.
    /// The venv itself ran fine -- `python --version` succeeded, so the probe
    /// passed and it was never rebuilt -- but every build isolates into a
    /// temporary venv created FROM that base interpreter, and that path was
    /// gone. Starting is not the property that matters.
    mod base_interpreter {
        use super::*;

        fn tmp(name: &str) -> PathBuf {
            let dir = std::env::temp_dir().join(format!("bn-venv-test-{name}"));
            let _ = std::fs::remove_dir_all(&dir);
            std::fs::create_dir_all(&dir).unwrap();
            dir
        }

        fn write_cfg(dir: &Path, body: &str) {
            std::fs::write(dir.join("pyvenv.cfg"), body).unwrap();
        }

        #[test]
        fn reads_base_executable() {
            let venv = tmp("base-exec");
            write_cfg(&venv, "home = C:\\py\nbase-executable = C:\\py\\python.exe\n");

            assert_eq!(
                recorded_base_interpreter(&venv),
                Some(PathBuf::from("C:\\py\\python.exe"))
            );
        }

        #[test]
        fn falls_back_to_home_when_base_executable_is_absent() {
            // Not every tool writes base-executable; `home` is the older key,
            // and is what the Windows launcher stub itself reads.
            let venv = tmp("home-only");
            write_cfg(&venv, "home = /usr/local\nversion = 3.12.8\n");

            let found = recorded_base_interpreter(&venv).expect("no interpreter");
            assert!(found.starts_with("/usr/local"), "{found:?}");
        }

        #[test]
        fn tolerates_spacing_around_the_separator() {
            let venv = tmp("spacing");
            write_cfg(&venv, "base-executable=/opt/py/bin/python\n");

            assert_eq!(
                recorded_base_interpreter(&venv),
                Some(PathBuf::from("/opt/py/bin/python"))
            );
        }

        #[test]
        fn keeps_a_path_containing_spaces_intact() {
            // "Program Files" — split on the first `=` only.
            let venv = tmp("spaces");
            write_cfg(
                &venv,
                "base-executable = C:\\Program Files\\BioNodulo\\python.exe\n",
            );

            assert_eq!(
                recorded_base_interpreter(&venv),
                Some(PathBuf::from("C:\\Program Files\\BioNodulo\\python.exe"))
            );
        }

        #[test]
        fn reports_nothing_when_there_is_no_config() {
            let venv = tmp("no-cfg");

            assert_eq!(recorded_base_interpreter(&venv), None);
        }

        #[test]
        fn a_missing_base_interpreter_makes_the_venv_unusable() {
            // The reported failure, exactly: the venv is fine, its base is not.
            let venv = tmp("dead-base");
            write_cfg(
                &venv,
                "base-executable = /definitely/not/here/python\nversion = 3.12.8\n",
            );

            assert!(!base_interpreter_present(&venv));
        }

        #[test]
        fn a_present_base_interpreter_is_accepted() {
            let venv = tmp("live-base");
            let base = venv.join("fake-python");
            std::fs::write(&base, b"").unwrap();
            write_cfg(&venv, &format!("base-executable = {}\n", base.to_string_lossy()));

            assert!(base_interpreter_present(&venv));
        }

        #[test]
        fn no_config_is_not_treated_as_broken() {
            // Absent metadata is not evidence of a dead base, and rebuilding a
            // working environment on every launch is worse than not checking.
            let venv = tmp("cfg-absent");

            assert!(base_interpreter_present(&venv));
        }
    }

    #[test]
    fn venv_python_layout() {
        let venv = Path::new("/data/venv");
        let py = venv_python(venv);
        if cfg!(target_os = "windows") {
            assert!(py.ends_with("Scripts/python.exe") || py.ends_with("Scripts\\python.exe"));
        } else {
            assert_eq!(py, Path::new("/data/venv/bin/python"));
        }
    }

    #[test]
    fn embedded_python_exe_defaults_to_first_candidate() {
        let dir = Path::new("/nonexistent-embedded-dir");
        let exe = embedded_python_exe(dir);
        assert!(exe.starts_with(dir));
    }

    #[test]
    fn cloudflared_path_layout() {
        let name = cloudflared_bin_name();
        if cfg!(target_os = "windows") {
            assert_eq!(name, "cloudflared.exe");
        } else {
            assert_eq!(name, "cloudflared");
        }
    }
}
