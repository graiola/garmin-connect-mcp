"""Offline fixture-only checks for the companion skill's distribution boundary."""
import hashlib
import importlib.util
import json
from pathlib import Path
import stat
import sys
import zipfile

import pytest


SPEC = importlib.util.spec_from_file_location(
    "build_agensi_package", Path(__file__).parents[1] / "scripts" / "build_agensi_package.py")
packager = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = packager
SPEC.loader.exec_module(packager)


@pytest.fixture
def repository(tmp_path):
    root = tmp_path / "repository"
    skill = root / "skills" / packager.SKILL_NAME
    for relative in packager.REQUIRED_FILES:
        path = skill / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("[]\n" if relative.endswith(".json") else "Synthetic public documentation.\n")
    (skill / "SKILL.md").write_text(
        f"---\nname: {packager.SKILL_NAME}\ndescription: Read selected Garmin data.\n---\n"
        "# Companion\nUse only the connected read-only tools.\n")
    metadata = root / "docs" / "agensi" / "listing.json"
    metadata.parent.mkdir(parents=True)
    metadata.write_text(json.dumps({
        "version": "0.1.0", "name": "Garmin Connect MCP Assistant", "summary": "Read-only companion.",
        "price_model": "free", "categories": ["Productivity", "Data & Databases"],
    }))
    return root


def skill_path(repository, relative):
    return repository / "skills" / packager.SKILL_NAME / relative


def test_archive_is_reproducible_and_only_contains_allowlisted_text(repository, tmp_path):
    optional = skill_path(repository, "agents/openai.yaml")
    optional.parent.mkdir()
    optional.write_text('interface:\n  display_name: "Companion"\n')
    first, checksum = packager.build_package(repository, tmp_path / "one")
    second, _ = packager.build_package(repository, tmp_path / "two")
    assert first.read_bytes() == second.read_bytes()
    assert checksum.read_text() == f"{hashlib.sha256(first.read_bytes()).hexdigest()}  {first.name}\n"
    with zipfile.ZipFile(first) as archive:
        expected = [f"{packager.SKILL_NAME}/{name}" for name in sorted(packager.REQUIRED_FILES)]
        assert archive.namelist() == expected
        assert archive.testzip() is None
        for info in archive.infolist():
            assert info.date_time == packager.ZIP_TIMESTAMP
            assert info.compress_type == zipfile.ZIP_STORED
            assert stat.S_IMODE(info.external_attr >> 16) == 0o644
            relative = info.filename.removeprefix(f"{packager.SKILL_NAME}/")
            assert archive.read(info) == skill_path(repository, relative).read_bytes()


def test_default_output_and_identical_rebuild_are_safe(repository):
    first = packager.build_package(repository)
    assert first == packager.build_package(repository)
    assert first[0].parent == repository / "dist" / "agensi"


@pytest.mark.parametrize("which", [0, 1])
def test_different_existing_outputs_are_not_overwritten(repository, which):
    outputs = packager.build_package(repository)
    outputs[which].write_bytes(b"Keep this existing content.")
    with pytest.raises(ValueError, match="Refusing to replace"):
        packager.build_package(repository)
    assert outputs[which].read_bytes() == b"Keep this existing content."


@pytest.mark.parametrize("relative", packager.REQUIRED_FILES)
def test_missing_file_rejected(repository, relative):
    skill_path(repository, relative).unlink()
    with pytest.raises(ValueError, match="missing"):
        packager.validate_package(repository)


@pytest.mark.parametrize("relative", [".env", "server.py", "credentials.json", "references/capture.json"])
def test_unexpected_files_rejected(repository, relative):
    skill_path(repository, relative).write_text("Synthetic forbidden addition.\n")
    with pytest.raises(ValueError, match="Unexpected"):
        packager.validate_package(repository)


def test_unexpected_empty_directory_rejected(repository):
    skill_path(repository, "exports").mkdir()
    with pytest.raises(ValueError, match="Unexpected"):
        packager.validate_package(repository)


@pytest.mark.parametrize("payload,match", [(b"\xff", "UTF-8"), (b"text\0text", "NUL")])
def test_non_text_payload_rejected(repository, payload, match):
    skill_path(repository, "references/setup.md").write_bytes(payload)
    with pytest.raises(ValueError, match=match):
        packager.validate_package(repository)


def test_oversized_text_rejected(repository):
    skill_path(repository, "references/setup.md").write_bytes(b"a" * (packager.MAX_TEXT_BYTES + 1))
    with pytest.raises(ValueError, match="exceeds"):
        packager.validate_package(repository)


@pytest.mark.parametrize("relative", ["SKILL.md", "references/setup.md", "agents/openai.yaml"])
def test_file_symlinks_rejected(repository, tmp_path, relative):
    target = tmp_path / "target.md"
    target.write_text("Synthetic external text.\n")
    link = skill_path(repository, relative)
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.exists():
        link.unlink()
    link.symlink_to(target)
    with pytest.raises(ValueError, match="Symlinks"):
        packager.validate_package(repository)


