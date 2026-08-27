"""Tests for scripts/bundles.py — the shared bundles.yml reader."""
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import bundles  # noqa: E402

CFG = {
    "site_host": "wiki.test",
    "bundles": [
        {"id": "eng", "repo": "https://github.com/o/brain-eng.git"},
        {"id": "hr", "repo": "https://github.com/o/brain-hr.git",
         "readers": ["alice@example.com"]},
    ],
}


def test_load_reads_yaml(tmp_path):
    p = tmp_path / "bundles.yml"
    p.write_text("site_host: wiki.test\nbundles: []\n", encoding="utf-8")
    assert bundles.load(p) == {"site_host": "wiki.test", "bundles": []}


def test_load_empty_file_is_empty_dict(tmp_path):
    p = tmp_path / "bundles.yml"
    p.write_text("", encoding="utf-8")
    assert bundles.load(p) == {}


def test_bundle_without_readers_is_public_to_authenticated_callers():
    assert "eng" in bundles.allowed_ids(CFG, "nobody@example.com")


def test_bundle_with_readers_is_restricted():
    assert bundles.allowed_ids(CFG, "nobody@example.com") == ["eng"]
    assert bundles.allowed_ids(CFG, "alice@example.com") == ["eng", "hr"]


def test_by_id_returns_entry_or_none():
    assert bundles.by_id(CFG, "eng")["repo"].endswith("brain-eng.git")
    assert bundles.by_id(CFG, "nope") is None
