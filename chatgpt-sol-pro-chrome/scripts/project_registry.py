#!/usr/bin/env python3
"""Maintain private local bindings between local and ChatGPT Projects."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


SCHEMA = "openai.chatgpt-project-bindings/v1"
DEFAULT_REGISTRY = (
    Path.home()
    / ".codex"
    / "state"
    / "chatgpt-sol-pro-chrome"
    / "project-bindings.json"
)
FINGERPRINT = re.compile(r"^[0-9a-f]{64}$")


class RegistryError(RuntimeError):
    pass


def now_utc() -> str:
    return (
        dt.datetime.now(dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RegistryError(f"cannot read JSON {path}: {exc}") from exc


def load_identity(path: Path) -> dict[str, Any]:
    value = load_json(path)
    if not isinstance(value, dict):
        raise RegistryError("identity file must contain an object")
    shareable = value.get("shareable")
    if not isinstance(shareable, dict):
        raise RegistryError("identity file is missing shareable identity")
    fingerprint = shareable.get("fingerprint")
    if not isinstance(fingerprint, str) or not FINGERPRINT.fullmatch(fingerprint):
        raise RegistryError("identity file has an invalid fingerprint")
    return value


def empty_registry() -> dict[str, Any]:
    return {"schema": SCHEMA, "bindings": {}}


def load_registry(path: Path) -> dict[str, Any]:
    if not path.exists():
        return empty_registry()
    value = load_json(path)
    if (
        not isinstance(value, dict)
        or value.get("schema") != SCHEMA
        or not isinstance(value.get("bindings"), dict)
    ):
        raise RegistryError("registry has the wrong schema")
    return value


def binding_key(
    fingerprint: str, account_workspace: str, privacy_partition: str
) -> str:
    material = {
        "local_project_fingerprint": fingerprint,
        "account_or_workspace": account_workspace.strip().casefold(),
        "privacy_partition": privacy_partition.strip().casefold(),
    }
    return hashlib.sha256(canonical_json(material)).hexdigest()


def parse_chatgpt_url(value: str):
    try:
        parsed = urlsplit(value)
    except ValueError as exc:
        raise RegistryError(f"invalid ChatGPT URL: {exc}") from exc
    hostname = (parsed.hostname or "").casefold()
    if parsed.scheme != "https" or not (
        hostname == "chatgpt.com" or hostname.endswith(".chatgpt.com")
    ):
        raise RegistryError("project URL must be an https://chatgpt.com URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise RegistryError("project URL must not contain credentials, query, or fragment")
    return parsed


def validate_project_url(value: str) -> tuple[str, str]:
    parsed = parse_chatgpt_url(value)
    match = re.fullmatch(r"/g/(g-p-[A-Za-z0-9_-]+)/project/?", parsed.path)
    if not match:
        raise RegistryError(
            "project URL must identify a concrete /g/g-p-.../project resource"
        )
    return value, match.group(1)


def validate_conversation_url(value: str) -> str:
    parsed = parse_chatgpt_url(value)
    if not re.fullmatch(
        r"(?:/g/g-p-[A-Za-z0-9_-]+)?/c/[A-Za-z0-9_-]+/?", parsed.path
    ):
        raise RegistryError("conversation URL must identify a concrete ChatGPT chat")
    return value


def atomic_write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    finally:
        if temporary.exists():
            temporary.unlink()


def common(args: argparse.Namespace) -> tuple[Path, dict[str, Any], str, str]:
    if not args.account_workspace.strip():
        raise RegistryError("--account-workspace cannot be empty")
    if not args.privacy_partition.strip():
        raise RegistryError("--privacy-partition cannot be empty")
    identity_path = Path(args.identity).expanduser().resolve(strict=True)
    identity = load_identity(identity_path)
    fingerprint = identity["shareable"]["fingerprint"]
    key = binding_key(fingerprint, args.account_workspace, args.privacy_partition)
    return identity_path, identity, fingerprint, key


def command_lookup(args: argparse.Namespace) -> int:
    registry_path = Path(args.registry).expanduser().resolve()
    _, identity, fingerprint, key = common(args)
    registry = load_registry(registry_path)
    binding = registry["bindings"].get(key)
    binding_state = binding.get("state") if isinstance(binding, dict) else None
    status = (
        "FOUND"
        if binding_state == "VERIFIED"
        else ("STALE" if binding_state == "STALE" else "NOT_FOUND")
    )
    result = {
        "status": status,
        "binding_key": key,
        "local_project_fingerprint": fingerprint,
        "suggested_chatgpt_project_name": identity["shareable"][
            "suggested_chatgpt_project_name"
        ],
        "binding": binding,
        "registry": str(registry_path),
    }
    sys.stdout.write(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    return 0


def command_bind(args: argparse.Namespace) -> int:
    registry_path = Path(args.registry).expanduser().resolve()
    _, identity, fingerprint, key = common(args)
    project_url, url_project_id = validate_project_url(args.project_url)
    if not args.project_name.strip():
        raise RegistryError("--project-name cannot be empty")
    if not args.evidence or any(not value.strip() for value in args.evidence):
        raise RegistryError("at least one --evidence value is required")
    if args.project_id and args.project_id != url_project_id:
        raise RegistryError("--project-id does not match the project URL")
    registry = load_registry(registry_path)
    existing = registry["bindings"].get(key)
    if existing and existing.get("state") != "STALE":
        if existing.get("chatgpt_project", {}).get("url") != project_url:
            raise RegistryError(
                "a different active project is already bound; mark it stale first"
            )
    binding = {
        "state": "VERIFIED",
        "local_project": {
            "fingerprint": fingerprint,
            "name": identity["shareable"]["name"],
            "kind": identity["shareable"]["kind"],
            "local_root": identity["local_only"]["root"],
        },
        "routing": {
            "account_or_workspace": args.account_workspace,
            "privacy_partition": args.privacy_partition,
        },
        "chatgpt_project": {
            "name": args.project_name,
            "url": project_url,
            "id": args.project_id or url_project_id,
            "memory_mode": args.memory_mode,
            "shared_state": args.shared_state,
            "created_by_skill": args.created_by_skill,
        },
        "last_conversation_url": (
            validate_conversation_url(args.conversation_url)
            if args.conversation_url
            else None
        ),
        "verified_at": args.verified_at or now_utc(),
        "verification_evidence": args.evidence,
        "stale_reason": None,
    }
    registry["bindings"][key] = binding
    atomic_write(registry_path, registry)
    sys.stdout.write(
        json.dumps(
            {
                "status": "BOUND",
                "binding_key": key,
                "project_url": project_url,
                "registry": str(registry_path),
            },
            indent=2,
        )
        + "\n"
    )
    return 0


def command_stale(args: argparse.Namespace) -> int:
    registry_path = Path(args.registry).expanduser().resolve()
    _, _, _, key = common(args)
    registry = load_registry(registry_path)
    binding = registry["bindings"].get(key)
    if not binding:
        raise RegistryError("no binding exists for this identity/account/partition")
    binding["state"] = "STALE"
    binding["stale_reason"] = args.reason
    binding["stale_at"] = now_utc()
    atomic_write(registry_path, registry)
    sys.stdout.write(
        json.dumps(
            {
                "status": "STALE",
                "binding_key": key,
                "registry": str(registry_path),
            },
            indent=2,
        )
        + "\n"
    )
    return 0


def add_common(command: argparse.ArgumentParser) -> None:
    command.add_argument("--identity", required=True)
    command.add_argument("--account-workspace", required=True)
    command.add_argument("--privacy-partition", default="private")
    command.add_argument("--registry", default=str(DEFAULT_REGISTRY))


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        description="Maintain verified local-to-ChatGPT Project bindings."
    )
    commands = root.add_subparsers(dest="command", required=True)

    lookup = commands.add_parser("lookup")
    add_common(lookup)
    lookup.set_defaults(handler=command_lookup)

    bind = commands.add_parser("bind")
    add_common(bind)
    bind.add_argument("--project-url", required=True)
    bind.add_argument("--project-name", required=True)
    bind.add_argument("--project-id")
    bind.add_argument(
        "--memory-mode",
        required=True,
        choices=("project-only", "default"),
    )
    bind.add_argument(
        "--shared-state",
        required=True,
        choices=("private", "shared"),
    )
    bind.add_argument("--created-by-skill", action="store_true")
    bind.add_argument("--conversation-url")
    bind.add_argument("--verified-at")
    bind.add_argument("--evidence", action="append", default=[])
    bind.set_defaults(handler=command_bind)

    stale = commands.add_parser("mark-stale")
    add_common(stale)
    stale.add_argument("--reason", required=True)
    stale.set_defaults(handler=command_stale)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        return args.handler(args)
    except (RegistryError, OSError, ValueError) as exc:
        sys.stderr.write(
            json.dumps({"status": "BLOCKED", "error": str(exc)}, ensure_ascii=False)
            + "\n"
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
