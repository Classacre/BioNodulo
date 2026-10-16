"""Exercise the real prepared-release shell and the bounded Vercel Git request."""

from __future__ import annotations

import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock
import urllib.error

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/cloud-sync.yml"
BASH = Path(r"C:\Program Files\Git\bin\bash.exe") if os.name == "nt" else Path("/bin/bash")
APP = "a" * 40
WEB = "b" * 40
MASTER = "c" * 40
TOKEN = "fixture-vercel-token-never-log"
SPEC = importlib.util.spec_from_file_location("cloud_sync_deploy", ROOT / "scripts/cloud_sync_deploy.py")
assert SPEC is not None and SPEC.loader is not None
deploy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(deploy)


@unittest.skipUnless(BASH.is_file(), "Bash is required for the release shell regression")
class PreparedReleaseShellTests(unittest.TestCase):
    def run_step(self, step_id, **changes):
        steps = yaml.safe_load(WORKFLOW.read_text())["jobs"]["sync"]["steps"]
        step = next(row for row in steps if row.get("id") == step_id) if step_id == "rel" else steps[-1]
        with tempfile.TemporaryDirectory(prefix="bionodulo-prepared-release-") as folder:
            root = Path(folder)
            binaries = root / "bin"
            binaries.mkdir()
            events = root / "events"
            output = root / "output"
            env = os.environ.copy()
            env.update(
                APP_SHA=APP, WEBSITE_SHA=WEB, WEBSITE_REF=WEB, MASTER_SHA=MASTER,
                MAIN_SHA=APP, ANCESTOR="0", WEBSITE_CI="1", APP_VERSION="0.1.1-alpha.10",
                SITE_VERSION="0.1.1-alpha.10", GITHUB_EVENT_NAME="push",
                GITHUB_REPOSITORY="Classacre/BioNodulo", WEBSITE_REPO="Classacre/bionodulo-website",
                GITHUB_OUTPUT=output.as_posix(), EVENT_LOG=events.as_posix(), MOCK_BIN=binaries.as_posix(),
                EXPECTED_MASTER=MASTER, PREPARED_REDEPLOY="", WEBSITE_REPO_ID="1285848505",
                VERCEL_TOKEN=TOKEN,
            )
            env.update(changes)
            scripts = {
                "git": r"""#!/usr/bin/env bash
set -euo pipefail
case "$*" in
 '-C BioNodulo rev-parse HEAD') printf '%s\n' "$APP_SHA";;
 '-C bionodulo-website rev-parse HEAD') printf '%s\n' "$WEBSITE_SHA";;
 'ls-remote https://github.com/Classacre/BioNodulo.git refs/heads/main') printf '%s\trefs/heads/main\n' "$MAIN_SHA";;
 '-C bionodulo-website fetch origin master') :;;
 '-C bionodulo-website rev-parse origin/master') printf '%s\n' "${FETCHED_MASTER_SHA:-$MASTER_SHA}";;
 '-C bionodulo-website merge-base --is-ancestor '*) exit "$ANCESTOR";;
 '-C bionodulo-website ls-remote origin refs/heads/master') printf '%s\trefs/heads/master\n' "$MASTER_SHA";;
 '-C bionodulo-website push origin HEAD:master') printf 'push\n' >> "$EVENT_LOG";;
 *) exit 81;;
esac
""",
                "gh": r"""#!/usr/bin/env bash
set -euo pipefail
case "$2" in
 repos/Classacre/bionodulo-website/actions/workflows/ci.yml/runs*) printf '%s\n' "$WEBSITE_CI";;
 repos/Classacre/bionodulo-website) printf '%s\n' "$WEBSITE_REPO_ID";;
 *) exit 82;;
esac
""",
                "node": r"""#!/usr/bin/env bash
set -euo pipefail
case "$2" in
 *BioNodulo/web/package.json*) printf '%s\n' "$APP_VERSION";;
 *) printf '%s\n' "$SITE_VERSION";;
esac
""",
                "python3": r"""#!/usr/bin/env bash
set -euo pipefail
case "$1" in
 -c) printf 'sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd\n';;
 BioNodulo/scripts/cloud_sync_deploy.py) printf 'fresh-git-deployment\n' >> "$EVENT_LOG";;
 *) exit 83;;
esac
""",
            }
            for name, source in scripts.items():
                path = binaries / name
                path.write_text(source, newline="\n")
                path.chmod(0o755)
            setup = 'export PATH="$(cygpath -u "$MOCK_BIN"):$PATH"\n' if os.name == "nt" else 'export PATH="$MOCK_BIN:$PATH"\n'
            shell = root / "step.sh"
            shell.write_text(setup + step["run"], newline="\n")
            result = subprocess.run([str(BASH), "--noprofile", "--norc", shell.as_posix()], cwd=root,
                                    env=env, capture_output=True, text=True, timeout=15)
            self.assertNotIn(TOKEN, result.stdout + result.stderr)
            values = dict(line.split("=", 1) for line in output.read_text().splitlines()) if output.exists() else {}
            return result, values, events.read_text().splitlines() if events.exists() else []

    def test_equal_master_is_admitted_but_never_marked_current(self):
        result, output, _ = self.run_step("rel", MASTER_SHA=WEB)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output["prepared_redeploy"], "true")
        self.assertEqual(output["website_repo_id"], "1285848505")
        self.assertNotIn("current", output)

    def test_ahead_green_sha_keeps_normal_push_path(self):
        result, output, _ = self.run_step("rel")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("prepared_redeploy", output)

    def test_immutable_green_version_and_ancestry_guards_remain_fail_closed(self):
        cases = [
            {"WEBSITE_REF": "b" * 8}, {"WEBSITE_REF": "d" * 40},
            {"WEBSITE_CI": "0"}, {"SITE_VERSION": "0.0.0"},
            {"MAIN_SHA": "d" * 40}, {"ANCESTOR": "1"}, {"WEBSITE_REPO_ID": "null"},
            {"FETCHED_MASTER_SHA": WEB},
        ]
        for changes in cases:
            with self.subTest(changes=changes):
                result, _, events = self.run_step("rel", **changes)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(events, [])

    def test_same_sha_triggers_fresh_git_request_instead_of_noop_push(self):
        result, _, events = self.run_step("deploy", MASTER_SHA=WEB, EXPECTED_MASTER=WEB, PREPARED_REDEPLOY="true")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(events, ["fresh-git-deployment"])

    def test_ahead_sha_still_pushes_once(self):
        result, _, events = self.run_step("deploy")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(events, ["push"])

    def test_stale_heads_or_wrong_equal_sha_never_trigger_a_deployment(self):
        for changes in [{"MAIN_SHA": "d" * 40}, {"MASTER_SHA": "d" * 40}, {"PREPARED_REDEPLOY": "true"}]:
            with self.subTest(changes=changes):
                result, _, events = self.run_step("deploy", **changes)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(events, [])

    def test_real_workflow_orders_images_and_all_pins_before_deployment(self):
        steps = yaml.safe_load(WORKFLOW.read_text())["jobs"]["sync"]["steps"]
        images = next(i for i, row in enumerate(steps) if row.get("id") == "images")
        pins = next(i for i, row in enumerate(steps) if row.get("name") == "Update the Vercel env pins")
        self.assertLess(images, pins)
        self.assertLess(pins, len(steps) - 1)
        self.assertIn("WORKER_IMAGE_OCI", steps[pins]["run"])
        self.assertIn("python3 BioNodulo/scripts/cloud_sync_deploy.py", steps[-1]["run"])
        resolve = next(row for row in steps if row.get("id") == "rel")["run"]
        self.assertIn("Required app CI jobs did not pass for this SHA", resolve)
        self.assertIn('select(.event == "push" and .conclusion == "success")', resolve)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload if isinstance(payload, bytes) else json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *unused):
        return False

    def read(self, maximum):
        return self.payload[:maximum]


