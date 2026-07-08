use tauri::{AppHandle, Emitter, Manager};

use crate::security::parse_deep_link;
use crate::supervisor::{PythonStatus, Supervisor};

/// Validate in the trusted Rust layer, then emit the structured payload. The raw
/// attacker-controllable string never reaches the webview.
pub fn dispatch(app: &AppHandle, raw: &str) {
    match parse_deep_link(raw) {
        Some(payload) => {
            let _ = app.emit("app:deep-link", payload);
        }
        None => log::warn!("[deeplink] dropped unrecognized link: {raw}"),
    }
    focus_main(app);
}

/// Second-instance handler (Windows/Linux deliver deep links via argv).
pub fn on_second_instance(app: &AppHandle, argv: &[String]) {
    if let Some(link) = argv.iter().find(|a| a.starts_with("bionodulo://")) {
        handle(app, link);
    }
    focus_main(app);
}

/// Runtime handler for macOS `open-url` style delivery via the deep-link plugin.
#[cfg(desktop)]
pub fn setup_runtime_deep_link(app: &AppHandle) {
    use tauri_plugin_deep_link::DeepLinkExt;
    let handle = app.clone();
    app.deep_link().on_open_url(move |event| {
        for url in event.urls() {
            handle_owned(&handle, url.as_str());
        }
    });
}

fn handle(app: &AppHandle, raw: &str) {
    handle_owned(app, raw);
}

fn handle_owned(app: &AppHandle, raw: &str) {
    let running = app.state::<Supervisor>().status() == PythonStatus::Running;
    if running && app.get_webview_window("main").is_some() {
        dispatch(app, raw);
    } else {
        // Stash for flush after the backend is ready.
        crate::stash_pending_deep_link(raw.to_string());
    }
}

fn focus_main(app: &AppHandle) {
    if let Some(win) = app.get_webview_window("main") {
        let _ = win.unminimize();
        let _ = win.set_focus();
    }
}
