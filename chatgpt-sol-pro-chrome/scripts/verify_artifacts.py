#!/usr/bin/env python3
"""Verify ChatGPT-downloaded files, directories, and ZIP packages."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


MANIFEST_NAMES = ("run_manifest.json", "manifest.json", "artifact_manifest.json")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalize_name(name: str) -> str:
    value = name.replace("\\", "/")
    while value.startswith("./"):
        value = value[2:]
    return value


def safe_member_name(name: str) -> bool:
    if "\\" in name or re.match(r"^[A-Za-z]:", name):
        return False
    path = PurePosixPath(name)
    return bool(name) and not path.is_absolute() and ".." not in path.parts


class Reader:
    kind = "unknown"

    def names(self) -> list[str]:
        raise NotImplementedError

    def read(self, name: str) -> bytes:
        raise NotImplementedError

    def close(self) -> None:
        return None


class ZipReader(Reader):
    kind = "zip"

    def __init__(self, path: Path, errors: list[str]) -> None:
        self.path = path
        self.archive = zipfile.ZipFile(path)
        raw_names = [info.filename for info in self.archive.infolist() if not info.is_dir()]
        unsafe = sorted(name for name in raw_names if not safe_member_name(name))
        if unsafe:
            errors.append(f"unsafe ZIP member names: {unsafe}")
        duplicates = sorted({name for name in raw_names if raw_names.count(name) > 1})
        if duplicates:
            errors.append(f"duplicate ZIP members: {duplicates}")
        self._members: dict[str, str] = {}
        for raw_name in raw_names:
            if not safe_member_name(raw_name):
                continue
            normalized = normalize_name(raw_name)
            if normalized in self._members:
                errors.append(
                    f"duplicate normalized ZIP member: {normalized} "
                    f"({self._members[normalized]!r}, {raw_name!r})"
                )
                continue
            self._members[normalized] = raw_name
        bad_crc = self.archive.testzip()
        if bad_crc:
            errors.append(f"ZIP CRC failure: {bad_crc}")

    def names(self) -> list[str]:
        return sorted(self._members)

    def read(self, name: str) -> bytes:
        return self.archive.read(self._members[normalize_name(name)])

    def close(self) -> None:
        self.archive.close()


class DirectoryReader(Reader):
    kind = "directory"

    def __init__(self, path: Path) -> None:
        self.path = path.resolve()
        self._paths = {
            normalize_name(item.relative_to(self.path).as_posix()): item
            for item in self.path.rglob("*")
            if item.is_file()
        }

    def names(self) -> list[str]:
        return sorted(self._paths)

    def read(self, name: str) -> bytes:
        return self._paths[normalize_name(name)].read_bytes()


class SingleFileReader(Reader):
    kind = "file"

    def __init__(self, path: Path) -> None:
        self.path = path.resolve()
        self.name = self.path.name

    def names(self) -> list[str]:
        return [self.name]

    def read(self, name: str) -> bytes:
        if normalize_name(name) != self.name:
            raise KeyError(name)
        return self.path.read_bytes()


def build_reader(path: Path, errors: list[str]) -> Reader:
    if path.is_dir():
        return DirectoryReader(path)
    if zipfile.is_zipfile(path):
        return ZipReader(path, errors)
    return SingleFileReader(path)


def load_json(data: bytes, label: str, errors: list[str]) -> Any | None:
    try:
        return json.loads(data.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        errors.append(f"invalid JSON in {label}: {exc}")
        return None


def discover_manifest(
    reader: Reader, target: Path, requested: str | None, errors: list[str]
) -> tuple[str | None, dict[str, Any] | None]:
    names = reader.names()
    if requested:
        external = Path(requested)
        if external.is_file():
            data = external.read_bytes()
            label = str(external.resolve())
        else:
            member = normalize_name(requested)
            if member not in names:
                errors.append(f"manifest not found: {requested}")
                return None, None
            data = reader.read(member)
            label = member
        value = load_json(data, label, errors)
        if value is not None and not isinstance(value, dict):
            errors.append(f"manifest root must be an object: {label}")
            return label, None
        return label, value

    if reader.kind == "file":
        return None, None

    candidates: list[str] = []
    for preferred in MANIFEST_NAMES:
        exact = [name for name in names if name == preferred]
        nested = [name for name in names if PurePosixPath(name).name == preferred]
        candidates.extend(exact or nested)
        if candidates:
            break
    candidates = sorted(set(candidates))
    if len(candidates) > 1:
        errors.append(f"ambiguous manifest discovery: {candidates}")
        return None, None
    if not candidates:
        return None, None
    label = candidates[0]
    value = load_json(reader.read(label), label, errors)
    if value is not None and not isinstance(value, dict):
        errors.append(f"manifest root must be an object: {label}")
        return label, None
    return label, value


def first_value(mapping: dict[str, Any], keys: Iterable[str]) -> Any | None:
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return None


def manifest_entries(manifest: dict[str, Any] | None, errors: list[str]) -> list[dict[str, Any]]:
    if not manifest:
        return []
    raw_entries: list[dict[str, Any]] = []
    for key in ("files", "artifacts"):
        value = manifest.get(key)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    raw_entries.append({"name": item})
                elif isinstance(item, dict):
                    raw_entries.append(dict(item))
    output_files = manifest.get("output_files")
    if isinstance(output_files, dict):
        for name, metadata in output_files.items():
            entry = dict(metadata) if isinstance(metadata, dict) else {}
            entry.setdefault("name", name)
            raw_entries.append(entry)

    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in raw_entries:
        name = first_value(entry, ("name", "path", "file", "filename"))
        if not isinstance(name, str) or not name:
            errors.append(f"manifest file entry has no usable name: {entry}")
            continue
        if not safe_member_name(name):
            errors.append(f"unsafe manifest file name: {name}")
            continue
        normalized_name = normalize_name(name)
        if normalized_name in seen:
            errors.append(f"duplicate manifest file entry: {normalized_name}")
            continue
        seen.add(normalized_name)
        entry["name"] = normalized_name
        normalized.append(entry)
    return normalized


def expected_hash(entry: dict[str, Any]) -> str | None:
    value = first_value(entry, ("sha256", "sha_256", "hash"))
    if not isinstance(value, str):
        return None
    value = value.lower().removeprefix("sha256:")
    return value if re.fullmatch(r"[0-9a-f]{64}", value) else None


def expected_int(entry: dict[str, Any], keys: Iterable[str]) -> int | None:
    value = first_value(entry, keys)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def validate_jsonl(
    data: bytes, name: str, entry: dict[str, Any], errors: list[str]
) -> dict[str, Any]:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        errors.append(f"invalid UTF-8 in {name}: {exc}")
        return {}
    rows: list[Any] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            errors.append(f"invalid JSONL in {name}:{line_number}: {exc}")
    expected = expected_int(entry, ("line_count", "records", "rows", "row_count"))
    if expected is not None and len(rows) != expected:
        errors.append(f"JSONL row count mismatch for {name}: expected {expected}, got {len(rows)}")
    unique_key = first_value(entry, ("unique_key", "id_field"))
    if isinstance(unique_key, str) and unique_key:
        values: list[Any] = []
        for index, row in enumerate(rows, start=1):
            if not isinstance(row, dict) or unique_key not in row:
                errors.append(f"missing unique key {unique_key!r} in {name}:{index}")
                continue
            values.append(row[unique_key])
        if len(values) != len({json.dumps(value, sort_keys=True) for value in values}):
            errors.append(f"duplicate values for unique key {unique_key!r} in {name}")
    return {"rows": len(rows), "unique_key": unique_key}


def validate_csv(
    data: bytes, name: str, entry: dict[str, Any], errors: list[str]
) -> dict[str, Any]:
    try:
        text = data.decode("utf-8-sig")
        rows = list(csv.reader(io.StringIO(text)))
    except (UnicodeDecodeError, csv.Error) as exc:
        errors.append(f"invalid CSV in {name}: {exc}")
        return {}
    data_rows = max(0, len(rows) - 1)
    expected = expected_int(entry, ("row_count", "rows", "records"))
    if expected is not None and data_rows != expected:
        errors.append(f"CSV row count mismatch for {name}: expected {expected}, got {data_rows}")
    return {"rows": data_rows, "columns": len(rows[0]) if rows else 0}


def validate_type(
    data: bytes, name: str, entry: dict[str, Any], errors: list[str]
) -> dict[str, Any]:
    lower = name.lower()
    if lower.endswith(".json"):
        value = load_json(data, name, errors)
        return {"json_type": type(value).__name__ if value is not None else None}
    if lower.endswith(".jsonl"):
        return validate_jsonl(data, name, entry, errors)
    if lower.endswith(".csv"):
        return validate_csv(data, name, entry, errors)
    if lower.endswith(".pdf"):
        if not data.startswith(b"%PDF-") or b"%%EOF" not in data[-4096:]:
            errors.append(f"invalid or incomplete PDF signature: {name}")
    elif lower.endswith(".png") and not data.startswith(b"\x89PNG\r\n\x1a\n"):
        errors.append(f"invalid PNG signature: {name}")
    elif lower.endswith((".jpg", ".jpeg")) and not (
        data.startswith(b"\xff\xd8") and data.endswith(b"\xff\xd9")
    ):
        errors.append(f"invalid JPEG signature: {name}")
    elif lower.endswith(".zip"):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                bad_crc = archive.testzip()
                if bad_crc:
                    errors.append(f"ZIP CRC failure in {name}: {bad_crc}")
        except zipfile.BadZipFile as exc:
            errors.append(f"invalid ZIP container {name}: {exc}")
    return {}


def required_from_manifest(manifest: dict[str, Any] | None) -> list[str]:
    if not manifest:
        return []
    value = first_value(manifest, ("required_files", "required"))
    if not isinstance(value, list):
        return []
    return [normalize_name(item) for item in value if isinstance(item, str)]


def verify(args: argparse.Namespace) -> dict[str, Any]:
    target = Path(args.target)
    errors: list[str] = []
    warnings: list[str] = []
    checked: list[dict[str, Any]] = []
    if not target.exists():
        return {
            "ok": False,
            "target": str(target),
            "errors": [f"target not found: {target}"],
            "warnings": [],
            "checked_files": [],
        }

    reader = build_reader(target, errors)
    try:
        names = reader.names()
        manifest_label, manifest = discover_manifest(
            reader, target, args.manifest, errors
        )
        entries = manifest_entries(manifest, errors)
        entry_map = {entry["name"]: entry for entry in entries}
        required: set[str] = set()
        for raw_name in [*args.required, *required_from_manifest(manifest)]:
            if not safe_member_name(raw_name):
                errors.append(f"unsafe required file name: {raw_name}")
                continue
            required.add(normalize_name(raw_name))
        for name in sorted(required):
            if name not in names:
                errors.append(f"required file missing: {name}")

        to_check = set(entry_map) | required
        if not to_check:
            to_check = set(names)
            if reader.kind != "file":
                warnings.append("no manifest entries or required files; checked all files")

        for name in sorted(to_check):
            if name not in names:
                if name in entry_map:
                    errors.append(f"manifest file missing: {name}")
                continue
            data = reader.read(name)
            entry = entry_map.get(name, {})
            expected_bytes = expected_int(entry, ("bytes", "size", "size_bytes"))
            actual_hash = sha256_bytes(data)
            declared_hash = expected_hash(entry)
            if expected_bytes is not None and len(data) != expected_bytes:
                errors.append(
                    f"byte count mismatch for {name}: expected {expected_bytes}, got {len(data)}"
                )
            if declared_hash is not None and actual_hash != declared_hash:
                errors.append(
                    f"SHA-256 mismatch for {name}: expected {declared_hash}, got {actual_hash}"
                )
            details = validate_type(data, name, entry, errors)
            checked.append(
                {
                    "name": name,
                    "bytes": len(data),
                    "sha256": actual_hash,
                    **details,
                }
            )

        if manifest is None and args.manifest:
            errors.append("requested manifest could not be loaded")
        return {
            "ok": not errors,
            "target": str(target.resolve()),
            "container": reader.kind,
            "manifest": manifest_label,
            "checked_files": checked,
            "errors": errors,
            "warnings": warnings,
        }
    finally:
        reader.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify a downloaded artifact, directory, or ZIP package."
    )
    parser.add_argument("target", help="Downloaded file, directory, or ZIP path")
    parser.add_argument(
        "--manifest",
        help="Manifest member name or external manifest path; auto-detected when omitted",
    )
    parser.add_argument(
        "--required",
        action="append",
        default=[],
        help="Required relative file/member name; repeat as needed",
    )
    parser.add_argument("--report", help="Write the JSON validation report to this path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = verify(args)
    rendered = json.dumps(report, indent=2, ensure_ascii=False)
    print(rendered)
    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(rendered + "\n", encoding="utf-8")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