def test_directory_symlink_rejected(repository, tmp_path):
    skill = repository / "skills" / packager.SKILL_NAME
    real = tmp_path / "real-skill"
    skill.rename(real)
    skill.symlink_to(real, target_is_directory=True)
    with pytest.raises(ValueError, match="Symlinks"):
        packager.validate_package(repository)


@pytest.mark.parametrize("frontmatter", [
    "name: wrong\ndescription: Description.",
    f"name: {packager.SKILL_NAME}",
    f"name: {packager.SKILL_NAME}\ndescription:",
    f"name: {packager.SKILL_NAME}\ndescription: null",
    f"name: {packager.SKILL_NAME}\ndescription: yes",
    f"name: {packager.SKILL_NAME}\ndescription: 123",
    f"name: {packager.SKILL_NAME}\ndescription: # comment only",
    f"name: {packager.SKILL_NAME}\ndescription: - sequence item",
    f"name: {packager.SKILL_NAME}\ndescription: bad: unquoted mapping",
    f"name: {packager.SKILL_NAME}\ndescription: unquoted colon:",
    f"name: {packager.SKILL_NAME}\ndescription: !tag content",
    f"name: {packager.SKILL_NAME}\ndescription: >\n  Multiline",
    f"name: {packager.SKILL_NAME}\ndescription: 'unclosed",
    f'name: {packager.SKILL_NAME}\ndescription: "bad" trailing',
    f"name: {packager.SKILL_NAME}\ndescription: First.\ndescription: Second.",
    f"name: {packager.SKILL_NAME}\ndescription: Fine.\nextra: Unsupported.",
])
def test_malformed_frontmatter_rejected(repository, frontmatter):
    skill_path(repository, "SKILL.md").write_text(f"---\n{frontmatter}\n---\n# Instructions\n")
    with pytest.raises(ValueError, match="[Ff]rontmatter"):
        packager.validate_package(repository)


@pytest.mark.parametrize("text", ["# No frontmatter\n", "---\nname: value\n", "---\n---\n"])
def test_absent_or_unclosed_frontmatter_rejected(repository, text):
    skill_path(repository, "SKILL.md").write_text(text)
    with pytest.raises(ValueError, match="[Ff]rontmatter"):
        packager.validate_package(repository)


@pytest.mark.parametrize("description", ['"Description: preserve units."', "'User''s selected activities.'"])
def test_quoted_frontmatter_supported(repository, description):
    skill_path(repository, "SKILL.md").write_text(
        f"---\nname: {packager.SKILL_NAME}\ndescription: {description}\n---\n# Instructions\n")
    assert packager.validate_package(repository).version == "0.1.0"


@pytest.mark.parametrize("key,value", [
    ("version", None), ("version", "../../outside"), ("version", "01.0.0"),
    ("version", "1.0"), ("version", 1), ("name", "x" * 61), ("name", ""),
    ("summary", "x" * 301), ("summary", []), ("price_model", "paid"),
    ("categories", ["a", "b", "c", "d"]), ("categories", "a"),
    ("categories", ["a", "a"]), ("categories", [False]),
    ("skill_name", "another-skill"),
])
def test_invalid_listing_fields_rejected(repository, key, value):
    path = repository / "docs" / "agensi" / "listing.json"
    listing = json.loads(path.read_text())
    listing[key] = value
    path.write_text(json.dumps(listing))
    with pytest.raises(ValueError):
        packager.validate_package(repository)


@pytest.mark.parametrize("text", ["not json", "[]", "null"])
def test_invalid_listing_json_rejected(repository, text):
    (repository / "docs" / "agensi" / "listing.json").write_text(text)
    with pytest.raises(ValueError, match="Listing metadata"):
        packager.validate_package(repository)


def test_invalid_schema_json_rejected(repository):
    skill_path(repository, "references/tool-schemas.json").write_text("not JSON")
    with pytest.raises(ValueError, match="not valid JSON"):
        packager.validate_package(repository)


@pytest.mark.parametrize("directory", [".", "skills", "src", "docs/agensi"])
def test_output_cannot_be_a_source_directory(repository, directory):
    with pytest.raises(ValueError, match="not source directories"):
        packager.build_package(repository, repository / directory)


def test_output_symlink_rejected(repository, tmp_path):
    output = repository / "dist"
    output.symlink_to(tmp_path / "elsewhere", target_is_directory=True)
    with pytest.raises(ValueError, match="Symlinks"):
        packager.build_package(repository)


def test_check_mode_does_not_write_and_reports_validation_errors(repository, monkeypatch, capsys):
    monkeypatch.setattr(packager, "REPOSITORY_ROOT", repository)
    assert packager.main(["--check"]) == 0
    assert "6 text files" in capsys.readouterr().out
    assert not (repository / "dist").exists()
    skill_path(repository, "SKILL.md").unlink()
    assert packager.main(["--check"]) == 2
    assert "Package validation failed" in capsys.readouterr().err
    assert not (repository / "dist").exists()
