#!/usr/bin/env python3
"""Identify the local project that should map to a ChatGPT Project.

The shareable portion deliberately omits absolute paths and remote URLs. The
local-only portion is intended for a private run receipt or binding registry.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import unicodedata
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlsplit, urlunsplit


SCHEMA = "openai.chatgpt-local-project/v1"
STRONG_MARKERS = (
    ".openai/hosting.json",
    "pyproject.toml",
    "package.json",
    "Cargo.toml",
    "go.mod",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "composer.json",
    "Gemfile",
)
STAGING_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SAFE_LABEL = re.compile(r"[^A-Za-z0-9._ -]+")


class ProjectError(RuntimeError):
    pass


def canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run_git(start: Path, *args: str) -> Optional[str]:
    try:
        result = subprocess.run(
            ["git", "-C", str(start), *args],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def sanitize_remote(remote: str) -> Optional[str]:
    """Normalize a Git remote for hashing without retaining credentials."""
    remote = remote.strip()
    if not remote:
        return None
    scp = re.fullmatch(r"(?:[^@/\s]+@)?([^:/\s]+):(.+)", remote)
    if scp and "://" not in remote:
        host = scp.group(1).lower()
        path = scp.group(2).strip("/").removesuffix(".git")
        return f"git://{host}/{path.casefold()}"
    try:
        parsed = urlsplit(remote)
    except ValueError:
        return None
    if not parsed.scheme or not parsed.hostname:
        return None
    host = parsed.hostname.lower()
    port = f":{parsed.port}" if parsed.port else ""
    path = parsed.path.strip("/").removesuffix(".git").casefold()
    return urlunsplit(("git", f"{host}{port}", f"/{path}", "", ""))


def safe_label(value: str, fallback: str) -> str:
    value = unicodedata.normalize("NFC", value)
    value = SAFE_LABEL.sub(" ", value)
    value = re.sub(r"\s+", " ", value).strip(" .-_")
    return (value[:64] or fallback).strip()


def parse_manifest_name(marker: Path) -> Optional[str]:
    try:
        if marker.name == "package.json":
            value = json.loads(marker.read_text(encoding="utf-8"))
            name = value.get("name")
            return str(name) if isinstance(name, str) and name.strip() else None
        if marker.name == "pyproject.toml":
            try:
                import tomllib  # Python 3.11+
            except ImportError:
                return None
            value = tomllib.loads(marker.read_text(encoding="utf-8"))
            project = value.get("project", {})
            name = project.get("name") if isinstance(project, dict) else None
            if not name:
                poetry = value.get("tool", {}).get("poetry", {})
                name = poetry.get("name") if isinstance(poetry, dict) else None
            return str(name) if isinstance(name, str) and name.strip() else None
        if marker.name == "Cargo.toml":
            try:
                import tomllib
            except ImportError:
                return None
            value = tomllib.loads(marker.read_text(encoding="utf-8"))
            package = value.get("package", {})
            name = package.get("name") if isinstance(package, dict) else None
            return str(name) if isinstance(name, str) and name.strip() else None
        if marker.name == "go.mod":
            first = marker.read_text(encoding="utf-8").splitlines()[0].strip()
            if first.startswith("module "):
                return first.split("/")[-1].removesuffix(".git")
        if marker.name == "hosting.json" and marker.parent.name == ".openai":
            value = json.loads(marker.read_text(encoding="utf-8"))
            for key in ("name", "project_name", "project_id"):
                name = value.get(key)
                if isinstance(name, str) and name.strip():
                    return name
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, IndexError):
        return None
    return None


def nearest_manifest(start: Path, stop: Optional[Path] = None) -> tuple[Optional[Path], Optional[Path]]:
    current = start
    while True:
        for marker_name in STRONG_MARKERS:
            marker = current / Path(marker_name)
            if marker.is_file():
                return current, marker
        solutions = sorted(current.glob("*.sln"), key=lambda p: p.name.casefold())
        if solutions:
            return current, solutions[0]
        if stop is not None and current == stop:
            break
        if current.parent == current:
            break
        current = current.parent
    return None, None


def is_codex_staging(path: Path) -> bool:
    parts = [part.casefold() for part in path.parts]
    for index in range(len(parts) - 3):
        if (
            parts[index] == "documents"
            and parts[index + 1] == "codex"
            and STAGING_DATE.fullmatch(path.parts[index + 2])
        ):
            return True
    return False


def relative_component(start: Path, git_root: Path) -> tuple[Optional[Path], Optional[Path]]:
    component_root, marker = nearest_manifest(start, git_root)
    if component_root is None or component_root == git_root:
        return None, marker
    try:
        component_root.relative_to(git_root)
    except ValueError:
        return None, marker
    return component_root, marker


def identify(
    start_arg: str, task_label: Optional[str], project_label: Optional[str]
) -> dict[str, Any]:
    raw = Path(start_arg).expanduser()
    if not raw.exists():
        raise ProjectError(f"start path does not exist: {raw}")
    start = raw.resolve(strict=True)
    if start.is_file():
        start = start.parent
    if not start.is_dir():
        raise ProjectError("start path must resolve to a file or directory")

    git_root_text = run_git(start, "rev-parse", "--show-toplevel")
    git_root = (
        Path(git_root_text).resolve(strict=True)
        if git_root_text and Path(git_root_text).exists()
        else None
    )

    local: dict[str, Any] = {
        "start_path": str(start),
        "root": None,
        "component_root": None,
        "git": None,
    }
    shareable: dict[str, Any]
    identity_material: dict[str, Any]

    if git_root is not None:
        component_root, marker = relative_component(start, git_root)
        remote_names_text = run_git(git_root, "remote") or ""
        remote_names = sorted(
            {name.strip() for name in remote_names_text.splitlines() if name.strip()},
            key=str.casefold,
        )
        preferred_remote = (
            "origin"
            if "origin" in remote_names
            else (remote_names[0] if remote_names else None)
        )
        remote_raw = (
            run_git(git_root, "remote", "get-url", preferred_remote)
            if preferred_remote
            else None
        )
        remote_normalized = sanitize_remote(remote_raw or "")
        remote_hash = (
            sha256_bytes(remote_normalized.encode("utf-8"))
            if remote_normalized
            else None
        )
        commit = run_git(git_root, "rev-parse", "HEAD")
        branch = run_git(git_root, "branch", "--show-current")
        common_dir = run_git(git_root, "rev-parse", "--git-common-dir")
        if common_dir:
            common_path = Path(common_dir)
            if not common_path.is_absolute():
                common_path = git_root / common_path
            common_path = common_path.resolve()
        else:
            common_path = git_root
        dirty = bool(run_git(git_root, "status", "--porcelain"))
        parsed_name = parse_manifest_name(marker) if marker else None
        fallback_name = (
            marker.stem
            if marker is not None and marker.suffix.casefold() == ".sln"
            else (component_root or git_root).name
        )
        name = safe_label(project_label or parsed_name or fallback_name, "Project")
        component_relative = (
            component_root.relative_to(git_root).as_posix()
            if component_root is not None
            else None
        )
        identity_material = {
            "kind": "git",
            "remote_identity_sha256": remote_hash,
            "fallback_root_sha256": None
            if remote_hash
            else sha256_bytes(os.path.normcase(str(common_path)).encode("utf-8")),
            "component": component_relative,
        }
        shareable = {
            "kind": "git",
            "name": name,
            "component_identity_sha256": (
                sha256_bytes(component_relative.casefold().encode("utf-8"))
                if component_relative
                else None
            ),
            "remote_identity_sha256": remote_hash,
            "identity_basis": [
                "normalized_git_remote_hash" if remote_hash else "local_root_hash",
                *([] if component_relative is None else ["monorepo_component"]),
            ],
            "confidence": "high",
            "projectless_reason": None,
        }
        local.update(
            {
                "root": str(git_root),
                "component_root": str(component_root) if component_root else None,
                "component_relative": component_relative,
                "git": {
                    "head": commit,
                    "branch": branch or None,
                    "dirty": dirty,
                    "common_dir": common_dir,
                    "remote_configured": bool(remote_raw),
                    "remote_count": len(remote_names),
                    "identity_remote": preferred_remote,
                },
            }
        )
    else:
        workspace_root, marker = nearest_manifest(start)
        staging = is_codex_staging(start)
        if workspace_root is not None and not staging:
            parsed_name = parse_manifest_name(marker) if marker else None
            workspace_fallback = (
                marker.stem
                if marker is not None and marker.suffix.casefold() == ".sln"
                else workspace_root.name
            )
            name = safe_label(
                project_label or parsed_name or workspace_fallback, "Project"
            )
            marker_name = marker.relative_to(workspace_root).as_posix() if marker else None
            identity_material = {
                "kind": "workspace",
                "root_sha256": sha256_bytes(
                    os.path.normcase(str(workspace_root)).encode("utf-8")
                ),
                "marker": marker_name,
            }
            shareable = {
                "kind": "workspace",
                "name": name,
                "component_identity_sha256": None,
                "remote_identity_sha256": None,
                "identity_basis": ["local_root_hash", f"marker:{marker_name}"],
                "confidence": "medium",
                "projectless_reason": None,
            }
            local["root"] = str(workspace_root)
        else:
            fallback_name = project_label or task_label or start.name or "Codex Task"
            name = safe_label(fallback_name, "Codex Task")
            reason = (
                "codex_projectless_staging"
                if staging
                else "no_git_or_strong_workspace_marker"
            )
            identity_material = {
                "kind": "projectless",
                "task_label": name.casefold(),
                "staging_root_sha256": sha256_bytes(
                    os.path.normcase(str(start)).encode("utf-8")
                ),
            }
            shareable = {
                "kind": "projectless",
                "name": name,
                "component_identity_sha256": None,
                "remote_identity_sha256": None,
                "identity_basis": ["task_label", "local_staging_hash"],
                "confidence": "high",
                "projectless_reason": reason,
            }
            local["root"] = str(start)

    fingerprint = sha256_bytes(canonical_json(identity_material))
    shareable["fingerprint"] = fingerprint
    if shareable["kind"] == "projectless":
        suggested = f"Codex Task - {shareable['name']} [{fingerprint[:8]}]"
    else:
        suggested = f"{shareable['name']} [{fingerprint[:8]}]"
    shareable["suggested_chatgpt_project_name"] = suggested[:100]

    return {
        "schema": SCHEMA,
        "shareable": shareable,
        "local_only": local,
        "routing": {
            "primary_project_detected": shareable["kind"] != "projectless",
            "privacy_partition": "private",
            "binding_registry": "~/.codex/state/chatgpt-sol-pro-chrome/project-bindings.json",
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Identify a task's local project without exposing local paths."
    )
    parser.add_argument(
        "--start",
        default=os.getcwd(),
        help="Explicit task file/folder or active workspace (default: cwd).",
    )
    parser.add_argument(
        "--task-label",
        help="Privacy-safe label used only when no project is detected.",
    )
    parser.add_argument(
        "--project-label",
        help="Privacy-safe display label that overrides detected manifest/repo names.",
    )
    parser.add_argument(
        "--output",
        help="Optional new JSON output path. Existing files are never overwritten.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = identify(args.start, args.task_label, args.project_label)
        rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
        if args.output:
            output = Path(args.output).expanduser().resolve()
            if output.exists():
                raise ProjectError(f"refusing to overwrite output: {output}")
            output.parent.mkdir(parents=True, exist_ok=True)
            with output.open("x", encoding="utf-8", newline="\n") as handle:
                handle.write(rendered)
        else:
            sys.stdout.write(rendered)
        return 0
    except (ProjectError, OSError, ValueError) as exc:
        sys.stderr.write(
            json.dumps({"status": "BLOCKED", "error": str(exc)}, ensure_ascii=False)
            + "\n"
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
