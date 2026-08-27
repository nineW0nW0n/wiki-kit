#!/usr/bin/env python3
"""github.py — branch, file, pull request. Nothing else.

The transport is injected so tests never reach the network, and so the only
credentialed call site in the service is `_http` below. A contents PUT without
a `sha` fails with 422 when the path exists; that is the collision check, so
no extra probe call is made. The branch carries the same -2..-5 suffix as the
path, because a same-day duplicate title collides on the branch first.
"""
from __future__ import annotations

import base64
import os
import re

MAX_SUFFIX = 5


class GitHubError(Exception):
    def __init__(self, message: str, status: int = 0):
        super().__init__(message)
        self.status = status


def owner_repo(url: str) -> tuple[str, str]:
    m = re.search(r"[/:]([^/:]+)/([^/]+?)(?:\.git)?$", url.strip())
    if not m:
        raise GitHubError(f"cannot read owner/repo from {url!r}")
    return m.group(1), m.group(2)


def _suffixed(stem: str, n: int, tail: str = "") -> str:
    """n == 1 is the original; 2..5 append `-n` before the tail."""
    return (stem if n == 1 else f"{stem}-{n}") + tail


def open_note_pr(*, request, token: str, url: str, base: str, path: str,
                 content: str, title: str, body: str, day: str,
                 slug: str) -> str:
    owner, repo = owner_repo(url)
    api = f"repos/{owner}/{repo}"

    status, payload = request("GET", f"{api}/git/ref/heads/{base}", token, None)
    if status != 200:
        raise GitHubError(f"cannot read {base}: HTTP {status}", status)
    base_sha = payload["object"]["sha"]

    encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
    # Branch and path carry the same suffix. A second note with the same title
    # on the same day collides on the branch first (the earlier note's branch
    # is still open), so the retry has to move both or it never fires.
    branch = written = None
    for n in range(1, MAX_SUFFIX + 1):
        candidate_branch = _suffixed(f"intake/{day}-{slug}", n)
        candidate = _suffixed(path[:-3], n, ".md")
        status, _ = request("POST", f"{api}/git/refs", token,
                            {"ref": f"refs/heads/{candidate_branch}",
                             "sha": base_sha})
        if status == 422:  # branch exists — same title, same day
            continue
        if status not in (200, 201):
            raise GitHubError(
                f"cannot create branch {candidate_branch}: HTTP {status}",
                status)
        status, _ = request("PUT", f"{api}/contents/{candidate}", token,
                            {"message": f"raw: {title}", "content": encoded,
                             "branch": candidate_branch})
        if status in (200, 201):
            branch, written = candidate_branch, candidate
            break
        _delete_branch(request, token, api, candidate_branch)
        if status != 422:
            raise GitHubError(f"cannot write {candidate}: HTTP {status}", status)
    if written is None:
        raise GitHubError(f"{path} and {MAX_SUFFIX - 1} suffixed variants "
                          f"already exists; rename the note", 422)

    status, payload = request("POST", f"{api}/pulls", token,
                              {"title": f"raw: {title}", "head": branch,
                               "base": base, "body": body})
    if status not in (200, 201):
        _delete_branch(request, token, api, branch)
        raise GitHubError(f"file written but PR failed: HTTP {status}", status)
    return payload["html_url"]


def _delete_branch(request, token: str, api: str, branch: str) -> None:
    try:
        request("DELETE", f"{api}/git/refs/heads/{branch}", token, None)
    except Exception:  # best effort; the caller already has a real error
        pass


def http(method: str, path: str, token: str, json=None):
    """Real transport. Imported lazily so unit tests need no HTTP client."""
    import httpx2 as httpx

    base = os.environ.get("GITHUB_API", "https://api.github.com")
    r = httpx.request(
        method, f"{base}/{path}", timeout=15.0,
        headers={"Authorization": f"Bearer {token}",
                 "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28"},
        json=json)
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, {}
