//! Local workflow execution on Windows, via a private WSL2 distribution.
//!
//! Windows cannot run these workflows natively: every tool comes from bioconda,
//! which publishes no win-64 packages. WSL2 gives a real linux-64 userland on
//! the same machine, and the committed environment locks apply unchanged.
//!
//! Four constraints from the platform shape everything here:
//!
//! * **Enabling WSL needs administrator once.** `VirtualMachinePlatform` is a
//!   machine-wide optional component. There is no supported way around it, so
//!   the app detects the situation and hands the user an exact command rather
//!   than pretending it can self-install.
//! * **`wsl --import` does not need elevation** and does not touch the Store,
//!   so once WSL exists we provision a private distro without admin rights and
//!   without group policy blocking us.
//! * **`/mnt/c` is roughly ten times slower** than ext4 (9P, uncached, a host
//!   round trip per stat). The workspace therefore lives inside the distro and
//!   is reached from Windows through `\\wsl.localhost`, not the other way
//!   round.
//! * **localhost forwarding is not a stable contract.** It breaks after
//!   sleep/wake, under VPN filter drivers, and historically on low ports. The
//!   backend binds 0.0.0.0 on a high port and the caller is given both
//!   candidate URLs to try, loopback first.

use std::path::{Path, PathBuf};

/// Name of the private distribution. Deliberately not a user's own distro: we
/// install a pinned userland and must never mutate something they rely on.
pub const DISTRO: &str = "BioNodulo";

/// Ports at or below this have a documented history of not being forwarded to
/// the Windows host (microsoft/WSL#5942). Stay well clear.
pub const MIN_FORWARDED_PORT: u16 = 8300;

/// Enforced at compile time so lowering the constant into the range that is
/// known not to forward fails the build rather than a user's first run.
const _: () = assert!(MIN_FORWARDED_PORT > 3088);

/// Where the distro keeps its own state, inside ext4 rather than on /mnt/c.
pub const LINUX_HOME: &str = "/opt/bionodulo";

/// Why local execution is unavailable, and what the user can do about it.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum WslReadiness {
    /// Provisioned and usable.
    Ready,
    /// WSL itself is missing; enabling it requires an elevated command.
    NotInstalled,
    /// The installer enabled WSL, but Windows has not restarted yet.
    RebootRequired,
    /// WSL exists but our distribution has not been imported yet.
    DistroMissing,
    /// WSL is present but reports version 1, which cannot run our userland.
    Version1Only,
}

impl WslReadiness {
    /// Message shown to the user, in their terms, with the next action.
    pub fn message(&self) -> String {
        match self {
            Self::Ready => "Local execution is ready.".into(),
            Self::NotInstalled => "Windows cannot run these tools directly, so local \
                 execution uses WSL2. Enabling it is a one-time step that needs \
                 administrator rights: open PowerShell as administrator, run \
                 `wsl --install --no-distribution`, then restart Windows. Running on the \
                 cloud needs no setup at all."
                .into(),
            Self::RebootRequired => "BioNodulo enabled WSL2 during installation, but \
                 Windows needs to restart before workflows can run on this PC. Until then \
                 they will run on the cloud."
                .into(),
            Self::DistroMissing => format!(
                "WSL2 is enabled but the {DISTRO} environment has not been set up yet. \
                 This downloads a small Linux userland and needs no administrator rights."
            ),
            Self::Version1Only => "WSL is installed but running version 1, which cannot run \
                 these tools. Run `wsl --set-default-version 2` and set up local execution again."
                .into(),
        }
    }

    /// Stable identifier for the UI to branch on.
    pub fn state_key(&self) -> &'static str {
        match self {
            Self::Ready => "ready",
            Self::NotInstalled => "wsl-missing",
            Self::RebootRequired => "reboot-required",
            Self::DistroMissing => "distro-missing",
            Self::Version1Only => "wsl-v1",
        }
    }

    /// Whether the user can resolve this without an administrator.
    pub fn user_fixable(&self) -> bool {
        // A pending restart is the user's to perform, but not from inside this
        // wizard, so it is grouped with the states we cannot resolve here.
        matches!(self, Self::DistroMissing | Self::Version1Only)
    }
}

