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
}
