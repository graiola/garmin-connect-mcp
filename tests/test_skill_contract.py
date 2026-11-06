"""Check the shipped companion against the real connector without accessing Garmin."""
import importlib.util
import json
from pathlib import Path, PurePosixPath
import re
import sys
import tomllib
from urllib.parse import unquote, urlsplit
import zipfile

import pytest

from garmin_connect_mcp import __version__
from garmin_connect_mcp.tools import TOOLS


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "garmin-connect-mcp-assistant"
MARKDOWN_FILES = [SKILL / "SKILL.md", *sorted((SKILL / "references").glob("*.md"))]
TOOLS_BY_NAME = {tool.name: tool for tool in TOOLS}
LISTING = json.loads((ROOT / "docs/agensi/listing.json").read_text(encoding="utf-8"))

SPEC = importlib.util.spec_from_file_location("skill_package_builder", ROOT / "scripts/build_agensi_package.py")
packager = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = packager
SPEC.loader.exec_module(packager)


def test_package_version_matches_runtime_version():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert project["project"]["version"] == __version__


def test_saved_schemas_match_all_live_tool_definitions():
    saved = json.loads((SKILL / "references/tool-schemas.json").read_text(encoding="utf-8"))
    assert saved == [tool.definition() for tool in TOOLS]


def test_workflow_call_examples_validate_against_the_live_models():
    text = (SKILL / "references/workflows.md").read_text(encoding="utf-8")
    examples = re.findall(r"^```json\s*\n(.*?)^```", text, flags=re.MULTILINE | re.DOTALL)
    assert examples, "The workflow guide must provide executable input-contract examples."
    for source in examples:
        example = json.loads(source)
        assert set(example) == {"tool", "arguments"}
        assert example["tool"] in TOOLS_BY_NAME
        TOOLS_BY_NAME[example["tool"]].model.model_validate(example["arguments"])


@pytest.mark.parametrize("document", MARKDOWN_FILES, ids=lambda path: path.name)
def test_relative_markdown_links_resolve_inside_the_skill(document):
    text = document.read_text(encoding="utf-8")
    for target in re.findall(r"\[[^\]]+\]\(([^\s)]+)\)", text):
        parsed = urlsplit(target)
        if parsed.scheme or parsed.netloc:
            continue
        destination = (document.parent / unquote(parsed.path)).resolve() if parsed.path else document
        assert destination.is_relative_to(SKILL), f"Escaping link in {document.name}: {target}"
        assert destination.is_file(), f"Broken link in {document.name}: {target}"
        if parsed.fragment and destination.suffix == ".md":
            headings = re.findall(r"^#+\s+(.+)$", destination.read_text(encoding="utf-8"), re.MULTILINE)
            anchors = {re.sub(r"\s+", "-", re.sub(r"[^\w\s-]", "", title.lower())) for title in headings}
            assert unquote(parsed.fragment) in anchors, f"Broken heading link: {target}"


@pytest.mark.parametrize("document", MARKDOWN_FILES, ids=lambda path: path.name)
def test_skill_has_no_unfinished_authoring_scaffolds(document):
    # User-specific example paths are intentional; this catches unfinished authoring markers.
    markers = r"\b(?:TODO|FIXME|TBD)\b|\[INSERT(?:[ _][^\]]*)?\]|<INSERT_[^>]+>|\{\{\s*[A-Za-z_][^}]*\}\}"
    assert not re.search(markers, document.read_text(encoding="utf-8")), document.name


def test_skill_preserves_the_repository_license():
    assert (SKILL / "LICENSE.txt").read_bytes() == (ROOT / "LICENSE").read_bytes()


def test_skill_and_local_ui_metadata_have_consistent_identity():
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    frontmatter = text.split("---\n", 2)[1]
    machine_name = re.search(r"^name: (.+)$", frontmatter, re.MULTILINE).group(1)
    description = re.search(r"^description: (.+)$", frontmatter, re.MULTILINE).group(1)
    # The generated UI fields are JSON-compatible quoted scalars, not general YAML.
    ui = {key: json.loads(value) for key, value in re.findall(
        r'^  (display_name|short_description|default_prompt): (".*")$',
        (SKILL / "agents/openai.yaml").read_text(encoding="utf-8"), re.MULTILINE)}
    assert machine_name == LISTING["skill_name"] == packager.SKILL_NAME
    assert description.strip() and len(description) <= 1024
    assert ui["display_name"] == LISTING["name"]
    assert f"${machine_name}" in ui["default_prompt"]
    assert 25 <= len(ui["short_description"]) <= 64


def test_listing_limits_and_discovery_metadata():
    packager.validate_package(ROOT)
    for key, maximum in (("tags", 10), ("keywords", 10), ("use_cases", 8)):
        values = LISTING[key]
        assert isinstance(values, list) and 1 <= len(values) <= maximum
        assert all(isinstance(value, str) and value.strip() for value in values)
        assert len(set(values)) == len(values)
    assert LISTING["repository_url"] == "https://github.com/graiola/garmin-connect-mcp"
    assert LISTING["license"] == "MIT"
    assert LISTING["needs_access_to"]


@pytest.mark.parametrize("field", ["logo_path", "description_path", "demo_path"])
def test_listing_local_assets_exist_inside_the_repository(field):
    path = (ROOT / LISTING[field]).resolve()
    assert path.is_relative_to(ROOT)
    assert path.is_file()


def test_actual_export_contains_only_the_six_distribution_files(tmp_path):
    archive_path, _ = packager.build_package(ROOT, tmp_path / "package")
    with zipfile.ZipFile(archive_path) as archive:
        expected = {f"{packager.SKILL_NAME}/{name}" for name in packager.REQUIRED_FILES}
        assert set(archive.namelist()) == expected
        assert len(expected) == 6
        for info in archive.infolist():
            assert PurePosixPath(info.filename).suffix in {".md", ".txt", ".json"}
            assert not (info.external_attr >> 16) & 0o111
            archive.read(info).decode("utf-8")


def test_synthetic_demo_input_and_arithmetic():
    demo = json.loads((ROOT / "docs/agensi/demo-input.json").read_text(encoding="utf-8"))
    assert demo["synthetic"] is True
    TOOLS_BY_NAME[demo["tool"]].model.model_validate(demo["arguments"])
    assert demo["result"]["isError"] is False
    records = demo["result"]["structuredContent"]["data"]
    assert len(records) == demo["arguments"]["limit"] == 3
    assert len({record["calendarDate"] for record in records}) == 3
    run, swim, strength = records
    assert all(record["durationUnit"] == "seconds" for record in records)
    assert run["distanceUnit"] == swim["distanceUnit"] == "metres"
    assert run["movingDuration"] / (run["distance"] / 1000) == 310  # 5:10/km.
    assert run["elapsedDuration"] / (run["distance"] / 1000) == 330  # 5:30/km.
    assert swim["movingDuration"] / (swim["distance"] / 100) == 120  # 2:00/100m.
    assert swim["elapsedDuration"] / (swim["distance"] / 100) == 175  # 2:55/100m.
    assert strength["elapsedDuration"] == 45 * 60
    assert "movingDuration" not in strength and "distance" not in strength