/// Translate a Windows path to its WSL equivalent.
///
/// Implemented directly rather than by shelling out to `wslpath` because this
/// runs on every path crossing the boundary and a process spawn per path is
/// visible. UNC paths have no `/mnt` form and are returned as an error so the
/// caller can fall back to `wslpath` or refuse the file.
pub fn to_wsl_path(path: &Path) -> Result<String, String> {
    let mut raw = path.to_string_lossy().replace('\\', "/");

    // Windows hands out extended-length paths (\\?\C:\...) from canonicalize
    // and several shell APIs. Those denote an ordinary drive path, so strip the
    // prefix rather than mistaking the leading slashes for a network share.
    if let Some(rest) = raw.strip_prefix("//?/") {
        raw = match rest.strip_prefix("UNC/") {
            // \\?\UNC\server\share is genuinely a network path.
            Some(share) => format!("//{share}"),
            None => rest.to_string(),
        };
    }

    if raw.starts_with("//") {
        return Err(format!(
            "Network paths like \"{raw}\" are not reachable from the local Linux environment. \
             Copy the file to a local drive first."
        ));
    }

    let bytes = raw.as_bytes();
    let is_drive = bytes.len() >= 2
        && bytes[0].is_ascii_alphabetic()
        && bytes[1] == b':'
        && (bytes.len() == 2 || bytes[2] == b'/');
    if !is_drive {
        // Already a POSIX path (or a relative one); pass through untouched.
        return Ok(raw);
    }

    let drive = (bytes[0] as char).to_ascii_lowercase();
    let rest = raw[2..].trim_start_matches('/');
    if rest.is_empty() {
        Ok(format!("/mnt/{drive}"))
    } else {
        Ok(format!("/mnt/{drive}/{rest}"))
    }
}

/// Windows-visible path for a location inside the distribution.
///
/// Files under this share are on ext4, so tools inside WSL read them at full
/// speed while Explorer and file dialogs can still open them.
pub fn windows_share_path(linux_path: &str) -> String {
    let trimmed = linux_path.trim_start_matches('/').replace('/', "\\");
    format!("\\\\wsl.localhost\\{DISTRO}\\{trimmed}")
}

/// Arguments for running a command inside the distribution.
///
/// `--cd` sets the working directory inside Linux; without it wsl.exe inherits
/// the Windows working directory and lands the process in `/mnt/c/...`, which
/// is both slow and surprising.
pub fn exec_args(working_dir: &str, program: &str, program_args: &[String]) -> Vec<String> {
    let mut args = vec![
        "--distribution".to_string(),
        DISTRO.to_string(),
        "--cd".to_string(),
        working_dir.to_string(),
        "--exec".to_string(),
        program.to_string(),
    ];
    args.extend(program_args.iter().cloned());
    args
}

/// Full wsl.exe argument list for launching the backend inside the distro.
///
/// Two things make this more than `exec_args` plus a script name, and getting
/// either wrong kills the backend instantly with nothing in the logs:
///
/// * every path must already be a Linux path. A Windows path handed to the
///   Linux interpreter simply does not exist.
/// * environment variables set on the wsl.exe process do **not** reach the
///   Linux process -- WSL forwards only what WSLENV names. The environment is
///   therefore passed explicitly by running the interpreter under `env`.
pub fn backend_argv(
    working_dir: &str,
    python: &str,
    script: &str,
    app_args: &[String],
    envs: &[(String, String)],
) -> Vec<String> {
    let mut args = vec![
        "--distribution".to_string(),
        DISTRO.to_string(),
        "--cd".to_string(),
        working_dir.to_string(),
        "--exec".to_string(),
        // /usr/bin/env, not a shell: argv is passed through untouched, so a
        // value containing spaces needs no quoting and cannot be re-split.
        "env".to_string(),
    ];
    for (key, value) in envs {
        args.push(format!("{key}={value}"));
    }
    args.push(python.to_string());
    args.push(script.to_string());
    args.extend(app_args.iter().cloned());
    args
}

