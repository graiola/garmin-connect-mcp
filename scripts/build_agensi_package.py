#!/usr/bin/env python3
"""Validate and reproducibly package the text-only companion skill, without network access.

Only explicitly listed files are exported. Review those files for private data before
submission; a packaging allowlist cannot detect every secret embedded in prose.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import io
import json
from pathlib import Path
import re
import stat
import sys
import zipfile


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SKILL_NAME = "garmin-connect-mcp-assistant"
REQUIRED_FILES = (
    "LICENSE.txt",
    "SKILL.md",
    "references/setup.md",
    "references/tool-contracts.md",
    "references/tool-schemas.json",
    "references/workflows.md",
)
OPTIONAL_FILES = {"agents/openai.yaml"}  # Local UI metadata, not marketplace content.
MAX_TEXT_BYTES = 512 * 1024
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


@dataclass(frozen=True)
class Package:
    version: str
    files: tuple[tuple[str, bytes], ...]


def _reject_symlinks(path: Path) -> None:
    for component in (path, *path.parents):
        if component.is_symlink():
            raise ValueError(f"Symlinks are not allowed: {component}")


def _read_text(path: Path) -> tuple[str, bytes]:
    _reject_symlinks(path)
    if not path.is_file():
        raise ValueError(f"Required regular file is missing: {path}")
    if path.stat().st_size > MAX_TEXT_BYTES:
        raise ValueError(f"Text file exceeds {MAX_TEXT_BYTES} bytes: {path}")
    payload = path.read_bytes()
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError(f"File is not UTF-8 text: {path}") from None
    if "\0" in text:
        raise ValueError(f"NUL bytes are not allowed in text files: {path}")
    return text, payload


def _scalar(value: str) -> str:
    """Accept the deliberately small single-line YAML subset used by this skill."""
    if value.startswith('"'):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            raise ValueError("Malformed quoted frontmatter string.") from None
        if not isinstance(parsed, str):
            raise ValueError("Frontmatter fields must be strings.")
        return parsed
    if value.startswith("'"):
        if not re.fullmatch(r"'(?:[^']|'')*'", value):
            raise ValueError("Malformed quoted frontmatter string.")
        return value[1:-1].replace("''", "'")
    if (not re.match(r"[A-Za-z]", value) or re.search(r":(?:\s|$)|\s#", value)
            or value.lower() in {"true", "false", "yes", "no", "on", "off", "null"}):
        raise ValueError("Use plain or quoted single-line string frontmatter.")
    return value


def _validate_frontmatter(text: str) -> None:
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        raise ValueError("SKILL.md must start with YAML frontmatter.")
    try:
        end = lines.index("---", 1)
    except ValueError:
        raise ValueError("SKILL.md frontmatter has no closing delimiter.") from None
    fields = {}
    for line in lines[1:end]:
        match = re.fullmatch(r"(name|description):[ \t]*(.+)", line)
        if not match or match[1] in fields:
            raise ValueError("Frontmatter requires name and description exactly once.")
        fields[match[1]] = _scalar(match[2].strip())
    if fields.get("name") != SKILL_NAME:
        raise ValueError(f"Frontmatter name must be {SKILL_NAME}.")
    description = fields.get("description", "")
    if (not description.strip() or len(description) > 1024
            or "\n" in description or "\r" in description):
        raise ValueError("Frontmatter description must be a non-empty single-line string.")
    if not "\n".join(lines[end + 1:]).strip():
        raise ValueError("SKILL.md needs instructions after its frontmatter.")


def _validate_listing(text: str) -> str:
    try:
        listing = json.loads(text)
    except json.JSONDecodeError:
        raise ValueError("Listing metadata must be valid JSON.") from None
    if not isinstance(listing, dict):
        raise ValueError("Listing metadata must be a JSON object.")
    version = listing.get("version")
    if not isinstance(version, str) or not re.fullmatch(
            r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)", version):
        raise ValueError("Listing version must be X.Y.Z without leading zeros.")
    for field, limit in (("name", 60), ("summary", 300)):
        value = listing.get(field)
        if not isinstance(value, str) or not value.strip() or len(value) > limit:
            raise ValueError(f"Listing {field} must be 1–{limit} characters.")
    if listing.get("price_model") != "free":
        raise ValueError("This launch package must use the free price model.")
    categories = listing.get("categories", [])
    if (not isinstance(categories, list) or len(categories) > 3
            or any(not isinstance(value, str) or not value.strip() for value in categories)
            or len(set(categories)) != len(categories)):
        raise ValueError("Listing categories must be up to three distinct non-empty strings.")
    if listing.get("skill_name", SKILL_NAME) != SKILL_NAME:
        raise ValueError("Listing skill_name does not match the package.")
    return version


def validate_package(repository_root: Path = REPOSITORY_ROOT) -> Package:
    """Read an exact, text-only export set; reject extra files instead of ignoring them."""
    repository_root = Path(repository_root).absolute()
    skill_root = repository_root / "skills" / SKILL_NAME
    _reject_symlinks(skill_root)
    if not skill_root.is_dir():
        raise ValueError(f"Skill directory is missing: {skill_root}")
    allowed_files = set(REQUIRED_FILES) | OPTIONAL_FILES
    allowed_directories = {"references", "agents"}
    for path in sorted(skill_root.rglob("*")):
        relative = path.relative_to(skill_root).as_posix()
        _reject_symlinks(path)
        if path.is_dir() and relative in allowed_directories:
            continue
        if not path.is_file() or relative not in allowed_files:
            raise ValueError(f"Unexpected skill file or directory: {relative}")
        if relative in OPTIONAL_FILES:
            _read_text(path)
    contents = []
    for relative in REQUIRED_FILES:
        text, payload = _read_text(skill_root / relative)
        if relative == "SKILL.md":
            _validate_frontmatter(text)
        elif relative.endswith(".json"):
            try:
                json.loads(text)
            except json.JSONDecodeError:
                raise ValueError(f"File is not valid JSON: {relative}") from None
        contents.append((relative, payload))
    listing_text, _ = _read_text(repository_root / "docs" / "agensi" / "listing.json")
    return Package(_validate_listing(listing_text), tuple(contents))


def _archive_bytes(package: Package) -> bytes:
    buffer = io.BytesIO()
    # Stored entries avoid zlib-version differences and keep this small package reproducible.
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
        for relative, payload in sorted(package.files):
            info = zipfile.ZipInfo(f"{SKILL_NAME}/{relative}", ZIP_TIMESTAMP)
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            archive.writestr(info, payload)
    return buffer.getvalue()


def build_package(repository_root: Path = REPOSITORY_ROOT,
                  output_dir: Path | None = None) -> tuple[Path, Path]:
    """Write a ZIP and checksum; reuse identical outputs but never replace other content."""
    repository_root = Path(repository_root).absolute()
    package = validate_package(repository_root)
    output_dir = Path(output_dir or repository_root / "dist" / "agensi").absolute()
    _reject_symlinks(output_dir)
    resolved_root = repository_root.resolve()
    resolved_output = output_dir.resolve()
    if (resolved_output.is_relative_to(resolved_root)
            and not resolved_output.is_relative_to(resolved_root / "dist")):
        raise ValueError("Output inside the repository must be under dist, not source directories.")
    archive_path = output_dir / f"{SKILL_NAME}-{package.version}.zip"
    archive_bytes = _archive_bytes(package)
    checksum_path = archive_path.with_suffix(".zip.sha256")
    digest = hashlib.sha256(archive_bytes).hexdigest()
    outputs = ((archive_path, archive_bytes),
               (checksum_path, f"{digest}  {archive_path.name}\n".encode("ascii")))
    for path, payload in outputs:
        _reject_symlinks(path)
        if path.exists() and (not path.is_file() or path.read_bytes() != payload):
            raise ValueError(f"Refusing to replace different existing output: {path}")
    output_dir.mkdir(parents=True, exist_ok=True)
    for path, payload in outputs:
        if not path.exists():
            with path.open("xb") as stream:
                stream.write(payload)
    return archive_path, checksum_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Validate inputs without writing files.")
    parser.add_argument("--output-dir", type=Path, help="Output directory (default: repository/dist/agensi).")
    args = parser.parse_args(argv)
    try:
        if args.check:
            package = validate_package(REPOSITORY_ROOT)
            print(f"Validated {SKILL_NAME} {package.version}: {len(package.files)} text files.")
        else:
            archive, checksum = build_package(REPOSITORY_ROOT, args.output_dir)
            print(f"Created or verified {archive}\nChecksum: {checksum}")
    except (OSError, ValueError) as exc:
        print(f"Package validation failed: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
