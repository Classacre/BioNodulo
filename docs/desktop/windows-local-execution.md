# Local execution on Windows

Windows cannot run BioNodulo workflows natively. Every tool comes from
bioconda, which publishes **no win-64 packages at all** — `blast` and `samtools`
exist only for `linux-64`, `linux-aarch64`, `osx-64` and `osx-arm64`. This is an
upstream packaging fact, not something the installer can work around.

pixi's own error suggests `pixi workspace platform add win-64`. Following it
does not help: it converts a clear install failure into a confusing solve
failure a few minutes later. `explain_unsupported_platform` in
`bionodulo/environments/manifest.py` pre-empts that message.

**Local execution is the default on Windows.** The installer runs elevated
(`installMode: perMachine`) and enables WSL2 in `NSIS_HOOK_POSTINSTALL`, while
it already holds the rights to do so. Everything after that -- importing the
distribution, installing the engine -- needs no elevation, so **the application
itself never runs elevated**.

That distinction is deliberate. Running the GUI as administrator would be a
poor trade: it hosts a webview that loads remote content and spawns arbitrary
processes, so any code-execution bug becomes a full machine compromise; UIPI
blocks drag-and-drop from a normal Explorer window, which breaks the main way
files get into a file-oriented app; and it puts a UAC prompt on every launch.
None of it is necessary, because the only privileged step happens once, in the
installer.

The cloud is offered as a **suggestion**, not a gate: a single dismissible
notification the first time a workflow runs locally, with an action to switch.
It never blocks or delays the run.

## How local execution works

`desktop/src-tauri/src/wsl.rs` provisions a **private** distribution named
`BioNodulo` and runs the backend inside it. The committed `linux-64` locks apply
unchanged, so a workflow behaves exactly as it does on a Linux desktop or a
cloud worker.

A user's own distributions are never touched. We install a pinned userland and
must not mutate something they depend on.

### Four platform constraints shape the design

**Enabling WSL needs administrator, once.** `VirtualMachinePlatform` is a
machine-wide optional component. The installer does this while elevated, trying
`wsl --install --no-distribution` first and falling back to enabling the two
features with `dism.exe` on builds whose `wsl.exe` predates that flag. Exit code
3010 ("success, reboot required") is the normal outcome.

The features do not take effect until Windows restarts, so the installer
records `HKLM\Software\BioNodulo\WslRebootPending` and the app reports
`WslReadiness::RebootRequired` -- distinct from `NotInstalled`, because telling
someone to run an elevated command the installer already ran reads as a failure.

If enabling fails anyway -- virtualization disabled in firmware, or restricted
by policy -- neither the installer nor the app can fix it. Both say so and fall
back to the cloud.

**`wsl --import` needs no elevation** and does not use the Microsoft Store. That
matters on managed machines where Store installs are blocked by group policy —
the tarball path still works there.

**`/mnt/c` is roughly 10× slower than ext4.** It is served over 9P with no
caching, so every `stat` is a host round trip. The workspace and the Python
virtualenv therefore live at `/opt/bionodulo` inside the distribution, and
Windows reaches results through `\\wsl.localhost\BioNodulo\...` — files are read
from Linux at full speed while Explorer and file dialogs still open them.

The backend itself is installed editable from the Windows-side resources
directory. Python imports cross the 9P boundary at startup, which is a
deliberate trade: it costs a slower start, and it means an app update takes
effect without re-provisioning. The run itself never crosses the boundary.

**localhost forwarding is not a stable contract.** It breaks after sleep/wake,
under VPN filter drivers, and historically on ports at or below 3088. So:

- the backend binds `0.0.0.0`, not loopback, because loopback-only would be
  unreachable from Windows;
- the port starts at `MIN_FORWARDED_PORT` (8300), enforced at compile time;
- the health check probes `127.0.0.1` **and** the distribution's own address on
  every pass, and adopts whichever answers. Giving loopback the full 60-second
  budget first would look like a dead backend for a minute whenever forwarding
  is broken.

## Failure handling

Local setup is optional, so a failure is not a failed installation — first-run
reports "Setup complete, without local execution" and the app remains usable on
the cloud. `reset_local_execution` unregisters the distribution for a clean
retry.

`localExecution` is only recorded as enabled once **both** provisioning and the
engine install succeed. A half-provisioned distribution the app believes is
ready would fail every run instead of offering setup.

## Testing status

The pure logic — path translation, argument construction, UTF-16 decoding,
distro-list parsing, URL candidates, readiness messaging — is covered by unit
tests in `wsl.rs` that run on any platform.

**The runtime path has not been exercised on real Windows hardware.** Provision,
import, apt, the pip install, loopback forwarding, and the whole NSIS hook are
all unverified in practice. The Windows CI job compiles the code and builds the
installer; neither runs it. Treat the first Windows install as the real test,
and check in this order: does the installer enable WSL, does the reboot-pending
message appear, does the distribution import, does the engine install.
