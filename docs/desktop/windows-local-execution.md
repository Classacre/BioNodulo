# Local execution on Windows

Windows cannot run BioNodulo workflows natively. Every tool comes from
bioconda, which publishes **no win-64 packages at all** — `blast` and `samtools`
exist only for `linux-64`, `linux-aarch64`, `osx-64` and `osx-arm64`. This is an
upstream packaging fact, not something the installer can work around.

pixi's own error suggests `pixi workspace platform add win-64`. Following it
does not help: it converts a clear install failure into a confusing solve
failure a few minutes later. `explain_unsupported_platform` in
`bionodulo/environments/manifest.py` pre-empts that message.

Windows users therefore have two routes:

| | Setup | Where it runs |
|---|---|---|
| **Cloud** (recommended) | none | Linux workers |
| **Local execution** | administrator once, a few GB | a private WSL2 distribution |

The app recommends the cloud, and keeps recommending it: local execution costs
an elevated command, several GB of disk, and a multi-minute first install.

## How local execution works

`desktop/src-tauri/src/wsl.rs` provisions a **private** distribution named
`BioNodulo` and runs the backend inside it. The committed `linux-64` locks apply
unchanged, so a workflow behaves exactly as it does on a Linux desktop or a
cloud worker.

A user's own distributions are never touched. We install a pinned userland and
must not mutate something they depend on.

### Four platform constraints shape the design

**Enabling WSL needs administrator, once.** `VirtualMachinePlatform` is a
machine-wide optional component; there is no supported way around it. The app
detects this state (`WslReadiness::NotInstalled`), shows the exact command
(`wsl --install --no-distribution`), and does not pretend it can self-install.
This is the only state the user may be unable to resolve alone, so it is also
the state where the cloud is offered most prominently.

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
import, apt, the pip install, and loopback forwarding are all unverified in
practice. Treat the first Windows run as the real test.
