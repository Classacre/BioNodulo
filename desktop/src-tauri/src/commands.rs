use serde_json::Value;
use tauri::{AppHandle, Manager, State};
use tauri_plugin_dialog::DialogExt;
use tauri_plugin_opener::OpenerExt;

use crate::supervisor::Supervisor;
use crate::{paths, provision, security, settings};

#[tauri::command]
pub fn get_version(app: AppHandle) -> String {
    app.package_info().version.to_string()
}

#[tauri::command]
pub fn get_paths(app: AppHandle) -> Value {
    // Under WSL the workspace lives on ext4 inside the distribution, so the
    // Windows-visible path is a \\wsl.localhost share rather than a drive
    // path. Without this the user has no way to open their own results.
    let workspace: Value = if crate::wsl_mode_enabled(&app) {
        Value::String(crate::wsl::windows_share_path(&crate::wsl::linux_workspace()))
    } else {
        serde_json::json!(paths::workspace_path(&app))
    };
    serde_json::json!({
        "userData": paths::data_root(&app),
        "workspace": workspace,
        "venv": paths::venv_path(&app),
        "logs": paths::logs_path(&app),
        "temp": std::env::temp_dir(),
        "downloads": app.path().download_dir().ok(),
    })
}

#[tauri::command]
pub fn get_settings(app: AppHandle) -> Value {
    settings::get_all(&app)
}

#[tauri::command]
pub fn get_setting(app: AppHandle, key: String) -> Value {
    settings::get(&app, &key)
}

#[tauri::command]
pub fn set_setting(app: AppHandle, key: String, value: Value) -> bool {
    settings::set_checked(&app, &key, value)
}

#[tauri::command]
pub fn get_python_status(sup: State<'_, Supervisor>) -> String {
    sup.status().as_str().to_string()
}

#[tauri::command]
pub fn get_python_logs(sup: State<'_, Supervisor>) -> Vec<String> {
    sup.logs()
}

#[tauri::command]
pub fn get_server_url(sup: State<'_, Supervisor>) -> String {
    sup.server_url()
}

#[tauri::command]
pub async fn restart_python(
    app: AppHandle,
    sup: State<'_, Supervisor>,
) -> Result<String, String> {
    sup.restart(&app).await
}

#[tauri::command]
pub async fn update_dependencies(app: AppHandle) -> Result<Value, String> {
    provision::update_dependencies(&app).await?;
    Ok(serde_json::json!({ "success": true }))
}

#[tauri::command]
pub async fn run_setup(app: AppHandle) -> Result<Value, String> {
    provision::setup(&app).await?;
    Ok(serde_json::json!({ "success": true }))
}

#[tauri::command]
pub async fn complete_setup(app: AppHandle) -> Result<Value, String> {
    settings::set_internal(&app, "firstRun", Value::Bool(false));
    settings::set_internal(
        &app,
        "venvPath",
        Value::String(paths::venv_path(&app).to_string_lossy().into_owned()),
    );
    crate::start_backend_and_load(&app).await;
    Ok(serde_json::json!({ "success": true }))
}

#[tauri::command]
pub async fn select_directory(app: AppHandle) -> Option<String> {
    let folder = app.dialog().file().blocking_pick_folder();
    folder.map(|p| p.to_string())
}

#[tauri::command]
pub fn open_external(app: AppHandle, url: String) -> bool {
    let lower = url.to_ascii_lowercase();
    if lower.starts_with("https:")
        || lower.starts_with("http:")
        || lower.starts_with("mailto:")
        || lower.starts_with("bionodulo:")
    {
        let _ = app.opener().open_url(url, None::<&str>);
        true
    } else {
        log::warn!("[ipc] refused open_external for {url}");
        false
    }
}

#[tauri::command]
pub fn open_path(app: AppHandle, path: String) -> String {
    let roots = [paths::workspace_path(&app), paths::logs_path(&app)]
        .into_iter()
        .chain(app.path().download_dir().ok())
        .map(|p| p.to_string_lossy().into_owned())
        .collect::<Vec<_>>();
    if !security::is_path_within_roots(&path, &roots) {
        log::warn!("[ipc] refused open_path outside safe roots: {path}");
        return "refused: path is outside the allowed directories".into();
    }
    match app.opener().open_path(path, None::<&str>) {
        Ok(()) => String::new(),
        Err(e) => e.to_string(),
    }
}

#[tauri::command]
pub fn show_logs(app: AppHandle) -> String {
    let logs = paths::logs_path(&app).to_string_lossy().into_owned();
    match app.opener().open_path(logs, None::<&str>) {
        Ok(()) => String::new(),
        Err(e) => e.to_string(),
    }
}

/// Report whether local workflow execution can run on this machine.
///
/// Only Windows needs the WSL2 path: bioconda publishes no win-64 packages, so
/// nothing can be installed natively there. Every other platform already is
/// the target platform and is always ready.
#[tauri::command]
pub async fn get_local_execution_status(app: AppHandle) -> Value {
    let enabled = matches!(settings::get(&app, "localExecution"), Value::Bool(true));

    if !cfg!(windows) {
        return serde_json::json!({
            "supported": true,
            "requiresWsl": false,
            "enabled": enabled,
            "state": "ready",
            "message": "Local execution runs natively on this platform.",
            "userFixable": true,
        });
    }

    let readiness = crate::wsl::runtime::readiness().await;
    serde_json::json!({
        "supported": true,
        "requiresWsl": true,
        "enabled": enabled,
        "state": readiness.state_key(),
        "message": readiness.message(),
        "userFixable": readiness.user_fixable(),
    })
}

/// Provision the private WSL2 distribution and install the engine into it.
#[tauri::command]
pub async fn setup_local_execution(app: AppHandle) -> Result<(), String> {
    if !cfg!(windows) {
        return Err("Local execution needs no setup on this platform.".into());
    }
    let data = paths::data_root(&app);
    let backend = paths::backend_path(&app);

    let notify = |app: &AppHandle, message: &str| {
        let _ = tauri::Emitter::emit(
            app,
            "setup:progress",
            provision::SetupProgress {
                phase: "wsl".into(),
                message: message.into(),
                fraction: None,
            },
        );
    };

    let handle = app.clone();
    crate::wsl::runtime::provision(&data, |m| notify(&handle, m)).await?;
    let handle = app.clone();
    crate::wsl::runtime::install_backend(&backend, |m| notify(&handle, m)).await?;

    // Only recorded once both steps succeeded: a half-provisioned distribution
    // that the app believes is ready fails every run instead of offering setup.
    settings::set_internal(&app, "localExecution", Value::Bool(true));
    Ok(())
}

/// Remove the private distribution so setup can be retried from scratch.
#[tauri::command]
pub async fn reset_local_execution(app: AppHandle) -> Result<(), String> {
    settings::set_internal(&app, "localExecution", Value::Bool(false));
    if !cfg!(windows) {
        return Ok(());
    }
    crate::wsl::runtime::unregister().await
}