/// Arguments that import the distribution from a rootfs tarball.
pub fn import_args(install_dir: &Path, tarball: &Path) -> Vec<String> {
    vec![
        "--import".to_string(),
        DISTRO.to_string(),
        install_dir.to_string_lossy().into_owned(),
        tarball.to_string_lossy().into_owned(),
        "--version".to_string(),
        "2".to_string(),
    ]
}

/// Parse `wsl --list --quiet` output into distribution names.
///
/// wsl.exe writes UTF-16LE, so callers decode before calling this. Output also
/// carries stray NUL and BOM bytes that survive a lossy decode.
pub fn parse_distro_list(output: &str) -> Vec<String> {
    output
        .lines()
        .map(|line| line.trim().trim_matches('\u{0}').trim_matches('\u{feff}').trim())
        .filter(|line| !line.is_empty())
        .map(|line| line.trim_end_matches("(Default)").trim().to_string())
        .collect()
}

/// Decode wsl.exe output, which is UTF-16LE on every supported Windows build.
pub fn decode_wsl_output(bytes: &[u8]) -> String {
    // A lone odd byte means this is not UTF-16; fall back rather than lose it.
    if bytes.len() % 2 != 0 {
        return String::from_utf8_lossy(bytes).into_owned();
    }
    let units: Vec<u16> = bytes
        .chunks_exact(2)
        .map(|pair| u16::from_le_bytes([pair[0], pair[1]]))
        .collect();
    match String::from_utf16(&units) {
        Ok(text) => text,
        Err(_) => String::from_utf8_lossy(bytes).into_owned(),
    }
}

/// Extract the distribution's IP from `hostname -I`.
///
/// Used only as a fallback: loopback forwarding is preferred because the VM
/// address changes across restarts.
pub fn parse_vm_ip(output: &str) -> Option<String> {
    output
        .split_whitespace()
        .find(|token| token.contains('.') && token.parse::<std::net::Ipv4Addr>().is_ok())
        .map(str::to_string)
}

/// Candidate base URLs for the backend, in the order they should be tried.
///
/// Loopback first because it survives VM restarts; the mirrored address second
/// because loopback forwarding is the part that breaks under VPNs and after
/// sleep/wake.
pub fn candidate_urls(port: u16, vm_ip: Option<&str>) -> Vec<String> {
    let mut urls = vec![format!("http://127.0.0.1:{port}")];
    if let Some(ip) = vm_ip {
        urls.push(format!("http://{ip}:{port}"));
    }
    urls
}

/// Path inside the distribution for a workspace directory.
pub fn linux_workspace() -> String {
    format!("{LINUX_HOME}/workspace")
}

/// Virtualenv inside the distribution. On ext4, never under /mnt.
pub fn venv_path() -> String {
    format!("{LINUX_HOME}/venv")
}

/// The Linux interpreter that runs the backend.
pub fn linux_python() -> String {
    format!("{}/bin/python", venv_path())
}

/// Quote a path for `sh -lc`.
///
/// Windows paths reach here translated, and a user directory containing a
/// space or an apostrophe would otherwise split the command.
pub fn shell_quote(value: &str) -> String {
    format!("'{}'", value.replace('\'', r"'\''"))
}

/// Local filesystem location for the imported distribution's disk image.
pub fn install_dir(app_data: &Path) -> PathBuf {
    app_data.join("wsl").join(DISTRO)
}

