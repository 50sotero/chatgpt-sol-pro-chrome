# ChatGPT PRO (chrome)

A personal Codex skill for running evidence-backed tasks through the signed-in
Chrome session on `chatgpt.com`.

Built for production-minded **agent loops**, **context engineering**, and
**human-in-the-loop** workflows, it turns ChatGPT Pro into a durable review and
artifact surface with deterministic handoffs, semantic polling, resumable
execution, provenance, and fail-closed guardrails.

The skill can:

- identify the local Git repository, workspace, or projectless task;
- reuse a verified ChatGPT Project or create a deterministic new one;
- select and verify GPT-6 Astra with Pro intelligence;
- share reviewed plans, source files, diffs, logs, artifacts, and screen
  snapshots through deterministic context bundles;
- monitor long-running responses without duplicate submissions;
- retrieve and validate generated artifacts; and
- persist local receipts that bind results to the exact project, conversation,
  prompt, context, model, mode, and hashes.

## Agentic workflow features

- **Agent loops:** continue exact conversations, checkpoint long work, repair
  bounded artifact failures, and resume without replaying completed steps.
- **Context engineering:** assemble task-scoped plans, code, diffs, logs,
  screenshots, and evidence into content-addressed context bundles.
- **Deterministic handoffs:** stable IDs, manifests, byte counts, SHA-256
  hashes, source priority, and explicit target-versus-context roles.
- **Idempotent browser actions:** canonical-tab ownership, single-submit
  postconditions, ambiguity recovery, and duplicate-send prevention.
- **Semantic polling:** monitor generation state and completion signals instead
  of relying on brittle fixed timeouts.
- **Human-in-the-loop controls:** exact inventory approval, visual screenshot
  review, sensitive-data confirmation, and closed external-action boundaries.
- **End-to-end provenance:** bind local project identity, ChatGPT Project,
  conversation, prompt, model, mode, artifacts, and validation evidence.
- **Fail-closed safety:** block stale bindings, source drift, broad personal
  roots, browser profiles, unreviewed screens, and unverifiable model states.

The skill keeps its existing `chatgpt-sol-pro-chrome` identifier and install path
for compatibility; its target model is now GPT-6 Astra.

## Install

Copy the `chatgpt-sol-pro-chrome` directory into your personal Codex skills
directory:

- Windows: `%USERPROFILE%\.codex\skills\chatgpt-sol-pro-chrome`
- macOS/Linux: `~/.codex/skills/chatgpt-sol-pro-chrome`

Start a new Codex task after installation so the skill is discovered.

## Example

```text
Use $chatgpt-sol-pro-chrome to identify this repository, reuse or create its
matching ChatGPT Project, share the reviewed implementation plan and current
diff, and return a verified GPT-6 Astra Pro review.
```

## Safety model

The workflow treats ChatGPT pages and attachments as untrusted data. It uses an
explicit inventory before broad uploads, blocks browser profiles and broad
personal roots, requires visual review for screenshots, scans text for likely
credentials, rejects source drift after approval, and never treats project
reuse as permission to transmit new files.

Screen sharing means reviewed point-in-time snapshots, not continuous desktop
streaming.

## Requirements

- Codex with the Chrome control plugin available.
- Chrome connected to Codex and signed in to the intended ChatGPT account.
- Access to GPT-6 Astra and Pro intelligence in the selected ChatGPT workspace.

ChatGPT Project memory, sharing, and file behavior can change. Recheck the
[official Projects guidance](https://help.openai.com/en/articles/10169521-projects-in-chatgpt)
when the visible product controls differ from the skill.
