mod commands;
mod deeplink;
mod paths;
mod port;
mod provision;
mod security;
mod settings;
mod supervisor;

use once_cell::sync::Lazy;
use std::sync::Mutex;
use tauri::{Manager, RunEvent, WebviewUrl, WebviewWindowBuilder};

use supervisor::Supervisor;

/// Origin of the running backend, set once the backend URL is known. Read by the
/// window `on_navigation` guard so the loopback origin is allowed while all other
/// origins are blocked (H6 navigation lockdown).
static BACKEND_ORIGIN: Lazy<Mutex<Option<String>>> = Lazy::new(|| Mutex::new(None));

/// Deep link captured before the window/backend existed; flushed once ready.
static PENDING_DEEP_LINK: Lazy<Mutex<Option<String>>> = Lazy::new(|| Mutex::new(None));

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    // WebKitGTK white-screen workaround (Linux only). WebKitGTK's hardware
    // (DMABUF) rendering path paints nothing on many Intel/NVIDIA + Wayland
    // setups — the window chrome shows but the web content stays blank. This is
    // a WebKitGTK/driver bug (WebView2 on Windows and WKWebView on macOS are
    // unaffected), so we force the software-fallback renderer at process start,
    // before any GTK/WebKit initialization. Users can override by exporting the
    // vars themselves. See https://github.com/tauri-apps/tauri/issues/9304.
    #[cfg(target_os = "linux")]
    {
        if std::env::var_os("WEBKIT_DISABLE_DMABUF_RENDERER").is_none() {
            std::env::set_var("WEBKIT_DISABLE_DMABUF_RENDERER", "1");
        }
    }

    let mut builder = tauri::Builder::default();

    #[cfg(desktop)]
    {
        // single-instance MUST be registered before deep-link.
        builder = builder
            .plugin(tauri_plugin_single_instance::init(|app, argv, _cwd| {
                deeplink::on_second_instance(app, &argv);
            }))
            .plugin(tauri_plugin_deep_link::init())
            .plugin(tauri_plugin_updater::Builder::new().build());
    }

    builder
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_store::Builder::default().build())
        .plugin(tauri_plugin_window_state::Builder::default().build())
        .plugin(tauri_plugin_log::Builder::default().build())
        .manage(Supervisor::default())
        .invoke_handler(tauri::generate_handler![
            commands::get_version,
            commands::get_paths,
            commands::get_settings,
            commands::get_setting,
            commands::set_setting,
            commands::get_python_status,
            commands::get_python_logs,
            commands::get_server_url,
            commands::restart_python,
            commands::update_dependencies,
            commands::run_setup,
            commands::complete_setup,
            commands::select_directory,
            commands::open_external,
            commands::open_path,
            commands::show_logs
        ])
        .setup(|app| {
            let handle = app.handle().clone();

            #[cfg(desktop)]
            deeplink::setup_runtime_deep_link(&handle);

            // Capture a deep link passed at cold start (Windows/Linux).
            if let Some(link) = std::env::args().find(|a| a.starts_with("bionodulo://")) {
                stash_pending_deep_link(link);
            }

            // Build the main window on the main thread. First run → wizard;
            // otherwise the loading page while the backend starts.
            let needs_setup = settings::get_first_run(&handle)
                || !paths::venv_exists(&paths::venv_path(&handle));
            let initial = if needs_setup {
                WebviewUrl::App("first-run.html".into())
            } else {
                WebviewUrl::App("loading.html".into())
            };

            WebviewWindowBuilder::new(app, "main", initial)
                .title("BioNodulo")
                .inner_size(1400.0, 900.0)
                .min_inner_size(1024.0, 768.0)
                .on_navigation(|u| {
                    security::is_allowed_navigation(u.as_str(), backend_origin_opt().as_deref())
                })
                .build()?;

            if !needs_setup {
                let h2 = handle.clone();
                tauri::async_runtime::spawn(async move {
                    start_backend_and_load(&h2).await;
                });
            }
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app, event| {
            if let RunEvent::ExitRequested { api, .. } = event {
                // Drain the backend before the process exits.
                api.prevent_exit();
                let handle = app.clone();
                tauri::async_runtime::spawn(async move {
                    let sup = handle.state::<Supervisor>();
                    let _ = sup.stop().await;
                    handle.exit(0);
                });
            }
        });
}

/// Start the backend, point the main window at its loopback UI, and flush any
/// pending deep link. On failure, navigate to the local error page.
pub async fn start_backend_and_load(app: &tauri::AppHandle) {
    let sup = app.state::<Supervisor>();
    match sup.start(app).await {
        Ok(()) => {
            let url = sup.server_url();
            set_backend_origin(&url);
            navigate_main(app, &url);
            flush_pending_deep_link(app);
        }
        Err(e) => {
            // Navigate to the error page via a same-origin relative replace so it
            // works regardless of the platform's app host (tauri://localhost vs
            // http://tauri.localhost on Windows).
            let enc = urlencoding_min(&e);
            let app2 = app.clone();
            let _ = app.run_on_main_thread(move || {
                if let Some(win) = app2.get_webview_window("main") {
                    let _ = win.eval(&format!(
                        "window.location.replace('error.html?message={enc}')"
                    ));
                }
            });
        }
    }
}

/// Navigate the main window on the main thread (Tauri window ops want it there).
fn navigate_main(app: &tauri::AppHandle, url: &str) {
    let app2 = app.clone();
    let url_owned = url.to_string();
    let _ = app.run_on_main_thread(move || {
        if let Some(win) = app2.get_webview_window("main") {
            if let Ok(parsed) = url_owned.parse::<tauri::Url>() {
                let _ = win.navigate(parsed);
            }
        }
    });
}

fn set_backend_origin(url: &str) {
    if let Ok(u) = tauri::Url::parse(url) {
        let origin = match u.port() {
            Some(p) => format!("{}://{}:{}", u.scheme(), u.host_str().unwrap_or(""), p),
            None => format!("{}://{}", u.scheme(), u.host_str().unwrap_or("")),
        };
        *BACKEND_ORIGIN.lock().unwrap() = Some(origin);
    }
}

fn backend_origin_opt() -> Option<String> {
    BACKEND_ORIGIN.lock().unwrap().clone()
}

pub fn stash_pending_deep_link(raw: String) {
    *PENDING_DEEP_LINK.lock().unwrap() = Some(raw);
}

fn flush_pending_deep_link(app: &tauri::AppHandle) {
    let pending = PENDING_DEEP_LINK.lock().unwrap().take();
    if let Some(raw) = pending {
        deeplink::dispatch(app, &raw);
    }
}

/// Minimal percent-encoder for the error message query parameter.
fn urlencoding_min(s: &str) -> String {
    s.chars()
        .map(|c| match c {
            'A'..='Z' | 'a'..='z' | '0'..='9' | '-' | '_' | '.' | '~' => c.to_string(),
            ' ' => "%20".into(),
            other => format!("%{:02X}", other as u32),
        })
        .collect()
}