/// Runtime probing and provisioning.
///
/// Compiled on every platform even though wsl.exe only exists on Windows, so
/// that this logic is type-checked and reviewable from a Linux or macOS
/// checkout. Callers are gated by `wsl_mode_enabled`, which is false off
/// Windows; if one ever slips through, spawning wsl.exe simply fails and is
/// reported as "not available".
pub mod runtime {
    use super::*;
    use std::process::Stdio;
    use std::time::Duration;
    use tokio::process::Command;

    /// Where the rootfs is fetched from when local execution is first set up.
    /// A minimal userland only: pixi and the environment locks provide the
    /// tools, exactly as they do on Linux and macOS.
    /// Note the `releases/` segment: the sibling `wsl/noble/current/` path
    /// publishes only manifests, and 404s for the tarball. That mistake made
    /// provisioning impossible on every machine until CI ran it.
    const ROOTFS_URL: &str = "https://cloud-images.ubuntu.com/wsl/releases/noble/current/\
ubuntu-noble-wsl-amd64-wsl.rootfs.tar.gz";

    const PROBE_TIMEOUT: Duration = Duration::from_secs(20);
    const IMPORT_TIMEOUT: Duration = Duration::from_secs(600);
    /// apt plus a pip install of the engine; slow on a cold machine.
    const SETUP_TIMEOUT: Duration = Duration::from_secs(1800);

