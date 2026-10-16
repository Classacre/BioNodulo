"""Exercise the real rollout shell with fake registry/build commands only."""

from __future__ import annotations
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/cloud-sync.yml"
BASH = Path(r"C:\Program Files\Git\bin\bash.exe") if os.name == "nt" else Path("/bin/bash")
SYNTHETIC_PASSWORD = "fixture-public-registry-password-never-log"


@unittest.skipUnless(BASH.is_file(), "Bash is required for the rollout shell regression")
class PublicRegistryAuthTests(unittest.TestCase):
    def run_rollout(self, *, auth_fails=False, editor_fails=False):
        workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
        build = next(step for step in workflow["jobs"]["sync"]["steps"] if step.get("id") == "images")["run"]
        with tempfile.TemporaryDirectory(prefix="bionodulo-registry-auth-") as folder:
            root = Path(folder)
            binaries = root / "bin"
            binaries.mkdir()
            infrastructure = root / "bionodulo-website/infrastructure"
            infrastructure.mkdir(parents=True)
            events = root / "events.txt"
            marker = root / "public-login-marker"
            manifest = "fixture-exact-oci-manifest"
            digest = hashlib.sha256(manifest.encode()).hexdigest()
            env = os.environ.copy()
            env.update(
                PATH=str(binaries) + os.pathsep + env.get("PATH", ""),
                APP_SHA="a" * 40,
                WEBSITE_SHA="b" * 40,
                MOCK_BIN=binaries.as_posix(),
                EVENT_LOG=events.as_posix(),
                PUBLIC_LOGIN_MARKER=marker.as_posix(),
                GITHUB_OUTPUT=(root / "output.txt").as_posix(),
                SYNTHETIC_PASSWORD=SYNTHETIC_PASSWORD,
                AUTH_FAIL=str(int(auth_fails)),
                EDITOR_FAIL=str(int(editor_fails)),
                MANIFEST=manifest,
                WORKER_REF="108084495419.dkr.ecr.us-east-1.amazonaws.com/bionodulo/worker@sha256:" + digest,
            )
            scripts = {
                "aws": r"""#!/usr/bin/env bash
set -euo pipefail
[ "$*" = 'ecr-public get-login-password --region us-east-1' ] || exit 80
printf 'public-auth-us-east-1\n' >> "$EVENT_LOG"
[ "$AUTH_FAIL" = 0 ] || exit 23
printf '%s\n' "$SYNTHETIC_PASSWORD"
""",
                "git": r"""#!/usr/bin/env bash
set -euo pipefail
if [ "$2" = BioNodulo ]; then printf '%s\n' "$APP_SHA"; else printf '%s\n' "$WEBSITE_SHA"; fi
""",
                "docker": r"""#!/usr/bin/env bash
set -euo pipefail
case "$1" in
 login)
  [ "$*" = 'login --username AWS --password-stdin public.ecr.aws' ] || exit 81
  IFS= read -r password || true
  [ "${password:-}" = "$SYNTHETIC_PASSWORD" ] || exit 82
  printf 'public-login-password-on-stdin\n' >> "$EVENT_LOG"
  touch "$PUBLIC_LOGIN_MARKER"
  ;;
 logout)
  [ "$*" = 'logout public.ecr.aws' ] || exit 83
  printf 'public-logout\n' >> "$EVENT_LOG"
  rm -f "$PUBLIC_LOGIN_MARKER"
  ;;
 buildx)
  printf 'mirror-inspect\n' >> "$EVENT_LOG"
  printf '%s' "$MANIFEST"
  ;;
 *) exit 84;;
esac
""",
            }
            for name, source in scripts.items():
                target = binaries / name
                target.write_text(source, encoding="utf-8", newline="\n")
                target.chmod(0o755)
            deploy = infrastructure / "deploy-backend.sh"
            deploy.write_text(
                r"""#!/usr/bin/env bash
set -euo pipefail
[ -f "$PUBLIC_LOGIN_MARKER" ] || exit 85
printf 'deploy-%s\n' "$1" >> "$EVENT_LOG"
if [ "$1" = editor ] && [ "$EDITOR_FAIL" = 1 ]; then exit 24; fi
if [ "$1" = worker ]; then
 printf '[deploy] Image tag: rem-aaaaaaaa-bbbbbbbb-20261016\n'
 printf '%s\n' "$WORKER_REF"
fi
""",
                encoding="utf-8",
                newline="\n",
            )
            deploy.chmod(0o755)
            path_setup = (
                'export PATH="$(cygpath -u "$MOCK_BIN"):$PATH"\n'
                if os.name == "nt"
                else 'export PATH="$MOCK_BIN:$PATH"\n'
            )
            shell = root / "rollout.sh"
            shell.write_text(path_setup + build, encoding="utf-8", newline="\n")
            result = subprocess.run(
                [str(BASH), "--noprofile", "--norc", shell.as_posix()],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                timeout=20,
            )
            log = events.read_text().splitlines() if events.exists() else []
            self.assertNotIn(SYNTHETIC_PASSWORD, result.stdout + result.stderr + "\n".join(log))
            self.assertFalse(marker.exists(), "Public registry login must be removed on every exit")
            return result, log

    def test_authenticates_before_both_builds_and_logs_out(self):
        result, events = self.run_rollout()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            events,
            [
                "public-auth-us-east-1",
                "public-login-password-on-stdin",
                "deploy-editor",
                "deploy-worker",
                "mirror-inspect",
                "public-logout",
            ],
        )

    def test_auth_failure_stops_before_any_image_rollout(self):
        result, events = self.run_rollout(auth_fails=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(events, ["public-auth-us-east-1", "public-logout"])

    def test_later_build_failure_still_removes_only_public_login(self):
        result, events = self.run_rollout(editor_fails=True)
        self.assertEqual(result.returncode, 24, result.stderr)
        self.assertEqual(
            events, ["public-auth-us-east-1", "public-login-password-on-stdin", "deploy-editor", "public-logout"]
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
