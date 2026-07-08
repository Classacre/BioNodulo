use serde::Serialize;
use std::collections::BTreeMap;
use std::path::{Path, PathBuf};
use tauri::Url;

/// H6 — allow navigation only to a local wizard page (tauri:// or file://) or
/// the loopback backend origin. Everything else is denied.
pub fn is_allowed_navigation(target: &str, backend_origin: Option<&str>) -> bool {
    // Local app pages: the custom `tauri://` scheme (macOS/Linux) or `file://`.
    if target.starts_with("tauri://") || target.starts_with("file://") {
        return true;
    }
    match Url::parse(target) {
        Ok(u) => {
            // Windows/Android serve the bundled app from http(s)://tauri.localhost.
            if u.host_str() == Some("tauri.localhost") {
                return true;
            }
            match backend_origin {
                Some(origin) => origin_of(&u).as_deref() == Some(origin),
                None => false,
            }
        }
        Err(_) => false,
    }
}

fn origin_of(u: &Url) -> Option<String> {
    let scheme = u.scheme();
    let host = u.host_str()?;
    match u.port() {
        Some(p) => Some(format!("{scheme}://{host}:{p}")),
        None => Some(format!("{scheme}://{host}")),
    }
}

// M11 — deep-link validation
const ALLOWED_DEEP_LINK_HOSTS: [&str; 2] = ["open", "desktop-auth"];

#[derive(Serialize, Clone, Debug, PartialEq)]
pub struct DeepLinkPayload {
    pub host: String,
    pub path: String,
    pub params: BTreeMap<String, String>,
}

pub fn parse_deep_link(raw: &str) -> Option<DeepLinkPayload> {
    let url = Url::parse(raw).ok()?;
    if url.scheme() != "bionodulo" {
        return None;
    }
    let host = url.host_str()?.to_string();
    if !ALLOWED_DEEP_LINK_HOSTS.contains(&host.as_str()) {
        return None;
    }
    let mut params = BTreeMap::new();
    for (k, v) in url.query_pairs() {
        params.insert(k.into_owned(), v.into_owned());
    }
    Some(DeepLinkPayload {
        host,
        path: url.path().to_string(),
        params,
    })
}

// H5 — settings write allowlist
const RENDERER_WRITABLE_SETTINGS: [&str; 2] = ["updateChannel", "windowBounds"];

pub fn is_renderer_writable_setting(key: &str) -> bool {
    RENDERER_WRITABLE_SETTINGS.contains(&key)
}

// M12 — shell:open-path containment
pub fn is_path_within_roots(target: &str, roots: &[String]) -> bool {
    let resolved = normalize(Path::new(target));
    roots.iter().any(|root| {
        let r = normalize(Path::new(root));
        resolved == r || resolved.starts_with(&r)
    })
}

fn normalize(p: &Path) -> PathBuf {
    // Lexical resolution (no symlink touch); fold components manually so `..`
    // cannot escape a root prefix check.
    let mut out = PathBuf::new();
    for comp in p.components() {
        use std::path::Component::*;
        match comp {
            ParentDir => {
                out.pop();
            }
            CurDir => {}
            other => out.push(other.as_os_str()),
        }
    }
    out
}

// M10 note: the electron-updater feed-override env var was intentionally dropped
// in the Tauri v1 migration (the updater uses a static signed manifest), so the
// old feed-allowlist predicate was removed as dead code. Reintroduce a predicate
// here if a runtime feed override is ever added back.

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn nav_allows_local_and_loopback_only() {
        assert!(is_allowed_navigation("file:///x/first-run.html", None));
        assert!(is_allowed_navigation("tauri://localhost/loading.html", None));
        // Windows/Android app host must be allowed regardless of backend origin.
        assert!(is_allowed_navigation("http://tauri.localhost/error.html", None));
        // But a look-alike host must not slip through.
        assert!(!is_allowed_navigation("http://tauri.localhost.evil.com/", None));
        assert!(is_allowed_navigation(
            "http://127.0.0.1:8188/app",
            Some("http://127.0.0.1:8188")
        ));
        assert!(!is_allowed_navigation(
            "https://evil.example/login",
            Some("http://127.0.0.1:8188")
        ));
        assert!(!is_allowed_navigation(
            "http://127.0.0.1:9999/",
            Some("http://127.0.0.1:8188")
        ));
        assert!(!is_allowed_navigation("http://127.0.0.1:8188/", None));
    }

    #[test]
    fn deep_link_allowlist() {
        assert!(parse_deep_link("bionodulo://open?doi=10.1/x").is_some());
        assert!(parse_deep_link("bionodulo://desktop-auth?code=abc").is_some());
        assert!(parse_deep_link("bionodulo://evil?x=1").is_none());
        assert!(parse_deep_link("https://open/?x=1").is_none());
        assert!(parse_deep_link("not a url").is_none());
        let p = parse_deep_link("bionodulo://open?doi=10.1/x").unwrap();
        assert_eq!(p.host, "open");
        assert_eq!(p.params.get("doi").unwrap(), "10.1/x");
    }

    #[test]
    fn writable_settings_allowlist() {
        assert!(is_renderer_writable_setting("updateChannel"));
        assert!(is_renderer_writable_setting("windowBounds"));
        assert!(!is_renderer_writable_setting("pythonPath"));
        assert!(!is_renderer_writable_setting("venvPath"));
        assert!(!is_renderer_writable_setting("firstRun"));
    }

    #[test]
    fn path_containment_rejects_sibling_and_escape() {
        let roots = vec!["/a/workspace".to_string()];
        assert!(is_path_within_roots("/a/workspace", &roots));
        assert!(is_path_within_roots("/a/workspace/sub/f.txt", &roots));
        assert!(!is_path_within_roots("/a/workspace-evil/f.txt", &roots));
        assert!(!is_path_within_roots("/a/workspace/../secret", &roots));
        assert!(!is_path_within_roots("/etc/passwd", &roots));
    }

}