    fn wsl_command() -> Command {
        // Mutated only on Windows, where creation_flags suppresses the console
        // window that would otherwise flash on every probe.
        #[allow(unused_mut)]
        let mut cmd = Command::new("wsl.exe");
        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            cmd.creation_flags(0x0800_0000); // CREATE_NO_WINDOW
        }
        cmd
    }

    async fn run(args: &[String], timeout: Duration) -> Result<(bool, String), String> {
        let mut cmd = wsl_command();
        cmd.args(args).stdout(Stdio::piped()).stderr(Stdio::piped());
        let child = cmd.spawn().map_err(|e| format!("wsl.exe not available: {e}"))?;
        let out = tokio::time::timeout(timeout, child.wait_with_output())
            .await
            .map_err(|_| format!("wsl.exe timed out after {}s", timeout.as_secs()))?
            .map_err(|e| e.to_string())?;
        let mut text = decode_wsl_output(&out.stdout);
        text.push_str(&decode_wsl_output(&out.stderr));
        Ok((out.status.success(), text))
    }

    /// Determine what, if anything, blocks local execution.
    pub async fn readiness() -> WslReadiness {
        // `--status` fails outright when the optional component is absent,
        // which is the only case needing administrator rights.
        let Ok((ok, status)) = run(&["--status".to_string()], PROBE_TIMEOUT).await else {
            return unavailable_reason().await;
        };
        if !ok {
            return unavailable_reason().await;
        }

        match run(&["--list".into(), "--quiet".into()], PROBE_TIMEOUT).await {
            Ok((true, listed)) if parse_distro_list(&listed).iter().any(|d| d == DISTRO) => {
                if status.contains("Default Version: 1") {
                    WslReadiness::Version1Only
                } else {
                    WslReadiness::Ready
                }
            }
            _ => WslReadiness::DistroMissing,
        }
    }

    /// Import the private distribution and install the backend runtime in it.
    ///
    /// Needs no administrator rights and does not use the Microsoft Store, so
    /// it still works on machines where Store installs are blocked by policy.
    pub async fn provision(
        app_data: &Path,
        mut on_progress: impl FnMut(&str),
    ) -> Result<(), String> {
        let dir = install_dir(app_data);
        std::fs::create_dir_all(&dir).map_err(|e| format!("cannot create {}: {e}", dir.display()))?;
        let tarball = dir.join("rootfs.tar.gz");

        if !tarball.exists() {
            on_progress("Downloading Linux userland...");
            let bytes = reqwest::get(ROOTFS_URL)
                .await
                .map_err(|e| format!("failed to download the Linux userland: {e}"))?
                .error_for_status()
                .map_err(|e| format!("failed to download the Linux userland: {e}"))?
                .bytes()
                .await
                .map_err(|e| format!("failed to download the Linux userland: {e}"))?;
            // Write to a temporary name first so an interrupted download is not
            // mistaken for a complete one on the next attempt.
            let partial = dir.join("rootfs.tar.gz.partial");
            std::fs::write(&partial, &bytes).map_err(|e| e.to_string())?;
            std::fs::rename(&partial, &tarball).map_err(|e| e.to_string())?;
        }

        on_progress("Importing the Linux environment...");
        let (ok, output) = run(&import_args(&dir, &tarball), IMPORT_TIMEOUT).await?;
        if !ok {
            return Err(format!("wsl --import failed: {}", output.trim()));
        }

        on_progress("Preparing the environment...");
        // Workspace and Python live on ext4. /mnt/c costs roughly 10x per file
        // operation, and a run touches a great many files.
        let prepare = format!(
            "set -e; mkdir -p {LINUX_HOME}/workspace; \
             printf '[automount]\\nenabled=true\\n[interop]\\nappendWindowsPath=false\\n' \
             > /etc/wsl.conf"
        );
        let (ok, output) = run(
            &exec_args("/", "sh", &["-lc".to_string(), prepare]),
            PROBE_TIMEOUT,
        )
        .await?;
        if !ok {
            return Err(format!("environment setup failed: {}", output.trim()));
        }

        on_progress("Installing Python (a few minutes)...");
        let python = "set -e; export DEBIAN_FRONTEND=noninteractive; \
             apt-get update -qq; apt-get install -y -qq python3 python3-venv python3-pip; \
             python3 -m venv "
            .to_string()
            + &venv_path();
        let (ok, output) = run(
            &exec_args("/", "sh", &["-lc".to_string(), python]),
            SETUP_TIMEOUT,
        )
        .await?;
        if !ok {
            return Err(format!("Python setup failed: {}", output.trim()));
        }
        Ok(())
    }

    /// Install the backend into the distribution's virtualenv.
    ///
    /// Installed editable from the Windows-side resources directory so an app
    /// update takes effect without re-provisioning. The cost is that Python
    /// imports cross the 9P boundary at startup; the run itself does not,
    /// because the workspace and the pixi environments are on ext4.
    pub async fn install_backend(
        backend_dir: &Path,
        mut on_progress: impl FnMut(&str),
    ) -> Result<(), String> {
        on_progress("Installing the workflow engine...");
        let linux_backend = to_wsl_path(backend_dir)?;
        let script = format!(
            "set -e; {}/bin/pip install --quiet -e {}",
            venv_path(),
            shell_quote(&linux_backend)
        );
        let (ok, output) = run(
            &exec_args("/", "sh", &["-lc".to_string(), script]),
            SETUP_TIMEOUT,
        )
        .await?;
        if !ok {
            return Err(format!("engine install failed: {}", output.trim()));
        }
        Ok(())
    }

    /// Tell "WSL was never enabled" apart from "enabled, awaiting a restart".
    ///
    /// The installer records the flag after enabling the Windows features,
    /// which do not take effect until Windows restarts. Reporting that as a
    /// missing installation would send the user to run an elevated command
    /// they have already effectively run.
    async fn unavailable_reason() -> WslReadiness {
        if reboot_pending().await {
            WslReadiness::RebootRequired
        } else {
            WslReadiness::NotInstalled
        }
    }

    async fn reboot_pending() -> bool {
        // reg.exe rather than a registry crate: one probe, at startup, and it
        // keeps the dependency surface of the desktop shell unchanged.
        let mut cmd = tokio::process::Command::new("reg.exe");
        cmd.args([
            "query",
            r"HKLM\Software\BioNodulo",
            "/v",
            "WslRebootPending",
        ])
        .stdout(Stdio::piped())
        .stderr(Stdio::null());
        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            cmd.creation_flags(0x0800_0000);
        }
        match cmd.output().await {
            Ok(out) => out.status.success(),
            Err(_) => false,
        }
    }

    /// Current IP of the distribution, used only if loopback forwarding fails.
    pub async fn vm_ip() -> Option<String> {
        let args = exec_args("/", "hostname", &["-I".to_string()]);
        match run(&args, PROBE_TIMEOUT).await {
            Ok((true, out)) => parse_vm_ip(&out),
            _ => None,
        }
    }

    /// Remove the distribution, for a clean retry after a failed setup.
    pub async fn unregister() -> Result<(), String> {
        let (ok, out) = run(
            &["--unregister".to_string(), DISTRO.to_string()],
            IMPORT_TIMEOUT,
        )
        .await?;
        if ok {
            Ok(())
        } else {
            Err(out.trim().to_string())
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn drive_paths_become_mnt_paths() {
        assert_eq!(
            to_wsl_path(Path::new(r"C:\Users\mika\reads.fastq")).unwrap(),
            "/mnt/c/Users/mika/reads.fastq"
        );
    }

    #[test]
    fn drive_letters_are_lowercased() {
        // /mnt uses lowercase drive letters; /mnt/D does not exist.
        assert_eq!(
            to_wsl_path(Path::new(r"D:\data")).unwrap(),
            "/mnt/d/data"
        );
    }

    #[test]
    fn a_bare_drive_root_is_translated() {
        assert_eq!(to_wsl_path(Path::new(r"C:\")).unwrap(), "/mnt/c");
        assert_eq!(to_wsl_path(Path::new("C:")).unwrap(), "/mnt/c");
    }

    #[test]
    fn posix_paths_pass_through() {
        // The same code runs on Linux and macOS builds, where paths are already
        // POSIX and must not be mangled.
        assert_eq!(
            to_wsl_path(Path::new("/home/mika/reads.fastq")).unwrap(),
            "/home/mika/reads.fastq"
        );
    }

    #[test]
    fn extended_length_paths_are_ordinary_drive_paths() {
        // std::fs::canonicalize returns this form on Windows, so it reaches
        // to_wsl_path routinely. Refusing it as a network path made the engine
        // install fail with advice about copying to a local drive.
        assert_eq!(
            to_wsl_path(Path::new(r"\\?\D:\a\BioNodulo")).unwrap(),
            "/mnt/d/a/BioNodulo"
        );
    }

    #[test]
    fn an_extended_length_unc_path_is_still_a_network_path() {
        let err = to_wsl_path(Path::new(r"\\?\UNC\server\share\r.fastq")).unwrap_err();
        assert!(err.contains("Network paths"), "{err}");
    }

    #[test]
    fn unc_paths_are_refused_with_a_reason() {
        // \\server\share has no /mnt equivalent. Silently passing it through
        // would produce a file-not-found deep inside a run.
        let err = to_wsl_path(Path::new(r"\\server\share\reads.fastq")).unwrap_err();
        assert!(err.contains("Network paths"), "{err}");
    }

    #[test]
    fn a_colon_in_a_filename_is_not_a_drive() {
        assert_eq!(
            to_wsl_path(Path::new("/tmp/od:d/name")).unwrap(),
            "/tmp/od:d/name"
        );
    }

    #[test]
    fn share_paths_point_into_the_distro() {
        assert_eq!(
            windows_share_path("/opt/bionodulo/workspace"),
            r"\\wsl.localhost\BioNodulo\opt\bionodulo\workspace"
        );
    }

    #[test]
    fn exec_args_set_the_linux_working_directory() {
        // Without --cd the process starts in /mnt/c/... via the inherited
        // Windows cwd: slow, and not where the workspace is.
        let args = exec_args("/opt/bionodulo", "python", &["-m".into(), "server".into()]);

        let cd = args.iter().position(|a| a == "--cd").expect("--cd present");
        assert_eq!(args[cd + 1], "/opt/bionodulo");
        assert_eq!(args.last().unwrap(), "server");
    }

    #[test]
    fn exec_args_target_our_own_distro() {
        let args = exec_args("/tmp", "true", &[]);
        let d = args.iter().position(|a| a == "--distribution").unwrap();
        assert_eq!(args[d + 1], DISTRO);
    }

    fn sample_argv() -> Vec<String> {
        backend_argv(
            "/mnt/c/app",
            "/opt/bionodulo/venv/bin/python",
            "/mnt/c/app/main.py",
            &["--port".into(), "8400".into()],
            &[("BIONODULO_PORT".into(), "8400".into())],
        )
    }

    #[test]
    fn the_script_path_is_passed_through_verbatim() {
        // The caller translates it. Shipping a Windows path here made Python
        // exit instantly with an empty log, because C:\... does not exist in
        // the distribution.
        let argv = sample_argv();
        assert!(argv.contains(&"/mnt/c/app/main.py".to_string()));
        assert!(!argv.iter().any(|a| a.contains('\\') || a.contains(':')
            && a.chars().next().is_some_and(|c| c.is_ascii_uppercase())));
    }

    #[test]
    fn the_environment_travels_inside_the_distribution() {
        // Variables set on the wsl.exe process are NOT inherited by the Linux
        // process; WSL forwards only what WSLENV names. Passing them through
        // `env` is what makes them arrive.
        let argv = sample_argv();
        let env_at = argv.iter().position(|a| a == "env").expect("env prefix");
        let var_at = argv
            .iter()
            .position(|a| a == "BIONODULO_PORT=8400")
            .expect("variable present");
        let py_at = argv
            .iter()
            .position(|a| a.ends_with("/python"))
            .expect("interpreter present");

        // env, then assignments, then the interpreter -- any other order and
        // `env` treats the interpreter as a variable or vice versa.
        assert!(env_at < var_at, "{argv:?}");
        assert!(var_at < py_at, "{argv:?}");
    }

    #[test]
    fn application_arguments_follow_the_script() {
        let argv = sample_argv();
        let script_at = argv.iter().position(|a| a.ends_with("main.py")).unwrap();
        let port_at = argv.iter().position(|a| a == "--port").unwrap();
        assert!(script_at < port_at, "{argv:?}");
    }

    #[test]
    fn a_value_with_spaces_needs_no_quoting() {
        // argv goes straight to execve, so quoting would become part of the
        // value rather than protecting it.
        let argv = backend_argv(
            "/w",
            "/p",
            "/s.py",
            &[],
            &[("DIR".into(), "/mnt/c/My Data".into())],
        );
        assert!(argv.contains(&"DIR=/mnt/c/My Data".to_string()), "{argv:?}");
    }

    #[test]
    fn the_backend_runs_in_our_distribution_and_its_own_directory() {
        let argv = sample_argv();
        let d = argv.iter().position(|a| a == "--distribution").unwrap();
        assert_eq!(argv[d + 1], DISTRO);
        let cd = argv.iter().position(|a| a == "--cd").unwrap();
        assert_eq!(argv[cd + 1], "/mnt/c/app");
    }

    #[test]
    fn import_pins_wsl_version_2() {
        // A version-1 import silently produces a userland that cannot run these
        // tools, and the failure surfaces much later.
        let args = import_args(Path::new(r"C:\d"), Path::new(r"C:\rootfs.tar"));
        let v = args.iter().position(|a| a == "--version").unwrap();
        assert_eq!(args[v + 1], "2");
    }

    #[test]
    fn distro_list_ignores_the_default_marker_and_blanks() {
        let listed = parse_distro_list("Ubuntu (Default)\r\n\r\nBioNodulo\r\n");
        assert_eq!(listed, vec!["Ubuntu", "BioNodulo"]);
    }

    #[test]
    fn distro_list_survives_utf16_leftovers() {
        let listed = parse_distro_list("\u{feff}BioNodulo\u{0}\n");
        assert_eq!(listed, vec!["BioNodulo"]);
    }

    #[test]
    fn wsl_output_is_decoded_from_utf16le() {
        let bytes: Vec<u8> = "BioNodulo".encode_utf16().flat_map(u16::to_le_bytes).collect();
        assert_eq!(decode_wsl_output(&bytes), "BioNodulo");
    }

    #[test]
    fn odd_length_output_falls_back_to_utf8() {
        assert_eq!(decode_wsl_output(b"abc"), "abc");
    }

    #[test]
    fn vm_ip_takes_the_first_address() {
        // `hostname -I` prints every address, IPv6 included.
        assert_eq!(
            parse_vm_ip("172.24.60.3 fe80::215:5dff:fe0a:1").as_deref(),
            Some("172.24.60.3")
        );
    }

    #[test]
    fn vm_ip_is_absent_when_nothing_parses() {
        assert_eq!(parse_vm_ip(""), None);
        assert_eq!(parse_vm_ip("fe80::1"), None);
    }

    #[test]
    fn loopback_is_tried_before_the_vm_address() {
        let urls = candidate_urls(8400, Some("172.24.60.3"));
        assert_eq!(urls[0], "http://127.0.0.1:8400");
        assert_eq!(urls[1], "http://172.24.60.3:8400");
    }

    #[test]
    fn a_missing_vm_address_still_yields_loopback() {
        assert_eq!(candidate_urls(8400, None), vec!["http://127.0.0.1:8400"]);
    }

    #[test]
    fn every_state_has_a_distinct_key() {
        let keys: Vec<_> = [
            WslReadiness::Ready,
            WslReadiness::NotInstalled,
            WslReadiness::RebootRequired,
            WslReadiness::DistroMissing,
            WslReadiness::Version1Only,
        ]
        .iter()
        .map(|s| s.state_key())
        .collect();
        let mut unique = keys.clone();
        unique.sort_unstable();
        unique.dedup();
        assert_eq!(unique.len(), keys.len());
    }

    #[test]
    fn readiness_messages_name_the_next_action() {
        assert!(WslReadiness::NotInstalled.message().contains("wsl --install"));
        assert!(WslReadiness::NotInstalled.message().contains("administrator"));
        assert!(WslReadiness::Version1Only.message().contains("--set-default-version 2"));
    }

    #[test]
    fn a_pending_restart_does_not_ask_for_an_elevated_command() {
        // The installer already ran it. Repeating that advice would be wrong
        // and would read as the setup having failed.
        let message = WslReadiness::RebootRequired.message();
        assert!(message.contains("restart"), "{message}");
        assert!(!message.contains("wsl --install"), "{message}");
        assert!(message.contains("cloud"), "{message}");
    }

    #[test]
    fn the_cloud_is_offered_when_administrator_rights_are_needed() {
        // The one case the user may be unable to resolve themselves.
        assert!(!WslReadiness::NotInstalled.user_fixable());
        assert!(WslReadiness::NotInstalled.message().contains("cloud"));
        assert!(WslReadiness::DistroMissing.user_fixable());
    }

    #[test]
    fn the_virtualenv_is_not_on_the_windows_drive() {
        // Python imports over 9P would tax every backend start.
        assert!(!venv_path().starts_with("/mnt/"));
        assert!(linux_python().starts_with(&venv_path()));
    }

    #[test]
    fn shell_quoting_survives_spaces_and_apostrophes() {
        // "C:\Users\O'Brien\My Data" is an ordinary Windows home directory.
        assert_eq!(shell_quote("/mnt/c/My Data"), "'/mnt/c/My Data'");
        assert_eq!(shell_quote("/mnt/c/O'B"), r"'/mnt/c/O'\''B'");
    }

    #[test]
    fn the_workspace_is_not_on_the_windows_drive() {
        // Living under /mnt/c would cost roughly 10x on every file operation.
        assert!(!linux_workspace().starts_with("/mnt/"));
    }
}