class FakeOpener:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.requests = []

    def open(self, request, **unused):
        self.requests.append(request)
        value = next(self.responses)
        if isinstance(value, Exception):
            raise value
        return FakeResponse(value)


class FreshGitDeploymentTests(unittest.TestCase):
    def setUp(self):
        self.project = {"id": "prj_fixture", "name": "bionodulo", "link": {
            "type": "github", "repoId": 1285848505, "productionBranch": "master"}, "env": [TOKEN]}
        self.accepted = {"id": "dpl_fixture", "target": "production", "readyState": "QUEUED", "private": TOKEN}
        self.options = {"project_id": "prj_fixture", "team_id": "team_fixture", "repo_id": "1285848505",
                        "website_sha": WEB, "token": TOKEN}

    def test_post_pins_build_uses_exact_git_sha_and_current_project_without_snapshot_overrides(self):
        opener = FakeOpener([self.project, self.accepted])
        result = deploy.create_fresh_deployment(**self.options, opener=opener)
        request = opener.requests[1]
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.full_url, "https://api.vercel.com/v13/deployments?forceNew=1&teamId=team_fixture")
        self.assertEqual(json.loads(request.data), {"name": "bionodulo", "project": "prj_fixture", "target": "production",
            "gitSource": {"type": "github", "repoId": "1285848505", "ref": "master", "sha": WEB}})
        self.assertEqual(result, {"deployment_id": "dpl_fixture", "state": "QUEUED", "website_sha": WEB})
        self.assertNotIn(TOKEN, json.dumps(result))

    def test_invalid_identity_or_project_git_link_stops_before_post(self):
        for field, value in [("id", "prj_other"), ("name", None), ("link", None)]:
            with self.subTest(field=field):
                opener = FakeOpener([{**self.project, field: value}])
                with self.assertRaises(ValueError):
                    deploy.create_fresh_deployment(**self.options, opener=opener)
                self.assertEqual(len(opener.requests), 1)
        for field, value in [("type", "gitlab"), ("repoId", 999), ("productionBranch", "other")]:
            with self.subTest(field=field):
                opener = FakeOpener([{**self.project, "link": {**self.project["link"], field: value}}])
                with self.assertRaises(ValueError):
                    deploy.create_fresh_deployment(**self.options, opener=opener)
                self.assertEqual(len(opener.requests), 1)
        opener = FakeOpener([])
        with self.assertRaises(ValueError):
            deploy.create_fresh_deployment(**{**self.options, "website_sha": "master"}, opener=opener)
        self.assertEqual(opener.requests, [])

    def test_failed_or_ambiguous_post_is_not_retried(self):
        failure = urllib.error.HTTPError("https://api.vercel.com", 503, TOKEN, {}, None)
        opener = FakeOpener([self.project, failure])
        with self.assertRaises(urllib.error.HTTPError):
            deploy.create_fresh_deployment(**self.options, opener=opener)
        self.assertEqual(len(opener.requests), 2)

    def test_error_state_or_unknown_response_does_not_report_success(self):
        for response in [[], {**self.accepted, "readyState": "ERROR"}, {**self.accepted, "target": "preview"}, {"error": TOKEN}]:
            with self.subTest(response_type=type(response).__name__):
                with self.assertRaises(ValueError):
                    deploy.create_fresh_deployment(**self.options, opener=FakeOpener([self.project, response]))

    def test_responses_are_bounded_and_authorization_is_not_redirected(self):
        with self.assertRaises(ValueError):
            deploy.create_fresh_deployment(**self.options, opener=FakeOpener([b"x" * (deploy.MAX_RESPONSE_BYTES + 1)]))
        self.assertIsNone(deploy.NoRedirect().redirect_request(None, None, None, None, None, None))

    def test_cli_failure_never_prints_raw_api_details_or_credentials(self):
        environment = {"VERCEL_PROJECT_ID": "prj_fixture", "VERCEL_ORG_ID": "team_fixture",
                       "WEBSITE_REPO_ID": "1285848505", "WEBSITE_SHA": WEB, "VERCEL_TOKEN": TOKEN}
        opener = FakeOpener([urllib.error.URLError(TOKEN)])
        with mock.patch.dict(os.environ, environment), mock.patch.object(deploy.urllib.request, "build_opener", return_value=opener):
            with mock.patch("sys.stdout", new_callable=io.StringIO) as stdout, mock.patch("sys.stderr", new_callable=io.StringIO) as stderr:
                code = deploy.main()
        self.assertEqual(code, 1)
        self.assertNotIn(TOKEN, stdout.getvalue() + stderr.getvalue())
        self.assertIn("URLError", stderr.getvalue())


if __name__ == "__main__":
    unittest.main(verbosity=2)
