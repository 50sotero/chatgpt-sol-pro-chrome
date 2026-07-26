# Local project to ChatGPT Project routing

Resolve project identity before choosing a conversation. A local project, a ChatGPT Project, and a ChatGPT conversation are three different objects; record each independently.

## Identify the task origin

Run:

```powershell
python scripts\identify_project.py --start "<task path>" --output "<project-identity.json>"
```

Choose the start path in this order:

1. an explicit file, folder, repository, or worktree named by the user;
2. the active workspace containing the files being changed;
3. the process working directory.

The detector prefers the Git toplevel, then a nearest strong workspace marker. It reports a shareable fingerprint plus local-only path evidence. Treat generated `Documents/Codex/<date>/<slug>` folders with only `work/` and `outputs/` as projectless staging, not product repositories.

When several repositories are intentionally in scope, choose one primary project for ChatGPT routing and list the others as context dependencies. Do not merge identities silently.

## Resolve an existing ChatGPT Project

Use this precedence:

1. The exact ChatGPT Project URL or name explicitly supplied by the user.
2. An exact project URL in the private local binding registry or a prior run receipt whose local project fingerprint and ChatGPT account/workspace still match.
3. A unique visible project with the deterministic name `<project name> [<fingerprint prefix>]`.
4. A unique legacy project candidate backed by exact local provenance, such as a recorded canonical project URL and prior conversation URL.

A similar name, a conversation topic, or the current sidebar selection is not proof. Do not inspect unrelated project conversations to infer a match.

For an exact URL, navigate to it and verify the visible project name, stable URL/ID, account/workspace, memory mode, and private/shared state before reuse. If the URL is gone, the account/workspace differs, or evidence conflicts, mark the binding stale and continue to creation or ask the user when their choice is material.

Look up a verified local binding with:

```powershell
python scripts\project_registry.py lookup `
  --identity "<project-identity.json>" `
  --account-workspace "<visible account or workspace>"
```

A reused project carries persistent chats, files, and project instructions. Reuse does not authorize a new upload. Before every transmission, verify whether the project is shared; all project members can see project chats and files. Require exact confirmation before uploading sensitive material to a shared project, and prefer a new isolated project across client, tenant, or security boundaries.

## Create only when needed

If no verified match exists:

1. Derive a deterministic, privacy-safe name:
   - local project: `<project name> [<first 8 fingerprint characters>]`;
   - projectless task: `Codex Task - <concise task label> [<first 8 task-fingerprint characters>]`.
2. Search the visible project list for that exact name once.
3. If absent, start the Create Project action once.
4. Enter the deterministic name, choose project-only memory when available, and complete creation once. Project-only memory is a creation-time isolation choice and existing default-memory projects cannot be converted.
5. Prove success from a new stable project URL/ID and matching visible name.
6. Verify the project is not shared and record its memory mode.
7. Persist the binding locally using [../assets/project-binding.json](../assets/project-binding.json).

Use `scripts/project_registry.py bind` only after the visible project name, URL/ID, account/workspace, memory mode, and sharing state have been verified. The command requires at least one concrete `--evidence` value and refuses to replace a conflicting active binding.

Never include a Windows username, absolute local path, secret remote credential, customer identity, or branch name in the ChatGPT Project name. Review the detector's suggested name before searching or creating; use `identify_project.py --project-label "<privacy-safe label>"` when a manifest or repository label is sensitive.

Project creation is authorized by a request to run through this skill when no verified match exists. Renaming, deletion, sharing, permission changes, and workspace migration are separate actions and require separate authority.

If project-only memory is unavailable, record `default` only when that state is visibly verified. Before sensitive uploads on non-Enterprise plans, disclose that default-memory project chats may reference context outside the project and obtain explicit confirmation or create an isolated project when the control becomes available. Never record an unknown memory or sharing state as verified.

## Recover from ambiguity

After a click that may have created a project:

- remain on the same tab;
- inspect the resulting URL, heading, dialog state, and project list;
- search for the deterministic exact name;
- adopt a single proven result and record its ID/URL.

Never click Create again merely because a timeout or reconnect hid the postcondition. If two exact-name candidates exist, stop as `UNCERTAIN`; do not choose by position.

## Persist a durable binding

Keep the binding in a private registry outside the repository and outside the upload bundle, for example `~/.codex/state/chatgpt-sol-pro-chrome/project-bindings.json`. Namespace it by ChatGPT account/workspace and privacy partition. Record:

- local project shareable fingerprint and identity basis;
- local root only in the local record;
- ChatGPT account/workspace label when relevant;
- exact project name, stable URL, and stable ID when visible;
- memory mode and private/shared state;
- creation or verification evidence and timestamp;
- last known canonical conversation URL;
- stale reason when verification later fails.

Write the binding atomically only after visible verification. Do not commit the registry or a machine-specific absolute path. Put a binding in a repository only when the user explicitly asks to version that association.

## Choose the conversation inside the project

- New independent answer: new conversation inside the resolved project.
- Iterative review, prior authoritative screens, or accepted decisions: exact prior conversation.
- Independent second opinion: new conversation in the same project, without copying the first answer.
- Projectless one-off task: its task-scoped project and a new conversation.

Persistent project files and old conversation content can be stale. The current prompt and content-addressed context bundle remain authoritative; state source priority explicitly.

Do not automatically move an outside conversation into the project. A moved chat inherits the project's instructions and file context; start a new project chat with a bounded handoff unless the user explicitly requests the move.

Recheck the current official Projects guidance if creation, memory, sharing, file-limit, or move-chat controls differ from the visible UI:

- https://help.openai.com/en/articles/10169521-projects-in-chatgpt
