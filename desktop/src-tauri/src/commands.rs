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
    serde_json::json!({
        "userData": paths::data_root(&app),
        "workspace": paths::workspace_path(&app),
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
