use serde_json::{json, Value};
use tauri::AppHandle;
use tauri_plugin_store::StoreExt;

use crate::security::is_renderer_writable_setting;

pub const STORE_FILE: &str = "bionodulo-settings.json";

fn defaults() -> Value {
    json!({
        "dataDirectory": "",
        "pythonPath": "",
        "venvPath": "",
        "firstRun": true,
        "updateChannel": "stable",
        "lastCheckForUpdates": "",
        "windowBounds": { "width": 1400, "height": 900 }
    })
}

fn with_defaults(app: &AppHandle, key: &str) -> Value {
    let store = app.store(STORE_FILE).expect("store");
    store
        .get(key)
        .unwrap_or_else(|| defaults().get(key).cloned().unwrap_or(Value::Null))
}

pub fn get_all(app: &AppHandle) -> Value {
    let store = app.store(STORE_FILE).expect("store");
    let mut merged = defaults();
    if let Value::Object(map) = &mut merged {
        for (k, v) in store.entries() {
            map.insert(k, v);
        }
    }
    merged
}

pub fn get(app: &AppHandle, key: &str) -> Value {
    with_defaults(app, key)
}

pub fn set_checked(app: &AppHandle, key: &str, value: Value) -> bool {
    if !is_renderer_writable_setting(key) {
        log::warn!("[settings] refused renderer write for disallowed key {key}");
        return false;
    }
    set_internal(app, key, value);
    true
}

pub fn set_internal(app: &AppHandle, key: &str, value: Value) {
    let store = app.store(STORE_FILE).expect("store");
    store.set(key, value);
    let _ = store.save();
}

pub fn get_first_run(app: &AppHandle) -> bool {
    match get(app, "firstRun") {
        Value::Bool(b) => b,
        Value::Null => true, // unset → treat as first run
        _ => false,
    }
}
