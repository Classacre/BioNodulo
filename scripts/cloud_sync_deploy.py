"""Start a fresh production Git build using current project environment pins.

Used only after cloud-sync has admitted an exact CI-green prepared SHA that is
already website master, built matching images, and updated the production pins.
Never redeploy by deploymentId: that would inherit the old environment snapshot.
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.vercel.com"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *unused):
        return None


def _json_request(opener, token: str, path: str, body=None):
    request = urllib.request.Request(
        API + path,
        data=None if body is None else json.dumps(body).encode(),
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
            "User-Agent": "BioNodulo-Cloud-Sync/1.0",
        },
    )
    with opener.open(request, timeout=30) as response:
        payload = response.read(MAX_RESPONSE_BYTES + 1)
        if len(payload) > MAX_RESPONSE_BYTES:
            raise ValueError("Oversized Vercel response")
        result = json.loads(payload)
        if not isinstance(result, dict):
            raise ValueError("Invalid Vercel response")
        return result


def create_fresh_deployment(*, project_id, team_id, repo_id, website_sha, token, opener=None):
    """Validate the existing Git link, then POST once without settings overrides."""
    for value, pattern in [
        (project_id, r"prj_[A-Za-z0-9]+"),
        (team_id, r"team_[A-Za-z0-9]+"),
        (repo_id, r"[1-9][0-9]*"),
        (website_sha, r"[0-9a-f]{40}"),
    ]:
        if not isinstance(value, str) or re.fullmatch(pattern, value) is None:
            raise ValueError("Invalid immutable deployment identity")
    if not token:
        raise ValueError("Missing Vercel authorization")
    opener = opener or urllib.request.build_opener(NoRedirect())
    query = urllib.parse.urlencode({"teamId": team_id})
    project = _json_request(opener, token, f"/v9/projects/{project_id}?{query}")
    link = project.get("link")
    if (
        project.get("id") != project_id
        or not isinstance(project.get("name"), str)
        or re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,99}", project["name"]) is None
        or not isinstance(link, dict)
        or link.get("type") != "github"
        or isinstance(link.get("repoId"), bool)
        or str(link.get("repoId")) != repo_id
        or link.get("productionBranch") != "master"
    ):
        raise ValueError("Vercel project Git link does not match the admitted website")
    payload = {
        "name": project["name"],
        "project": project_id,
        "target": "production",
        "gitSource": {"type": "github", "repoId": repo_id, "ref": "master", "sha": website_sha},
    }
    # forceNew prevents a same-commit deployment from being deduplicated. No
    # deploymentId/env/projectSettings means the newly updated project pins apply.
    result = _json_request(opener, token, f"/v13/deployments?forceNew=1&{query}", payload)
    if (
        not isinstance(result.get("id"), str)
        or re.fullmatch(r"dpl_[A-Za-z0-9]+", result["id"]) is None
        or result.get("target") != "production"
        or result.get("readyState") not in {"QUEUED", "INITIALIZING", "BUILDING", "READY"}
    ):
        raise ValueError("Fresh production deployment was not accepted")
    # Do not print/store the full deployment response; it can contain environment
    # metadata. READY and the actual alias/source are independently checked later.
    return {"deployment_id": result["id"], "state": result["readyState"], "website_sha": website_sha}


def main() -> int:
    try:
        result = create_fresh_deployment(
            project_id=os.environ.get("VERCEL_PROJECT_ID"),
            team_id=os.environ.get("VERCEL_ORG_ID"),
            repo_id=os.environ.get("WEBSITE_REPO_ID"),
            website_sha=os.environ.get("WEBSITE_SHA"),
            token=os.environ.get("VERCEL_TOKEN"),
        )
    except Exception as error:
        # Raw API exceptions/responses may include private project details.
        status = f" (HTTP {error.code})" if isinstance(error, urllib.error.HTTPError) else ""
        print(f"Fresh production Git deployment failed: {type(error).__name__}{status}", file=sys.stderr)
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
