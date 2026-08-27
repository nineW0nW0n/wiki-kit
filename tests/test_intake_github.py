"""Tests for intake/github.py with an injected fake transport."""
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "intake"))

import github  # noqa: E402


class Fake:
    """Records calls; replays a scripted list of (status, payload)."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    def __call__(self, method, path, token, json=None):
        self.calls.append((method, path, json))
        return self.script.pop(0)


OK_REF = (200, {"object": {"sha": "basesha"}})
OK_CREATED = (201, {})
OK_PR = (201, {"html_url": "https://github.com/o/brain-eng/pull/7"})


@pytest.mark.parametrize("url,expected", [
    ("https://github.com/o/brain-eng.git", ("o", "brain-eng")),
    ("https://github.com/o/brain-eng", ("o", "brain-eng")),
    ("git@github.com:o/brain-eng.git", ("o", "brain-eng")),
])
def test_owner_repo(url, expected):
    assert github.owner_repo(url) == expected


def test_happy_path_makes_four_calls_and_returns_the_pr_url():
    fake = Fake([OK_REF, OK_CREATED, OK_CREATED, OK_PR])
    pr = github.open_note_pr(
        request=fake, token="t", url="https://github.com/o/brain-eng.git",
        base="main", path="raw/notes/2026-08-27-x.md", content="hello",
        title="x", body="filed by alice", day="2026-08-27", slug="x")
    assert pr == "https://github.com/o/brain-eng/pull/7"
    assert [c[0] for c in fake.calls] == ["GET", "POST", "PUT", "POST"]
    assert fake.calls[1][2]["ref"] == "refs/heads/intake/2026-08-27-x"


def test_existing_path_retries_with_a_suffix():
    # PUT 422 means the path exists; the branch it was for is abandoned and
    # the retry moves both the branch and the path to -2.
    fake = Fake([OK_REF, OK_CREATED, (422, {}), (204, {}), OK_CREATED,
                 OK_CREATED, OK_PR])
    github.open_note_pr(
        request=fake, token="t", url="https://github.com/o/brain-eng.git",
        base="main", path="raw/notes/2026-08-27-x.md", content="hello",
        title="x", body="b", day="2026-08-27", slug="x")
    puts = [c[1] for c in fake.calls if c[0] == "PUT"]
    assert puts[0].endswith("2026-08-27-x.md")
    assert puts[1].endswith("2026-08-27-x-2.md")
    refs = [c[2]["ref"] for c in fake.calls if c[0] == "POST" and "refs" in c[1]]
    assert refs == ["refs/heads/intake/2026-08-27-x",
                    "refs/heads/intake/2026-08-27-x-2"]


def test_same_day_duplicate_title_succeeds_on_a_suffixed_branch():
    # The common duplicate: the earlier note's branch is still open, so
    # POST git/refs is what collides — not the contents PUT.
    fake = Fake([OK_REF, (422, {"message": "Reference already exists"}),
                 OK_CREATED, OK_CREATED, OK_PR])
    pr = github.open_note_pr(
        request=fake, token="t", url="https://github.com/o/brain-eng.git",
        base="main", path="raw/notes/2026-08-27-x.md", content="hello",
        title="x", body="b", day="2026-08-27", slug="x")
    assert pr == "https://github.com/o/brain-eng/pull/7"
    assert "DELETE" not in [c[0] for c in fake.calls]
    assert fake.calls[2][2]["ref"] == "refs/heads/intake/2026-08-27-x-2"
    assert fake.calls[3][1].endswith("2026-08-27-x-2.md")
    assert fake.calls[3][2]["branch"] == "intake/2026-08-27-x-2"
    assert fake.calls[-1][2]["head"] == "intake/2026-08-27-x-2"


def test_gives_up_after_five_collisions():
    fake = Fake([OK_REF] + [OK_CREATED, (422, {}), (204, {})] * 5)
    with pytest.raises(github.GitHubError) as e:
        github.open_note_pr(
            request=fake, token="t", url="https://github.com/o/brain-eng.git",
            base="main", path="raw/notes/2026-08-27-x.md", content="hello",
            title="x", body="b", day="2026-08-27", slug="x")
    assert "already exists" in str(e.value)


def test_failed_put_deletes_the_branch_it_created():
    fake = Fake([OK_REF, OK_CREATED, (500, {}), (204, {})])
    with pytest.raises(github.GitHubError):
        github.open_note_pr(
            request=fake, token="t", url="https://github.com/o/brain-eng.git",
            base="main", path="raw/notes/2026-08-27-x.md", content="hello",
            title="x", body="b", day="2026-08-27", slug="x")
    assert fake.calls[-1][0] == "DELETE"
    assert fake.calls[-1][1].endswith("refs/heads/intake/2026-08-27-x")


def test_expired_token_surfaces_as_401():
    fake = Fake([(401, {"message": "Bad credentials"})])
    with pytest.raises(github.GitHubError) as e:
        github.open_note_pr(
            request=fake, token="t", url="https://github.com/o/brain-eng.git",
            base="main", path="raw/notes/2026-08-27-x.md", content="hello",
            title="x", body="b", day="2026-08-27", slug="x")
    assert e.value.status == 401
