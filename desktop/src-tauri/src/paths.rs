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
/// Third attempt, and the first that does not infer this from a path.
///
/// Checking that the recorded interpreter *exists* was not enough either: a
/// user on the build that did exactly that hit the same failure again, with
/// `%LOCALAPPDATA%\BioNodulo\python-embedded` still present as a directory and
/// only `python.exe` removed from it. Something in that `pyvenv.cfg` satisfied
/// the check while uv read a different value out of the same file -- which is
/// possible because `pyvenv.cfg` records the interpreter more than once
/// (`home`, `base-executable`, `executable`) and nothing keeps them agreeing.
///
/// So stop asking whether a recorded path exists and ask the question that
/// actually matters: was this venv built by the interpreter THIS installation
/// ships? Every interpreter the file names has to resolve to that one. A venv
/// that names anything else belongs to an installation that is gone, whether or
/// not some of its files happen to still be on disk.
pub fn venv_is_usable(app: &AppHandle, venv: &Path) -> bool {
    let bundled = embedded_python_exe(&embedded_python_dir(app));
    venv_is_usable_against(venv, &bundled)
}

/// The decision itself, separated from the app handle so it can be tested.
pub fn venv_is_usable_against(venv: &Path, bundled: &Path) -> bool {
    let python = venv_python(venv);
    if !python.exists() {
        return false;
    }
    if !venv_was_built_by(venv, bundled) {
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

/// Whether every interpreter this venv records is the one `bundled` names.
///
/// All of them, not the first that parses: the whole point is that the keys can
/// disagree, and uv is free to consult whichever it likes.
///
/// Two deliberate leniencies, both to avoid rebuilding a working environment on
/// every launch -- which costs minutes and is how an over-eager check gets
/// reverted. A venv recording nothing is accepted, because absent metadata is
/// not evidence of a wrong base. And if the bundled interpreter itself cannot
/// be resolved -- running unbundled, or a broken install -- there is nothing to
/// compare against, so fall back to requiring only that the recorded ones exist.
pub fn venv_was_built_by(venv: &Path, bundled: &Path) -> bool {
    let recorded = recorded_interpreters(venv);
    if recorded.is_empty() {
        return true;
    }
    let Ok(bundled) = bundled.canonicalize() else {
        return recorded.iter().all(|p| p.exists());
    };
    recorded
        .iter()
        .all(|p| matches!(p.canonicalize(), Ok(p) if same_path(&p, &bundled)))
}

/// Compare two already-canonical paths.
///
/// Canonicalising first is what makes this safe: it resolves 8.3 short names
/// (`RUNNER~1`), symlinks and `.` segments, and on Windows returns the same
/// verbatim `\\?\` form for both sides, so an extended-length path and a plain
/// one compare equal. Windows paths are then compared case-insensitively
/// because the filesystem is.
fn same_path(a: &Path, b: &Path) -> bool {
    if cfg!(target_os = "windows") {
        a.as_os_str()
            .to_string_lossy()
            .eq_ignore_ascii_case(&b.as_os_str().to_string_lossy())
    } else {
        a == b
    }
}

/// Every interpreter `pyvenv.cfg` names, in the keys that can name one.
///
/// `base-executable` and `executable` are full paths; `home` is the directory
/// holding the interpreter. uv 0.5.11 writes only `home`, CPython's `venv`
/// writes `home` and `executable`, and other tools write `base-executable` --
/// so which key is authoritative depends on who built the venv, and the reader
/// is not always the writer.
pub fn recorded_interpreters(venv: &Path) -> Vec<PathBuf> {
    let Ok(cfg) = std::fs::read_to_string(venv.join("pyvenv.cfg")) else {
        return Vec::new();
    };

    let value_of = |key: &str| -> Option<String> {
        cfg.lines().find_map(|line| {
            // Split on the FIRST `=` only: a Windows path contains no `=`, but
            // "C:\Program Files\..." must survive intact.
            let (k, v) = line.split_once('=')?;
            (k.trim() == key).then(|| v.trim().to_string())
        })
        .filter(|v| !v.is_empty())
    };

    let exe_name = if cfg!(target_os = "windows") {
        "python.exe"
    } else {
        "python"
    };

    let mut found: Vec<PathBuf> = Vec::new();
    for key in ["base-executable", "executable"] {
        if let Some(path) = value_of(key) {
            found.push(PathBuf::from(path));
        }
    }
    if let Some(home) = value_of("home") {
        found.push(PathBuf::from(home).join(exe_name));
    }
    found
}

/// The first interpreter `pyvenv.cfg` names, for reporting.
///
/// Deliberately not used to decide anything. "The first one that parses" is
/// what let a venv whose keys disagreed pass as healthy; decisions go through
/// [`venv_was_built_by`], which considers all of them.
pub fn recorded_base_interpreter(venv: &Path) -> Option<PathBuf> {
    recorded_interpreters(venv).into_iter().next()
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
        fn collects_every_key_that_can_name_an_interpreter() {
            // Because they can disagree, and uv reads whichever it likes.
            let venv = tmp("all-keys");
            write_cfg(
                &venv,
                "home = /a\nbase-executable = /b/python\nexecutable = /c/python\n",
            );

            let found = recorded_interpreters(&venv);
            assert_eq!(found.len(), 3, "{found:?}");
            assert!(found.contains(&PathBuf::from("/b/python")), "{found:?}");
            assert!(found.contains(&PathBuf::from("/c/python")), "{found:?}");
        }
    }

    /// Whether the venv belongs to THIS installation.
    ///
    /// Checking that the recorded interpreter merely *exists* shipped, and the
    /// same failure came back from a machine where
    /// `%LOCALAPPDATA%\BioNodulo\python-embedded` was still a directory with
    /// `python.exe` removed. Existence was never the property that mattered:
    /// a venv built by an installation that is gone is stale even if some of
    /// its files linger, and healthy only if it names the interpreter shipped
    /// alongside the code doing the asking.
    mod built_by_this_installation {
        use super::*;

        fn tmp(name: &str) -> PathBuf {
            let dir = std::env::temp_dir().join(format!("bn-venv-owner-{name}"));
            let _ = std::fs::remove_dir_all(&dir);
            std::fs::create_dir_all(&dir).unwrap();
            dir
        }

        /// A real file, so `canonicalize` has something to resolve.
        fn interpreter(dir: &Path, name: &str) -> PathBuf {
            let path = dir.join(name);
            std::fs::write(&path, b"").unwrap();
            path
        }

        fn write_cfg(dir: &Path, body: &str) {
            std::fs::write(dir.join("pyvenv.cfg"), body).unwrap();
        }

        #[test]
        fn accepts_a_venv_built_from_the_bundled_interpreter() {
            let dir = tmp("match");
            let bundled = interpreter(&dir, "python-bundled");
            let venv = dir.join("venv");
            std::fs::create_dir_all(&venv).unwrap();
            write_cfg(
                &venv,
                &format!("base-executable = {}\n", bundled.to_string_lossy()),
            );

            assert!(venv_was_built_by(&venv, &bundled));
        }

        #[test]
        fn rejects_a_venv_built_from_a_different_interpreter_that_still_exists() {
            // The case every previous check missed: nothing is missing, the
            // venv simply is not ours.
            let dir = tmp("other");
            let bundled = interpreter(&dir, "python-bundled");
            let other = interpreter(&dir, "python-elsewhere");
            let venv = dir.join("venv");
            std::fs::create_dir_all(&venv).unwrap();
            write_cfg(
                &venv,
                &format!("base-executable = {}\n", other.to_string_lossy()),
            );

            assert!(!venv_was_built_by(&venv, &bundled));
        }

        #[test]
        fn rejects_a_venv_whose_keys_disagree() {
            // One key naming the right interpreter is not enough. This is the
            // shape that would let a stale venv through while uv reads the
            // other key and fails.
            let dir = tmp("disagree");
            let bundled = interpreter(&dir, "python-bundled");
            let stale = dir.join("gone").join("python.exe");
            let venv = dir.join("venv");
            std::fs::create_dir_all(&venv).unwrap();
            write_cfg(
                &venv,
                &format!(
                    "base-executable = {}\nhome = {}\n",
                    bundled.to_string_lossy(),
                    stale.parent().unwrap().to_string_lossy()
                ),
            );

            assert!(!venv_was_built_by(&venv, &bundled));
        }

        #[test]
        fn rejects_a_venv_whose_interpreter_is_gone() {
            // Still caught, now as a special case of "not ours".
            let dir = tmp("gone");
            let bundled = interpreter(&dir, "python-bundled");
            let venv = dir.join("venv");
            std::fs::create_dir_all(&venv).unwrap();
            write_cfg(&venv, "base-executable = /definitely/not/here/python\n");

            assert!(!venv_was_built_by(&venv, &bundled));
        }

        #[test]
        fn a_venv_recording_nothing_is_left_alone() {
            // Absent metadata is not evidence of a wrong base, and rebuilding a
            // working environment on every launch is worse than not checking.
            let dir = tmp("no-cfg");
            let bundled = interpreter(&dir, "python-bundled");
            let venv = dir.join("venv");
            std::fs::create_dir_all(&venv).unwrap();

            assert!(venv_was_built_by(&venv, &bundled));
        }

        #[test]
        fn falls_back_to_existence_when_there_is_no_bundled_interpreter() {
            // Running unbundled there is nothing to compare against, so keep
            // the weaker check rather than rebuilding on every launch.
            let dir = tmp("unbundled");
            let live = interpreter(&dir, "python-live");
            let absent = dir.join("nowhere").join("python");

            let ok = dir.join("venv-ok");
            std::fs::create_dir_all(&ok).unwrap();
            write_cfg(&ok, &format!("base-executable = {}\n", live.to_string_lossy()));

            let dead = dir.join("venv-dead");
            std::fs::create_dir_all(&dead).unwrap();
            write_cfg(
                &dead,
                &format!("base-executable = {}\n", absent.to_string_lossy()),
            );

            let missing_bundle = dir.join("no-such-python");
            assert!(venv_was_built_by(&ok, &missing_bundle));
            assert!(!venv_was_built_by(&dead, &missing_bundle));
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
