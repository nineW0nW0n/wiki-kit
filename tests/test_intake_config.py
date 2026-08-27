"""Tests for intake/config.py — intake.yml parsing and its refusals."""
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "intake"))

import config  # noqa: E402


def write(tmp_path: Path, text: str) -> Path:
    (tmp_path / "intake.yml").write_text(text, encoding="utf-8")
    return tmp_path


def test_missing_file_yields_default_form(tmp_path):
    form = config.load(tmp_path)
    assert [f.name for f in form.fields] == ["body"]
    assert form.fields[0].type == "textarea"
    assert form.kinds == list(config.KINDS)


def test_fields_are_parsed_in_order(tmp_path):
    d = write(tmp_path, """
title: "Drop a note"
fields:
  - name: summary
    label: "What happened?"
    type: textarea
    required: true
    into: body
  - name: system
    label: "Which system?"
    type: select
    options: [mail-01, db-01]
    into: frontmatter
""")
    form = config.load(d)
    assert form.title == "Drop a note"
    assert [f.name for f in form.fields] == ["summary", "system"]
    assert form.fields[0].required is True
    assert form.fields[1].options == ["mail-01", "db-01"]
    assert form.fields[1].into == "frontmatter"


def test_scalar_kind_pins_the_directory(tmp_path):
    d = write(tmp_path, "kind: meeting\nfields: []\n")
    assert config.load(d).kinds == ["meeting"]


def test_list_kind_limits_the_selector(tmp_path):
    d = write(tmp_path, "kind: [note, meeting]\nfields: []\n")
    assert config.load(d).kinds == ["note", "meeting"]


def test_unknown_kind_is_rejected(tmp_path):
    d = write(tmp_path, "kind: gossip\nfields: []\n")
    with pytest.raises(config.ConfigError) as e:
        config.load(d)
    assert "gossip" in str(e.value)


@pytest.mark.parametrize("name", ["type", "kind", "author", "date",
                                  "classification", "status"])
def test_reserved_field_names_are_rejected(tmp_path, name):
    d = write(tmp_path, f"fields:\n  - name: {name}\n    label: X\n    type: text\n")
    with pytest.raises(config.ConfigError) as e:
        config.load(d)
    assert name in str(e.value)
    assert "reserved" in str(e.value)


def test_unknown_field_type_is_rejected(tmp_path):
    d = write(tmp_path, "fields:\n  - name: x\n    label: X\n    type: colorpicker\n")
    with pytest.raises(config.ConfigError) as e:
        config.load(d)
    assert "colorpicker" in str(e.value)


def test_select_without_options_is_rejected(tmp_path):
    d = write(tmp_path, "fields:\n  - name: x\n    label: X\n    type: select\n")
    with pytest.raises(config.ConfigError) as e:
        config.load(d)
    assert "options" in str(e.value)


def test_malformed_yaml_is_a_config_error_not_a_traceback(tmp_path):
    d = write(tmp_path, "fields: [oh: no: yes\n")
    with pytest.raises(config.ConfigError):
        config.load(d)


def test_duplicate_field_names_are_rejected(tmp_path):
    d = write(tmp_path, """
fields:
  - name: x
    label: One
    type: text
  - name: x
    label: Two
    type: text
""")
    with pytest.raises(config.ConfigError) as e:
        config.load(d)
    assert "duplicate" in str(e.value)
